"""
core/ai/decision.py – decyzja carriery: co zrobić z piłką.

Filozofia wg roli (bez zmian względem v0.4.1):
  FWD : shoot (szeroki zasięg) > dribble > pass (tylko pod presją)
  MID : pass-forward > shoot > dribble
  DEF : pass-forward > dribble  ← nigdy nie blokuje gry
  GK  : pass-forward > dribble
"""
from __future__ import annotations
from typing import TYPE_CHECKING
from enum import Enum

if TYPE_CHECKING:
    from core.state import GameState
    from core.entities import Player

import config as C
from core.ai import styles


class AiDecision(str, Enum):
    """Typ decyzji AI – co zrobić z piłką."""
    CONTINUE_DRIBBLE = "CONTINUE_DRIBBLE"
    PASS             = "PASS"
    SHOOT            = "SHOOT"


def _shot_range(role: str) -> int:
    """Zasięg strzału wg roli zawodnika."""
    return {
        "FWD": C.FWD_SHOT_RANGE,
        "MID": C.MID_SHOT_RANGE,
        "DEF": C.DEF_SHOT_RANGE,
        "GK":  C.DEF_SHOT_RANGE,
    }.get(role, C.DEF_SHOT_RANGE)


def is_under_pressure(state: "GameState", carrier: "Player", threshold: int) -> bool:
    """True jeśli jakikolwiek przeciwnik (nie bramkarz) jest ≤ threshold kratek od carriery."""
    for opp in state.opponents_of(carrier).outfield():
        if state.field.distance(carrier.pos, opp.pos) <= threshold:
            return True
    return False


def pick_pass_target(state: "GameState", carrier: "Player") -> "Player | None":
    """Wybiera najlepszego odbiorcę podania (logika z v0.4.1, bez zmian)."""
    opp_side     = carrier.side.opposite().value
    carrier_dist = state.field.distance_to_goal(carrier.pos, opp_side)
    carrier_role = carrier.role.value

    candidates = [p for p in state.team_of(carrier).outfield() if p != carrier]
    if not candidates:
        return None

    preferred: list[tuple] = []
    fallback: list[tuple] = []

    for p in candidates:
        p_dist = state.field.distance_to_goal(p.pos, opp_side)
        gain   = carrier_dist - p_dist

        if gain >= C.PASS_MIN_GAIN:
            same_role_penalty = (
                1 if (C.PASS_PENALIZE_SAME_ROLE and p.role.value == carrier_role) else 0
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
    return None


def decide_action(state: "GameState", carrier: "Player") -> tuple[AiDecision, "Player | None"]:
    """Decyduje, co zawodnik robi z piłką. Wywoływana RAZ na akcję (guard w match.py)."""
    role     = carrier.role.value
    opp_side = carrier.side.opposite().value

    in_penalty  = state.field.in_penalty_area(carrier.pos, opp_side)
    goal_dist   = state.field.distance_to_goal(carrier.pos, opp_side)
    under_press = is_under_pressure(state, carrier, C.THREAT_DISTANCE)
    shot_range  = _shot_range(role)

    decision: AiDecision
    target: "Player | None" = None

    if in_penalty:
        decision = AiDecision.SHOOT

    elif role == "FWD":
        if goal_dist <= shot_range:
            decision = AiDecision.SHOOT
        elif not under_press:
            decision = AiDecision.CONTINUE_DRIBBLE
        else:
            target = pick_pass_target(state, carrier)
            decision = AiDecision.PASS if target is not None else AiDecision.CONTINUE_DRIBBLE

    elif role == "MID":
        if not under_press:
            target = pick_pass_target(state, carrier)
        if target is not None:
            decision = AiDecision.PASS
        elif goal_dist <= shot_range:
            decision = AiDecision.SHOOT
        elif under_press:
            target = pick_pass_target(state, carrier)
            decision = AiDecision.PASS if target is not None else AiDecision.CONTINUE_DRIBBLE
        else:
            decision = AiDecision.CONTINUE_DRIBBLE

    else:  # DEF / GK
        target = pick_pass_target(state, carrier)
        decision = AiDecision.PASS if target is not None else AiDecision.CONTINUE_DRIBBLE

    # Punkt rozszerzenia na przyszłość (unikalne style zawodników, etap 2)
    decision, target = styles.apply_style(carrier, decision, target)
    return decision, target