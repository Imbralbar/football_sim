"""
core/ai/styles.py – hak rozszerzeń pod unikalne style zawodników (etap 2).

Obecnie no-op. W przyszłości: carrier.style == "POACHER" -> preferuj SHOOT,
"PLAYMAKER" -> preferuj PASS, itp. — bez ruszania decision.py.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.entities import Player
    from core.ai.decision import AiDecision


def apply_style(carrier: "Player", decision: "AiDecision", target: "Player | None"):
    """Punkt rozszerzenia — obecnie zwraca decyzję bez zmian."""
    return decision, target