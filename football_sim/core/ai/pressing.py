"""
core/ai/pressing.py – wybór aktywnych presserów (CHASERS).

CHASERS jest STAŁĄ (zawsze 2) — nie zależy od stylu drużyny.
Kandydaci są dodatkowo filtrowani wg roli, dystansu wyzwalającego
oraz karencji po duelu (frozen_until / defense_cooldown_until).
"""
from __future__ import annotations
from typing import TYPE_CHECKING

import config as C
from core.field import Field, Cell

if TYPE_CHECKING:
    from core.entities import Team


def select_pressers(state, defending: "Team", ball_cell: Cell) -> set[int]:
    """
    Wybiera do C.CHASERS zawodników drużyny broniącej, którzy biegną
    wprost na piłkę.

    Zasady:
    - Kandydaci: role z C.PRESS_ROLES (domyślnie DEF, MID), bez bramkarza.
    - Tylko w promieniu C.PRESS_TRIGGER_DIST od piłki.
    - Wykluczeni: zawodnicy w karencji (frozen_until, defense_cooldown_until).
    - Liczba = C.CHASERS (stała, zawsze 2).
    - Sortowanie po dystansie — najbliżsi pressują.
    """
    action_no = state.action_no
    candidates = [
        p for p in defending.outfield()
        if p.role.value in C.PRESS_ROLES
        and Field.distance(p.pos, ball_cell) <= C.PRESS_TRIGGER_DIST
        and p.frozen_until < action_no
        and p.defense_cooldown_until < action_no
    ]
    candidates.sort(key=lambda p: Field.distance(p.pos, ball_cell))
    return {id(p) for p in candidates[:C.CHASERS]}