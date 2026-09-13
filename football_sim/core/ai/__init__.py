"""
core/ai – pakiet AI drużynowego.

Publiczne API (zachowane 1:1 dla core/match.py):
    decide_action(state, carrier) -> tuple[AiDecision, Player | None]
    AiDecision

Submoduły:
    decision.py    – decyzja carriery: SHOOT / PASS / CONTINUE_DRIBBLE
    positioning.py – fazy gry, dynamiczna linia obrony, markowanie
    pressing.py    – wybór aktywnych presserów
    styles.py      – hak na unikalne style zawodników (etap 2, obecnie no-op)
"""
from __future__ import annotations

from core.ai.decision import (
    AiDecision,
    decide_action,
    pick_pass_target,
    is_under_pressure,
)
from core.ai.positioning import (
    update_phases,
    assign_marking,
    compute_dynamic_home,
    formation_target,
)
from core.ai.pressing import select_pressers

__all__ = [
    "AiDecision", "decide_action", "pick_pass_target", "is_under_pressure",
    "update_phases", "assign_marking", "compute_dynamic_home", "formation_target",
    "select_pressers",
]