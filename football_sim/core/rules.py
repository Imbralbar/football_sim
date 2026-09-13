"""
Modul M4 - Zasady gry.

Dispatcher rozstrzygajacy wyniki akcji (podania, strzaly, gole).
NIE modyfikuje stanu gry - to zadanie match.py.
"""

from __future__ import annotations
from typing import TYPE_CHECKING
from dataclasses import dataclass
from enum import Enum

if TYPE_CHECKING:
    from core.state import GameState
    from core.entities import Player

from core.geometry import line
from core.actions import AttackAction, DefenceAction, shot_value, ShotPlacement, GkAction
from core.resolver import resolve_air_interception, resolve_gk_save, Outcome
from core.dice import Rng


class PassResult(str, Enum):
    """Wynik podania."""
    COMPLETE = "COMPLETE"
    INTERCEPTED = "INTERCEPTED"


class ShotResult(str, Enum):
    """Wynik strzalu."""
    GOAL = "GOAL"
    SAVED = "SAVED"
    INTERCEPTED = "INTERCEPTED"
    OUT = "OUT"


@dataclass
class PassOutcome:
    """Pelny wynik podania z detalami."""
    result: PassResult
    interceptor: Player | None
    target: Player


@dataclass
class ShotOutcome:
    """Pelny wynik strzalu z detalami."""
    result: ShotResult
    interceptor: Player | None
    goalkeeper: Player


def resolve_pass(
    state: GameState,
    passer: Player,
    target: Player,
    rng: Rng
) -> PassOutcome:
    """
    Rozstrzyga podanie od passer do target.

    Mechanika (sekcja 6.4-6.5 dokumentacji):
    1. Trajektoria = line(passer.pos, target.pos)
    2. Dla kazdej kratki na trasie (pomijajac passer.pos):
       - Sprawdz, czy stoi tam przeciwnik (opponents_of(passer))
       - Jesli TAK -> resolve_air_interception(PASS, VS_PASS, ...)
         * Jesli interceptor wygra -> INTERCEPTED, pilka do niego
         * Jesli passer wygra -> podanie leci dalej
    3. Jesli dotarlo do target.pos -> COMPLETE

    Args:
        state: aktualny stan gry
        passer: podajacy zawodnik
        target: adresat podania (z tej samej druzyny!)
        rng: generator losowy

    Returns:
        PassOutcome z wynikiem i interceptorem (jesli byl)

    UWAGA: funkcja NIE modyfikuje state/ball - to robi match.py
    """
    # Trajektoria pomijajac pozycje passera
    trajectory = line(passer.pos, target.pos)[1:]
    
    # Wszyscy przeciwnicy z pola (bez bramkarza)
    opponents = state.opponents_of(passer).outfield()
    
    # Sprawdzamy kazda kratke na trasie
    for cell in trajectory:
        for opp in opponents:
            if opp.pos == cell:
                # STARCIE: proba przechwycenia w powietrzu
                result = resolve_air_interception(
                    passer,
                    opp,
                    AttackAction.PASS,
                    DefenceAction.VS_PASS,
                    rng
                )
                
                if result.outcome == Outcome.PASS_INTERCEPTED:
                    return PassOutcome(
                        PassResult.INTERCEPTED,
                        interceptor=opp,
                        target=target
                    )
                # Jesli nie przechwycil -> podanie leci dalej
    
    # Dotarlo do celu
    return PassOutcome(PassResult.COMPLETE, interceptor=None, target=target)


