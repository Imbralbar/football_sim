"""Testy modułu core/ai (pressing, fazy, markowanie)."""
from __future__ import annotations
import config as C
from core.field import Field, Cell
from core.entities import Role, Side, Player, Team
from core.ball import Ball
from core.state import GameState
from core.ai import update_phases, select_pressers, compute_dynamic_home
from core.ai.decision import decide_action, AiDecision


def _mk_team(side: Side, color: str) -> Team:
    field = Field()
    gk = Player(1, Role.GK, field.goal_center(side.value), side)
    d1 = Player(2, Role.DEF, Cell(4, 5), side)
    m1 = Player(6, Role.MID, Cell(10, 8), side)
    f1 = Player(10, Role.FWD, Cell(20, 8), side)
    return Team(name=f"T-{color}", side=side, color_key=color,
                players=[gk, d1, m1, f1])


def _mk_state() -> GameState:
    field = Field()
    home = _mk_team(Side.LEFT, "A")
    away = _mk_team(Side.RIGHT, "B")
    ball = Ball()
    ball.give_to(home.by_number(10))
    return GameState(field=field, home=home, away=away, ball=ball)


def test_update_phases_sets_attack_and_defense():
    state = _mk_state()
    update_phases(state)
    assert all(p.phase == C.PHASE_ATTACK for p in state.home.players)
    assert all(p.phase == C.PHASE_DEFENSE for p in state.away.players)


def test_select_pressers_respects_count_param():
    state = _mk_state()
    ball_cell = state.ball.carrier.pos
    pressers = select_pressers(state, state.away, ball_cell)
    assert len(pressers) <= C.PRESSERS_COUNT


def test_select_pressers_respects_trigger_distance():
    state = _mk_state()
    far_cell = Cell(0, 0)
    # przesuwamy "piłkę" logicznie daleko od wszystkich obrońców
    pressers = select_pressers(state, state.away, far_cell)
    for p in state.away.outfield():
        if id(p) in pressers:
            assert state.field.distance(p.pos, far_cell) <= C.PRESS_TRIGGER_DIST


def test_compute_dynamic_home_shifts_forward_when_attacking():
    state = _mk_state()
    update_phases(state)
    defender = state.home.by_number(2)
    new_home = compute_dynamic_home(defender, state.field, state.home)
    assert new_home.x > defender.home.x  # LEFT atakuje w prawo -> home przesunięty w +x


def test_decide_action_in_penalty_always_shoots():
    state = _mk_state()
    carrier = state.home.by_number(10)
    carrier.pos = Cell(1, state.field.center.y)  # w polu karnym przeciwnika (RIGHT broni prawej)
    decision, target = decide_action(state, carrier)
    # UWAGA: w tym mini-teście carrier jest LEFT, pole karne przeciwnika to prawa strona,
    # dla pełnej poprawności testu ustaw carrier.pos blisko bramki RIGHT
    carrier.pos = Cell(state.field.w - 2, state.field.center.y)
    decision, target = decide_action(state, carrier)
    assert decision == AiDecision.SHOOT