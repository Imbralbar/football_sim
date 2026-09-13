"""
core/ai.py – AI decydująca, co zawodnik robi z piłką.

Filozofia wg roli:
  FWD : shoot (szeroki zasięg) > dribble > pass (tylko pod presją)
  MID : pass-forward > shoot > dribble
  DEF : pass-forward > dribble   ← nigdy nie blokuje gry
  GK  : pass-forward > dribble

Podanie jest opłacalne tylko gdy odbiorca jest bliżej bramki
o co najmniej PASS_MIN_GAIN kratek (metryka Chebyshev).
Podania FWD↔FWD są dozwolone, ale traktowane jako ostatnia deska ratunku.
"""

from __future__ import annotations
from typing import TYPE_CHECKING
from enum import Enum

if TYPE_CHECKING:
    from core.state import GameState
    from core.entities import Player

import config as C


# ── Typ decyzji (bez zmian – zachowana kompatybilność) ────────────────────

class AiDecision(str, Enum):
    """Typ decyzji AI – co zrobić z piłką."""
    CONTINUE_DRIBBLE = "CONTINUE_DRIBBLE"
    PASS             = "PASS"
    SHOOT            = "SHOOT"


# ── Pomocnicze ────────────────────────────────────────────────────────────

def _shot_range(role: str) -> int:
    """Zasięg strzału wg roli zawodnika."""
    return {
        "FWD": C.FWD_SHOT_RANGE,
        "MID": C.MID_SHOT_RANGE,
        "DEF": C.DEF_SHOT_RANGE,
        "GK":  C.DEF_SHOT_RANGE,   # GK nie strzela z akcji
    }.get(role, C.DEF_SHOT_RANGE)


def is_under_pressure(state: GameState, carrier: Player,
                      threshold: int) -> bool:
    """
    True jeśli jakikolwiek przeciwnik (nie bramkarz) jest
    ≤ threshold kratek od carriery (metryka Chebyshev).
    """
    for opp in state.opponents_of(carrier).outfield():
        if state.field.distance(carrier.pos, opp.pos) <= threshold:
            return True
    return False


# ── Wybór celu podania ────────────────────────────────────────────────────

def pick_pass_target(state: GameState, carrier: Player) -> Player | None:
    """
    Wybiera najlepszego odbiorcę podania.

    Kryteria:
    1. Kandydat musi być bliżej bramki przeciwnika niż carrier
       o co najmniej PASS_MIN_GAIN kratek → „podanie do przodu".
    2. Podania do gracza tej samej roli (np. FWD→FWD) dostają karę
       w sortowaniu – lądują za graczami innej roli.
    3. Spośród równorzędnych: najpierw bliżej bramki, potem bliżej nas
       (łatwiejsze podanie).
    4. Fallback: jeśli brak kandydatów spełniających próg MIN_GAIN,
       zwróć najlepszego gracza bliżej bramki (gain > 0).
    5. Brak nikogo bliżej bramki → None (nie podawaj).

    Args:
        state:   aktualny stan gry
        carrier: zawodnik z piłką

    Returns:
        Player | None
    """
    opp_side     = carrier.side.opposite().value
    carrier_dist = state.field.distance_to_goal(carrier.pos, opp_side)
    carrier_role = carrier.role.value

    # Pula kandydatów: drużyna, bez bramkarza, bez siebie
    candidates = [p for p in state.team_of(carrier).outfield()
                  if p != carrier]
    if not candidates:
        return None

    preferred = []   # gain >= PASS_MIN_GAIN
    fallback   = []  # 0 < gain < PASS_MIN_GAIN

    for p in candidates:
        p_dist = state.field.distance_to_goal(p.pos, opp_side)
        gain   = carrier_dist - p_dist          # dodatni → kolega bliżej bramki

        if gain >= C.PASS_MIN_GAIN:
            # Kara za tę samą rolę (FWD→FWD, MID→MID)
            same_role_penalty = (
                1 if (C.PASS_PENALIZE_SAME_ROLE
                      and p.role.value == carrier_role)
                else 0
            )
            dist_from_us = state.field.distance(carrier.pos, p.pos)
            preferred.append((same_role_penalty, p_dist, dist_from_us, p))

        elif gain > 0:
            dist_from_us = state.field.distance(carrier.pos, p.pos)
            fallback.append((p_dist, dist_from_us, p))

    if preferred:
        preferred.sort(key=lambda t: (t[0], t[1], t[2]))
        return preferred[0][3]

    if fallback:
        fallback.sort(key=lambda t: (t[0], t[1]))
        return fallback[0][2]

    return None   # wszyscy są dalej od bramki niż carrier → nie podawaj


