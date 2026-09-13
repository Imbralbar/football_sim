"""
core/ai/positioning.py – fazy gry, dynamiczna linia obrony, markowanie.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

import config as C
from core.field import Field, Cell
from core import movement as mv

if TYPE_CHECKING:
    from core.state import GameState
    from core.entities import Team, Player


def _team_phase(state: "GameState", team: "Team") -> str:
    carrier = state.ball.carrier
    if carrier is None:
        return C.PHASE_NEUTRAL
    return C.PHASE_ATTACK if carrier in team.players else C.PHASE_DEFENSE


def update_phases(state: "GameState") -> None:
    """Ustawia player.phase dla obu drużyn wg tego, kto ma piłkę."""
    for team in state.teams:
        phase = _team_phase(state, team)
        for p in team.players:
            p.phase = phase


def _line_mult(team: "Team") -> float:
    level = team.style.get("defensive_line", "MEDIUM")
    return C.DEF_LINE_MULT.get(level, 1.0)


def compute_dynamic_home(p: "Player", field: Field, team: "Team") -> Cell:
    """Przesuwa bazową pozycję (home) wzdłuż osi ataku wg fazy gry drużyny (oś głębokości)."""
    if p.is_gk or p.home is None:
        return p.home if p.home is not None else p.pos

    if p.role.value == "FWD":
        return p.home
    if p.role.value == "MID" and not C.MID_TRACKBACK:
        return p.home

    mult = _line_mult(team)
    direction = 1 if p.side.value == "LEFT" else -1

    if p.phase == C.PHASE_ATTACK:
        shift = int(C.DEF_LINE_PUSH_ATTACK * mult)
    elif p.phase == C.PHASE_DEFENSE:
        shift = -int(C.DEF_LINE_DROP_DEFENSE * mult)
    else:
        shift = 0

    return field.clamp(Cell(p.home.x + direction * shift, p.home.y))


def assign_marking(state: "GameState") -> None:
    """Przypisuje DEF (i MID jeśli MID_TRACKBACK) broniącej drużyny do najbliższego niekrytego przeciwnika."""
    for team in state.teams:
        for p in team.players:
            p.marking_target = None

    carrier = state.ball.carrier

    for team in state.teams:
        if _team_phase(state, team) != C.PHASE_DEFENSE:
            continue

        opponents = state.away if team is state.home else state.home
        opp_pool  = [o for o in opponents.outfield() if o is not carrier]

        marker_roles = ("DEF", "MID") if C.MID_TRACKBACK else ("DEF",)
        markers = [p for p in team.outfield() if p.role.value in marker_roles]

        used_ids: set[int] = set()
        for p in sorted(markers, key=lambda m: m.pos.x,
                         reverse=(team.side.value == "RIGHT")):
            best, best_d = None, None
            for o in opp_pool:
                if id(o) in used_ids:
                    continue
                d = Field.distance(p.pos, o.pos)
                if d > C.MARKING_RADIUS:
                    continue
                if best_d is None or d < best_d:
                    best, best_d = o, d
            if best is not None:
                p.marking_target = best
                used_ids.add(id(best))


def formation_target(p: "Player", ball_cell: Cell, field: Field, chase: bool) -> Cell:
    """Wrapper zgodny z dawnym movement.formation_target — dokłada cień markowania."""
    mark_cell = p.marking_target.pos if p.marking_target is not None else None
    return mv.formation_target(p, ball_cell, field, chase=chase, mark_cell=mark_cell)