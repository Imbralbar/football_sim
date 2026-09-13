"""Rozstrzyganie starc - serce mechaniki symulatora.

Zasada nadrzedna:
    pilka przy nodze  (GROUND) -> przewaga ATAKUJACEGO (remis dla atakujacego)
    pilka w powietrzu (AIR)    -> przewaga OBRONCY     (remis dla obroncy)

Wzor ogolny:
    wynik_atakujacego = statystyka_akcji  + k10
    wynik_obroncy     = statystyka_obrony + k10
                        + MISMATCH_PENALTY  (gdy obrona NIE sparowana z akcja)
                        + AIR_INTERCEPT_BONUS (gdy kontekst AIR)

Modul jest czysty: nie zmienia stanu zawodnikow ani nie przenosi pilki -
to zadanie modulu match.py. Kazde rozstrzygniecie zuzywa DOKLADNIE dwa
rzuty k10, zawsze w kolejnosci: atakujacy, potem obronca.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from config import (
    AIR_INTERCEPT_BONUS,
    GK_TIE_CATCH_FAILS,
    MISMATCH_PENALTY,
    TIE_AIR_TO_DEFENDER,
    TIE_GROUND_TO_ATTACKER,
)
from core.actions import (
    AttackAction,
    DefenceAction,
    DuelContext,
    GkAction,
    ShotPlacement,
    attack_stat as get_attack_stat,
    defence_stat as get_defence_stat,
    gk_stat as get_gk_stat,
    is_paired,
)
from core.dice import Rng
from core.entities import Player

__all__ = [
    "Outcome",
    "DuelResult",
    "resolve_ground_duel",
    "resolve_air_interception",
    "resolve_gk_save",
]


class Outcome(str, Enum):
    """Wynik rozstrzygniecia - jedyne zrodlo prawdy dla match.py."""

    KEEP_BALL = "KEEP_BALL"                # atakujacy zachowuje pilke
    BEAT_DEFENDER = "BEAT_DEFENDER"        # udany drybling, minal obronce
    TURNOVER = "TURNOVER"                  # obronca przejmuje pilke
    PASS_COMPLETED = "PASS_COMPLETED"      # podanie doszlo do celu
    PASS_INTERCEPTED = "PASS_INTERCEPTED"  # podanie przechwycone
    SHOT_ON_TARGET = "SHOT_ON_TARGET"      # strzal przeszedl -> duel z GK
    SHOT_BLOCKED = "SHOT_BLOCKED"          # strzal zablokowany przez obronce
    GOAL = "GOAL"
    SAVE_CAUGHT = "SAVE_CAUGHT"            # GK zlapal, ma pilke
    SAVE_PUNCHED = "SAVE_PUNCHED"          # GK wybil, pilka wolna
    SAVE_LOOSE = "SAVE_LOOSE"              # GK obronil ale nie zlapal (remis przy 9)


# --------------------------------------------------------------------------
# nazwy akcji do logu - wartosci nie koliduja miedzy enumami
# (atak: 5/6/7 oraz 8/9 placement, obrona: 2/3/4 oraz 8/9 GK)
# --------------------------------------------------------------------------
_ATTACK_NAMES: dict[int, str] = {int(a): a.name for a in AttackAction}
_ATTACK_NAMES.update({int(p): p.name for p in ShotPlacement})

_DEFENCE_NAMES: dict[int, str] = {int(d): d.name for d in DefenceAction}
_DEFENCE_NAMES.update({int(g): g.name for g in GkAction})

# sparowanie strzelec <-> bramkarz
_GK_PAIRS: dict[ShotPlacement, GkAction] = {
    ShotPlacement.POWER: GkAction.PUNCH,
    ShotPlacement.PLACED: GkAction.CATCH,
}


def _format_side(number: int, name: str, stat: int, roll: int,
                 mods: tuple[int, ...], total: int) -> str:
    """Sklada jedna strone opisu: "#4 VS_SHOT(15)+4-6+3=16"."""
    text = f"#{number} {name}({stat})+{roll}"
    for mod in mods:
        if mod:
            text += f"{mod:+d}"
    return f"{text}={total}"


@dataclass(frozen=True)
class DuelResult:
    """Niezmienny zapis pojedynczego rozstrzygniecia (pelny audyt rzutow)."""

    context: DuelContext
    attacker_number: int
    defender_number: int
    attack: int              # wartosc IntEnum akcji ataku
    defence: int             # wartosc IntEnum akcji obrony
    attack_stat: int
    defence_stat: int
    attack_roll: int         # surowy k10
    defence_roll: int        # surowy k10
    mismatch_penalty: int    # 0 lub MISMATCH_PENALTY
    context_bonus: int       # 0 lub AIR_INTERCEPT_BONUS
    attack_total: int
    defence_total: int
    attacker_wins: bool
    was_tie: bool            # totals byly rowne PRZED regula remisu
    outcome: Outcome

    def describe(self) -> str:
        """Czytelny jednolinijkowy opis do logu.

        Przyklad:
            "GROUND #10 DRIBBLE(15)+7=22 vs #4 VS_SHOT(15)+4-6+3=16 -> BEAT_DEFENDER"

        Modyfikatory (-6 / +3) pokazywane sa tylko gdy sa niezerowe.
        """
        attack_side = _format_side(
            self.attacker_number,
            _ATTACK_NAMES.get(self.attack, str(self.attack)),
            self.attack_stat,
            self.attack_roll,
            (),
            self.attack_total,
        )
        defence_side = _format_side(
            self.defender_number,
            _DEFENCE_NAMES.get(self.defence, str(self.defence)),
            self.defence_stat,
            self.defence_roll,
            (self.mismatch_penalty, self.context_bonus),
            self.defence_total,
        )
        return (
            f"{self.context.value} {attack_side} vs {defence_side} "
            f"-> {self.outcome.value}"
        )


def _roll_pair(rng: Rng) -> tuple[int, int]:
    """Dwa rzuty k10 w ustalonej kolejnosci: atakujacy, potem obronca.

    Kolejnosc jest warunkiem powtarzalnosci symulacji - nie zmieniac.
    """
    attack_roll = rng.roll()
    defence_roll = rng.roll()
    return attack_roll, defence_roll


# ---------- 1. starcie zawodnik-zawodnik (pilka przy nodze) ----------
def resolve_ground_duel(attacker: Player, defender: Player,
                        attack: AttackAction, defence: DefenceAction,
                        rng: Rng) -> DuelResult:
    """Kontekst GROUND. Bez bonusu kontekstowego.

    Mapowanie outcome:
      atakujacy wygrywa + DRIBBLE  -> BEAT_DEFENDER
      atakujacy wygrywa + PASS     -> PASS_COMPLETED
      atakujacy wygrywa + SHOT     -> SHOT_ON_TARGET
      atakujacy przegrywa + SHOT   -> SHOT_BLOCKED
      atakujacy przegrywa (inne)   -> TURNOVER
      remis -> atakujacy wygrywa, ale przy DRIBBLE outcome = KEEP_BALL
               (nie mija obroncy - zostaje na swojej kratce)
    """
    a_stat = get_attack_stat(attacker, attack)
    d_stat = get_defence_stat(defender, defence)

    mismatch = 0 if is_paired(attack, defence) else MISMATCH_PENALTY
    context_bonus = 0

    attack_roll, defence_roll = _roll_pair(rng)

    attack_total = a_stat + attack_roll
    defence_total = d_stat + defence_roll + mismatch + context_bonus

    was_tie = attack_total == defence_total
    attacker_wins = attack_total > defence_total or (was_tie and TIE_GROUND_TO_ATTACKER)

    if attacker_wins:
        if attack == AttackAction.DRIBBLE:
            # remis = pilka zostaje, ale obronca NIE zostal miniety
            outcome = Outcome.KEEP_BALL if was_tie else Outcome.BEAT_DEFENDER
        elif attack == AttackAction.PASS:
            outcome = Outcome.PASS_COMPLETED
        else:
            outcome = Outcome.SHOT_ON_TARGET
    else:
        outcome = Outcome.SHOT_BLOCKED if attack == AttackAction.SHOT else Outcome.TURNOVER

    return DuelResult(
        context=DuelContext.GROUND,
        attacker_number=attacker.number,
        defender_number=defender.number,
        attack=int(attack),
        defence=int(defence),
        attack_stat=a_stat,
        defence_stat=d_stat,
        attack_roll=attack_roll,
        defence_roll=defence_roll,
        mismatch_penalty=mismatch,
        context_bonus=context_bonus,
        attack_total=attack_total,
        defence_total=defence_total,
        attacker_wins=attacker_wins,
        was_tie=was_tie,
        outcome=outcome,
    )


# ---------- 2. przechwyt na trajektorii (pilka w powietrzu) ----------
def resolve_air_interception(attacker: Player, defender: Player,
                             attack: AttackAction, defence: DefenceAction,
                             rng: Rng,
                             attack_value: int | None = None) -> DuelResult:
    """Kontekst AIR. Obronca dostaje AIR_INTERCEPT_BONUS (+3).

    attack MUSI byc PASS lub SHOT - inaczej ValueError.
    attack_value: gdy podane, nadpisuje attack_stat
                  (uzywane dla strzalu, gdzie wartosc liczy shot_value()).

    Mapowanie outcome:
      atakujacy wygrywa + PASS -> PASS_COMPLETED
      atakujacy wygrywa + SHOT -> SHOT_ON_TARGET
      obronca wygrywa + PASS   -> PASS_INTERCEPTED
      obronca wygrywa + SHOT   -> SHOT_BLOCKED
      remis -> wygrywa OBRONCA
    """
    if attack not in (AttackAction.PASS, AttackAction.SHOT):
        raise ValueError(
            f"przechwyt w powietrzu dotyczy tylko PASS lub SHOT, otrzymano: {attack!r}"
        )

    a_stat = get_attack_stat(attacker, attack) if attack_value is None else int(attack_value)
    d_stat = get_defence_stat(defender, defence)

    mismatch = 0 if is_paired(attack, defence) else MISMATCH_PENALTY
    context_bonus = AIR_INTERCEPT_BONUS

    attack_roll, defence_roll = _roll_pair(rng)

    attack_total = a_stat + attack_roll
    defence_total = d_stat + defence_roll + mismatch + context_bonus

    was_tie = attack_total == defence_total
    attacker_wins = attack_total > defence_total or (was_tie and not TIE_AIR_TO_DEFENDER)

    if attacker_wins:
        outcome = Outcome.PASS_COMPLETED if attack == AttackAction.PASS else Outcome.SHOT_ON_TARGET
    else:
        outcome = Outcome.PASS_INTERCEPTED if attack == AttackAction.PASS else Outcome.SHOT_BLOCKED

    return DuelResult(
        context=DuelContext.AIR,
        attacker_number=attacker.number,
        defender_number=defender.number,
        attack=int(attack),
        defence=int(defence),
        attack_stat=a_stat,
        defence_stat=d_stat,
        attack_roll=attack_roll,
        defence_roll=defence_roll,
        mismatch_penalty=mismatch,
        context_bonus=context_bonus,
        attack_total=attack_total,
        defence_total=defence_total,
        attacker_wins=attacker_wins,
        was_tie=was_tie,
        outcome=outcome,
    )


# ---------- 3. strzal vs bramkarz ----------
def resolve_gk_save(shooter: Player, gk: Player,
                    shot_value: int, placement: ShotPlacement,
                    gk_choice: GkAction, rng: Rng) -> DuelResult:
    """Bramkarz deklaruje PUNCH(8) albo CATCH(9) w ciemno.

    Strzelec deklaruje POWER(8) albo PLACED(9).
    Sparowanie: POWER<->PUNCH, PLACED<->CATCH.
    Brak sparowania -> MISMATCH_PENALTY dla bramkarza.
    Kontekst = AIR, ale BEZ AIR_INTERCEPT_BONUS (bramkarz ma juz stat 20).

    Mapowanie outcome:
      strzelec wygrywa            -> GOAL
      GK wygrywa + CATCH          -> SAVE_CAUGHT
      GK wygrywa + PUNCH          -> SAVE_PUNCHED
      remis + gk_choice == CATCH  -> SAVE_LOOSE   (regula: nie lapie przy 9)
      remis + gk_choice == PUNCH  -> SAVE_PUNCHED

    Rzuca ValueError gdy not gk.is_gk.
    """
    if not gk.is_gk:
        raise ValueError(
            f"obronca strzalu musi byc bramkarzem, zawodnik #{gk.number} nim nie jest"
        )

    placement = ShotPlacement(placement)
    gk_choice = GkAction(gk_choice)

    a_stat = int(shot_value)
    d_stat = get_gk_stat(gk, gk_choice)

    paired = _GK_PAIRS[placement] == gk_choice
    mismatch = 0 if paired else MISMATCH_PENALTY
    context_bonus = 0  # bramkarz nie dostaje bonusu za pilke w powietrzu

    attack_roll, defence_roll = _roll_pair(rng)

    attack_total = a_stat + attack_roll
    defence_total = d_stat + defence_roll + mismatch + context_bonus

    was_tie = attack_total == defence_total
    attacker_wins = attack_total > defence_total  # remis zawsze dla bramkarza

    if attacker_wins:
        outcome = Outcome.GOAL
    elif gk_choice == GkAction.PUNCH:
        outcome = Outcome.SAVE_PUNCHED
    elif was_tie and GK_TIE_CATCH_FAILS:
        outcome = Outcome.SAVE_LOOSE  # zlapal-nie zlapal: pilka wypada
    else:
        outcome = Outcome.SAVE_CAUGHT

    return DuelResult(
        context=DuelContext.AIR,
        attacker_number=shooter.number,
        defender_number=gk.number,
        attack=int(placement),
        defence=int(gk_choice),
        attack_stat=a_stat,
        defence_stat=d_stat,
        attack_roll=attack_roll,
        defence_roll=defence_roll,
        mismatch_penalty=mismatch,
        context_bonus=context_bonus,
        attack_total=attack_total,
        defence_total=defence_total,
        attacker_wins=attacker_wins,
        was_tie=was_tie,
        outcome=outcome,
    )