def resolve_shot(
    state: GameState,
    shooter: Player,
    rng: Rng
) -> ShotOutcome:
    """
    Rozstrzyga strzal na bramke.

    Mechanika:
    1. Cel = field.goal_center(shooter.side.opposite().value)
    2. Trajektoria = line(shooter.pos, cel)
    3. Dla kazdej kratki (pomijajac shooter.pos):
       - Czy stoi tam przeciwnik z pola (not is_gk)?
         -> resolve_air_interception(SHOT, VS_SHOT, ...)
         -> jesli przechwycil -> INTERCEPTED
    4. Jesli dotarlo do bramki:
       - Znajdz bramkarza (opponents_of(shooter).gk())
       - resolve_gk_save(shot_value(...), GkAction, gk_stat)
         * GOAL -> bramka
         * SAVE_* -> obroniony
    5. Opcjonalnie: jesli cel.y poza goal_rows() -> OUT (niecelny)

    Args:
        state: stan gry
        shooter: strzelec
        rng: generator

    Returns:
        ShotOutcome z wynikiem, interceptorem lub bramkarzem

    UWAGA: funkcja NIE modyfikuje state/ball
    """
    # Cel = srodek bramki przeciwnika
    goal_center = state.field.goal_center(shooter.side.opposite().value)
    
    # Trajektoria pomijajac pozycje strzelca
    trajectory = line(shooter.pos, goal_center)[1:]
    
    # Wszyscy przeciwnicy z pola (bez bramkarza)
    opponents = state.opponents_of(shooter).outfield()
    
    # Bramkarz przeciwnika
    goalkeeper = state.opponents_of(shooter).gk()
    
    # Wartosc strzalu (zalezna od odleglosci/pola karnego)
    shot_val = shot_value(state.field, shooter)
    
    # Sprawdzamy kazda kratke na trasie
    for cell in trajectory:
        for opp in opponents:
            if opp.pos == cell:
                # STARCIE: proba zablokowania strzalu
                result = resolve_air_interception(
                    shooter,
                    opp,
                    AttackAction.SHOT,
                    DefenceAction.VS_SHOT,
                    rng,
                    attack_value=shot_val
                )
                
                if result.outcome == Outcome.SHOT_BLOCKED:
                    return ShotOutcome(
                        ShotResult.INTERCEPTED,
                        interceptor=opp,
                        goalkeeper=goalkeeper
                    )
                # Jesli nie zablokował -> strzal leci dalej
    
    # Dotarlo do bramki - starcie z bramkarzem
    # TODO M5: AI moze wybierac placement, teraz losujemy 50/50
    placement = ShotPlacement.PLACED if rng.roll() > 5 else ShotPlacement.POWER
    
    # TODO M5: AI bramkarza moze wybierac akcje, teraz losujemy 50/50
    gk_action = GkAction.CATCH if rng.roll() > 5 else GkAction.PUNCH
    
    gk_result = resolve_gk_save(shooter, goalkeeper, shot_val, placement, gk_action, rng)
    
    if gk_result.outcome == Outcome.GOAL:
        return ShotOutcome(
            ShotResult.GOAL,
            interceptor=None,
            goalkeeper=goalkeeper
        )
    else:
        # SAVE_CAUGHT, SAVE_PUNCHED, SAVE_LOOSE -> wszystkie SAVED
        return ShotOutcome(
            ShotResult.SAVED,
            interceptor=None,
            goalkeeper=goalkeeper
        )


def is_goal(state: GameState) -> tuple[bool, str | None]:
    """
    Sprawdza, czy pilka przekroczyla linie bramkowa = GOL.

    Warunki:
    - ball.cell.x < 0 -> gol dla RIGHT (bramka LEFT)
    - ball.cell.x >= field.w -> gol dla LEFT (bramka RIGHT)
    - ball.cell.y musi byc w field.goal_rows() (3 kratki srodkowe)

    Returns:
        (True, "LEFT"|"RIGHT") jesli gol, (False, None) w p.p.

    Strona = kto STRACIL bramke (LEFT stracil -> RIGHT zdobyl punkt)
    """
    ball_pos = state.ball.cell
    goal_rows = state.field.goal_rows()
    
    # Sprawdz, czy y w zakresie bramki
    if ball_pos.y not in goal_rows:
        return (False, None)
    
    # Bramka LEFT (x < 0)
    if ball_pos.x < 0:
        return (True, "LEFT")
    
    # Bramka RIGHT (x >= field.w)
    if ball_pos.x >= state.field.w:
        return (True, "RIGHT")
    
    return (False, None)


def is_out_of_bounds(state: GameState) -> bool:
    """
    Sprawdza, czy pilka wyszla poza boisko (aut).

    Returns:
        True jesli ball.cell poza field.inside()

    UWAGA: aut/rzut rozny swiadomie odlozone do M5.
    Ta funkcja sluzy tylko do wykrywania - match.py moze zignorowac.
    """
    return not state.field.inside(state.ball.cell)