# ── Główna funkcja decyzyjna ──────────────────────────────────────────────

def decide_action(state: GameState,
                  carrier: Player) -> tuple[AiDecision, Player | None]:
    """
    Decyduje, co zawodnik robi z piłką.

    Wywołana w każdym ticku ruchu carriery (co 3 ticki).

    Returns:
        (AiDecision.CONTINUE_DRIBBLE, None)
        (AiDecision.PASS,  Player)   – target zawsze nie-None przy PASS
        (AiDecision.SHOOT, None)

    Priorytety:

    KAŻDA ROLA – pole karne przeciwnika:
        → SHOOT (zawsze, bez względu na zasięg)

    FWD (agresywny):
        1. Zasięg strzału → SHOOT
        2. Brak presji    → CONTINUE_DRIBBLE  (jedź do przodu)
        3. Presja + jest cel podania do przodu → PASS
        4.                  brak celu          → CONTINUE_DRIBBLE

    MID (rozgrywający):
        1. Brak presji + jest cel podania do przodu → PASS
        2. Zasięg strzału → SHOOT
        3. Presja + jest cel podania → PASS
        4. Fallback → CONTINUE_DRIBBLE

    DEF / GK (budowanie gry):
        1. Jest cel podania do przodu → PASS
        2. Fallback → CONTINUE_DRIBBLE  (nigdy nie blokuje)
    """
    role     = carrier.role.value
    opp_side = carrier.side.opposite().value

    in_penalty   = state.field.in_penalty_area(carrier.pos, opp_side)
    goal_dist    = state.field.distance_to_goal(carrier.pos, opp_side)
    under_press  = is_under_pressure(state, carrier, C.THREAT_DISTANCE)
    shot_range   = _shot_range(role)

    # ── 0. Pole karne → zawsze strzał ─────────────────────────────────────
    if in_penalty:
        return (AiDecision.SHOOT, None)

    # ── FWD: shoot > dribble > pass ───────────────────────────────────────
    if role == "FWD":
        if goal_dist <= shot_range:
            return (AiDecision.SHOOT, None)

        if not under_press:
            # Swobodny FWD poza zasięgiem → jedź do przodu, nie trać tempa
            return (AiDecision.CONTINUE_DRIBBLE, None)

        # Pod presją – szukamy kogoś do przodu
        target = pick_pass_target(state, carrier)
        if target is not None:
            return (AiDecision.PASS, target)

        return (AiDecision.CONTINUE_DRIBBLE, None)  # brak opcji → dryblinguj

    # ── MID: pass-forward > shoot > dribble ──────────────────────────────
    if role == "MID":
        if not under_press:
            target = pick_pass_target(state, carrier)
            if target is not None:
                return (AiDecision.PASS, target)

        if goal_dist <= shot_range:
            return (AiDecision.SHOOT, None)

        if under_press:
            target = pick_pass_target(state, carrier)
            if target is not None:
                return (AiDecision.PASS, target)

        return (AiDecision.CONTINUE_DRIBBLE, None)

    # ── DEF / GK: pass-forward > dribble ─────────────────────────────────
    # (DEF_SHOT_RANGE = 0 → DEF/GK praktycznie nigdy nie strzelają)
    target = pick_pass_target(state, carrier)
    if target is not None:
        return (AiDecision.PASS, target)

    return (AiDecision.CONTINUE_DRIBBLE, None)