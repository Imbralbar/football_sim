"""Testy orkiestratora meczu (core/match.py).

Podmieniane sa wylacznie zaleznosci rozstrzygajace (ai, rules, resolver)
oraz GameState. Encje, formacja, EventLog i Rng sa prawdziwe.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

import core.match as M
import config as C
from core.match import Match, MatchPhase
from core.actions import AttackAction, DefenceAction
from core.ai import AiDecision
from core.dice import Rng
from core.entities import Role, Side
from core.events import EventType
from core.field import Cell
from core.formation import build_442


# ---------------------------------------------------------------------------
# Atrapy infrastruktury
# ---------------------------------------------------------------------------

class FakeField:
    """Minimalne boisko - tyle, ile potrzebuje build_442 i formation.kickoff."""

    def __init__(self, w: int = C.FIELD_W, h: int = C.FIELD_H):
        self.w = w
        self.h = h

    @property
    def center(self) -> Cell:
        return Cell(self.w // 2, self.h // 2)

    def goal_center(self, side_value: str) -> Cell:
        x = 0 if side_value == "LEFT" else self.w - 1
        return Cell(x, self.h // 2)


class FakeState:
    """GameState z zegarem identycznym jak oryginal, ale bez ruchu i kontaktow.

    Ruch zawodnikow nie jest testowany tutaj (to domena test_movement.py) -
    liczy sie sam zegar, bo od niego zalezy takt decyzji AI.
    """

    def __init__(self, field, home, away, ball, tick=0, action_no=1, log=None):
        self.field = field
        self.home = home
        self.away = away
        self.ball = ball
        self.tick = tick
        self.action_no = action_no
        self.log = log if log is not None else []
        self.duel_queue: list = []
        self.total_ticks = 0

    @property
    def teams(self):
        return [self.home, self.away]

    def step_tick(self) -> None:
        self.total_ticks += 1
        self.tick += 1
        if self.tick >= C.TICKS_PER_ACTION:
            self.tick = 0
            self.action_no += 1

    def pending_duel(self):
        return self.duel_queue.pop(0) if self.duel_queue else None

    def team_of(self, p):
        return self.home if p in self.home.players else self.away

    def opponents_of(self, p):
        return self.away if p in self.home.players else self.home


@dataclass
class FakeDuelResult:
    """Odpowiednik resolver.DuelResult - musi byc dataclass (asdict w evencie)."""

    outcome: str
    attacker_wins: bool
    was_tie: bool = False
    attacker_total: int = 0
    defender_total: int = 0
    attack_stat: int = 0
    defence_stat: int = 0


class FakeOutcome:
    """Wspolna atrapa PassOutcome / ShotOutcome."""

    def __init__(self, result: str, interceptor=None, target=None, goalkeeper=None):
        self.result = result
        self.interceptor = interceptor
        self.target = target
        self.goalkeeper = goalkeeper


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def field():
    return FakeField()


@pytest.fixture
def teams(field):
    home = build_442(field, "Blues", Side.LEFT, "A")
    away = build_442(field, "Blacks", Side.RIGHT, "B")
    return home, away


@pytest.fixture
def wire(monkeypatch, field, teams):
    """Podmienia zaleznosci core.match i zwraca gotowy Match + jego state."""
    home, away = teams

    def _wire(decision=(AiDecision.CONTINUE_DRIBBLE, None),
              pass_outcome=None,
              shot_outcome=None,
              duel_result=None,
              goal=(False, None),
              extra_time=True):
        monkeypatch.setattr(M, "GameState", FakeState)
        monkeypatch.setattr(
            M, "decide_action",
            decision if callable(decision) else (lambda s, c: decision))
        monkeypatch.setattr(
            M, "resolve_pass",
            pass_outcome if callable(pass_outcome)
            else (lambda s, p, t, r: pass_outcome
                  or FakeOutcome("COMPLETE", target=t)))
        monkeypatch.setattr(
            M, "resolve_shot",
            shot_outcome if callable(shot_outcome)
            else (lambda s, sh, r: shot_outcome
                  or FakeOutcome("SAVED", goalkeeper=s.opponents_of(sh).gk())))
        monkeypatch.setattr(
            M, "resolve_ground_duel",
            duel_result if callable(duel_result)
            else (lambda rng, a, d, av, dv: duel_result
                  or FakeDuelResult("BEAT_DEFENDER", attacker_wins=True)))
        monkeypatch.setattr(M, "is_goal", goal if callable(goal) else (lambda s: goal))

        match = Match(home, away, field, Rng(7), enable_extra_time=extra_time)
        return match

    return _wire


def _start(match: Match, action_no: int = 1) -> FakeState:
    """Inicjalizuje stan bez rozgrywania meczu (do testow jednostkowych)."""
    match._setup_kickoff(match.home, action_no=action_no)
    return match.state


# ---------------------------------------------------------------------------
# 1-3: przebieg meczu
# ---------------------------------------------------------------------------

def test_goalless_match_ends_after_90_actions(wire):
    """1. Mecz bez goli, bez dogrywki -> 0:0, remis, 90 akcji."""
    match = wire(extra_time=False)
    result = match.play()

    assert (result.home_score, result.away_score) == (0, 0)
    assert result.winner is None
    assert result.total_actions == 90
    assert result.phase_ended is MatchPhase.SECOND_HALF
    # Zegar: 90 akcji x 36 tickow
    assert result.final_state.total_ticks == 90 * C.TICKS_PER_ACTION
    assert result.final_state.action_no == 91


def test_single_goal_gives_home_the_win(wire):
    """2. Jeden gol gospodarzy -> 1:0, winner='home'."""
    scored = {"done": False}

    def decision(state, carrier):
        if not scored["done"] and state.team_of(carrier) is state.home:
            return AiDecision.SHOOT, None
        return AiDecision.CONTINUE_DRIBBLE, None

    def shot(state, shooter, rng):
        scored["done"] = True
        return FakeOutcome("GOAL", goalkeeper=state.opponents_of(shooter).gk())

    match = wire(decision=decision, shot_outcome=shot)
    result = match.play()

    assert (result.home_score, result.away_score) == (1, 0)
    assert result.winner == "home"
    assert result.total_actions == 90
    goals = result.events.goals()
    assert len(goals) == 1
    assert goals[0].team == "Blues"


def test_draw_after_90_triggers_extra_time(wire):
    """3. Remis po 90' + enable_extra_time -> 120 akcji, dalej remis."""
    match = wire(extra_time=True)
    result = match.play()

    assert result.total_actions == 120
    assert result.phase_ended is MatchPhase.EXTRA_SECOND
    assert result.winner is None
    assert result.final_state.total_ticks == 120 * C.TICKS_PER_ACTION


def test_goal_resumes_from_kickoff_without_breaking_clock(wire):
    """Gol w srodku akcji nie rozjezdza zegara - akcja dobiega do konca."""
    fired = {"n": 0}

    def decision(state, carrier):
        if fired["n"] == 0 and state.team_of(carrier) is state.home:
            return AiDecision.SHOOT, None
        return AiDecision.CONTINUE_DRIBBLE, None

    def shot(state, shooter, rng):
        fired["n"] += 1
        return FakeOutcome("GOAL", goalkeeper=state.opponents_of(shooter).gk())

    match = wire(decision=decision, shot_outcome=shot, extra_time=False)
    result = match.play()

    assert result.total_actions == 90
    assert result.final_state.total_ticks == 90 * C.TICKS_PER_ACTION
    # Po golu pilke wznawia druzyna, ktora stracila
    assert fired["n"] == 1


# ---------------------------------------------------------------------------
# 4: starcia
# ---------------------------------------------------------------------------

def test_duel_lost_by_carrier_transfers_ball(wire, teams):
    """4. pending_duel() -> _handle_duel() -> obronca przejmuje pilke."""
    home, away = teams
    match = wire(duel_result=FakeDuelResult("TACKLED", attacker_wins=False))
    state = _start(match, action_no=7)

    carrier = state.ball.carrier          # #10 druzyny Blues
    defender = away.by_number(2)          # DEF
    defender.contact_ticks = C.DUEL_CONTACT_TICKS
    state.duel_queue = [defender]

    match._play_action()

    assert state.ball.carrier is defender
    assert defender.contact_ticks == 0
    duels = match.events.by_type(EventType.DUEL)
    assert len(duels) == 1
    assert duels[0].player == carrier.number
    assert duels[0].target == defender.number
    assert duels[0].duel["attacker_wins"] is False


def test_duel_won_by_carrier_grants_protection(wire, teams):
    """4b. Wygrane starcie -> carrier zachowuje pilke i dostaje ochrone."""
    home, away = teams
    match = wire(duel_result=FakeDuelResult("BEAT_DEFENDER", attacker_wins=True))
    state = _start(match, action_no=12)

    carrier = state.ball.carrier
    defender = away.by_number(3)

    match._handle_duel(defender)

    assert state.ball.carrier is carrier
    assert carrier.protected_until == 12 + C.PROTECTION_ACTIONS
    assert carrier.is_protected(13) is True
    assert carrier.is_protected(15) is False
    assert match.events.by_type(EventType.DUEL)[0].duel["attacker_wins"] is True


def test_defence_action_for_defender_is_vs_dribble(wire, teams):
    """Obronca zawsze wybiera VS_DRIBBLE (bez zuzycia rzutu k10)."""
    home, away = teams
    match = wire()
    _start(match)
    before = match.rng.rolls_made

    assert match._pick_defence_action(away.by_number(2)) is DefenceAction.VS_DRIBBLE
    assert match.rng.rolls_made == before  # DEF nie losuje


def test_goalkeeper_carrier_never_enters_duel(wire, teams):
    """GK z pilka nie wchodzi w starcie - attack_stat() rzucilby ValueError."""
    home, away = teams
    match = wire(duel_result=FakeDuelResult("TACKLED", attacker_wins=False))
    state = _start(match)

    state.ball.give_to(home.gk())
    match._handle_duel(away.by_number(9))

    assert state.ball.carrier is home.gk()
    assert match.events.by_type(EventType.DUEL) == []


# ---------------------------------------------------------------------------
# 5-8: decyzje AI, podania, strzaly
# ---------------------------------------------------------------------------

def test_ai_pass_completes_and_logs(wire, teams):
    """5. Decyzja PASS -> resolve_pass() -> event PASS + zmiana posiadacza."""
    home, _ = teams
    passer, target = home.by_number(10), home.by_number(11)
    calls = []

    def resolve(state, p, t, rng):
        calls.append((p.number, t.number))
        return FakeOutcome("COMPLETE", target=t)

    match = wire(decision=(AiDecision.PASS, target), pass_outcome=resolve)
    state = _start(match, action_no=3)
    state.ball.give_to(passer)

    match._handle_ai_decision(passer)

    assert calls == [(10, 11)]
    assert state.ball.carrier is target
    assert match.last_passer is passer
    ev = match.events.by_type(EventType.PASS)[0]
    assert (ev.player, ev.target, ev.note) == (10, 11, "COMPLETE")


def test_intercepted_pass_gives_ball_to_interceptor(wire, teams):
    """8. Podanie przechwycone -> interceptor ma pilke, asysta skasowana."""
    home, away = teams
    passer, target, thief = home.by_number(10), home.by_number(11), away.by_number(4)

    match = wire(
        decision=(AiDecision.PASS, target),
        pass_outcome=FakeOutcome("INTERCEPTED", interceptor=thief, target=target),
    )
    state = _start(match, action_no=4)
    state.ball.give_to(passer)
    match.last_passer = home.by_number(8)

    match._handle_ai_decision(passer)

    assert state.ball.carrier is thief
    assert match.last_passer is None
    assert match.events.by_type(EventType.PASS)[0].note == "INTERCEPTED"
    assert match.events.by_type(EventType.TURNOVER)[0].player == thief.number


def test_shot_goal_updates_score_and_records_assist(wire, teams):
    """6. SHOOT + GOAL -> wynik, event GOAL z asysta, wznowienie przez gosci."""
    home, away = teams
    passer, shooter = home.by_number(8), home.by_number(10)

    match = wire(
        decision=(AiDecision.SHOOT, None),
        shot_outcome=FakeOutcome("GOAL", goalkeeper=away.gk()),
    )
    state = _start(match, action_no=33)
    state.ball.give_to(shooter)
    match.last_passer = passer

    match._handle_ai_decision(shooter)

    assert (match.home_score, match.away_score) == (1, 0)
    goal = match.events.goals()[0]
    assert goal.player == shooter.number
    assert goal.target == passer.number      # asysta
    assert goal.note == "1-0"
    assert match.last_passer is None
    # Wznowienie: pilka u druzyny, ktora stracila gola
    assert state.ball.carrier is away.by_number(10)


def test_saved_shot_gives_ball_to_goalkeeper(wire, teams):
    """7. Strzal obroniony -> bramkarz ma pilke, wynik bez zmian."""
    home, away = teams
    shooter = home.by_number(10)

    match = wire(
        decision=(AiDecision.SHOOT, None),
        shot_outcome=FakeOutcome("SAVED", goalkeeper=away.gk()),
    )
    state = _start(match, action_no=20)
    state.ball.give_to(shooter)

    match._handle_ai_decision(shooter)

    assert state.ball.carrier is away.gk()
    assert (match.home_score, match.away_score) == (0, 0)
    assert match.events.by_type(EventType.SHOT)[0].note == "SAVED"
    assert len(match.events.by_type(EventType.SAVE)) == 1


def test_continue_dribble_changes_nothing(wire, teams):
    """5b. CONTINUE_DRIBBLE nie generuje zdarzen ani nie zmienia posiadacza."""
    home, _ = teams
    match = wire(decision=(AiDecision.CONTINUE_DRIBBLE, None))
    state = _start(match)
    carrier = state.ball.carrier
    before = len(match.events.events)

    match._handle_ai_decision(carrier)

    assert state.ball.carrier is carrier
    assert len(match.events.events) == before


def test_geometric_goal_credited_to_opposite_team(wire):
    """is_goal() zwraca strone, ktora STRACILA -> punkt dla przeciwnika."""
    match = wire(goal=lambda s: (True, "LEFT"))
    _start(match)

    match._play_action()

    assert match.home_score == 0
    assert match.away_score >= 1  # Blues (LEFT) stracil


def test_ai_is_consulted_only_on_carrier_move_ticks(wire):
    """Decyzja AI zapada dokladnie 12 razy na akcje (co C.CARRIER_MOVE_EVERY)."""
    calls = {"n": 0}

    def decision(state, carrier):
        calls["n"] += 1
        return AiDecision.CONTINUE_DRIBBLE, None

    match = wire(decision=decision)
    _start(match)
    match._play_action()

    assert calls["n"] == C.TICKS_PER_ACTION // C.CARRIER_MOVE_EVERY  # 12


# ---------------------------------------------------------------------------
# 9-10: determinizm i serializacja
# ---------------------------------------------------------------------------

def _stochastic_match(monkeypatch, seed: int) -> tuple:
    """Mecz sterowany wylacznie przez Rng(seed) - do testu determinizmu."""
    field = FakeField()
    home = build_442(field, "Blues", Side.LEFT, "A")
    away = build_442(field, "Blacks", Side.RIGHT, "B")
    rng = Rng(seed)

    monkeypatch.setattr(M, "GameState", FakeState)
    monkeypatch.setattr(M, "is_goal", lambda s: (False, None))
    monkeypatch.setattr(
        M, "resolve_ground_duel",
        lambda r, a, d, av, dv: FakeDuelResult("DUEL", attacker_wins=r.roll() > 4))

    def decision(state, carrier):
        roll = rng.roll()
        if roll >= 9 and not carrier.is_gk:
            return AiDecision.SHOOT, None
        if roll >= 6:
            mates = [p for p in state.team_of(carrier).outfield() if p is not carrier]
            return AiDecision.PASS, mates[roll % len(mates)]
        return AiDecision.CONTINUE_DRIBBLE, None

    def pass_fn(state, p, t, r):
        if r.roll() > 3:
            return FakeOutcome("COMPLETE", target=t)
        return FakeOutcome("INTERCEPTED",
                           interceptor=state.opponents_of(p).by_number(4), target=t)

    def shot_fn(state, sh, r):
        keeper = state.opponents_of(sh).gk()
        name = "GOAL" if r.roll() >= 9 else "SAVED"
        return FakeOutcome(name, goalkeeper=keeper)

    monkeypatch.setattr(M, "decide_action", decision)
    monkeypatch.setattr(M, "resolve_pass", pass_fn)
    monkeypatch.setattr(M, "resolve_shot", shot_fn)

    result = Match(home, away, field, rng).play()
    return (result.home_score, result.away_score, result.winner,
            result.total_actions, result.events.to_json())


def test_same_seed_produces_identical_match(monkeypatch):
    """9. Rng(42) x 2 mecze -> identyczny wynik i identyczny EventLog."""
    first = _stochastic_match(monkeypatch, 42)
    second = _stochastic_match(monkeypatch, 42)
    assert first == second


def test_different_seeds_diverge(monkeypatch):
    """9b. Rozne seedy powinny dac rozny przebieg (sanity check RNG)."""
    a = _stochastic_match(monkeypatch, 42)
    b = _stochastic_match(monkeypatch, 1337)
    assert a[4] != b[4]  # rozne logi zdarzen


def test_event_log_to_json_is_valid(monkeypatch):
    """10. EventLog.to_json() po meczu -> poprawny JSON bez surowych Enumow."""
    *_, payload = _stochastic_match(monkeypatch, 2024)
    events = json.loads(payload)

    assert isinstance(events, list) and events
    for ev in events:
        assert isinstance(ev["etype"], str)
        assert isinstance(ev["action_no"], int)
        if ev.get("duel") is not None:
            for value in ev["duel"].values():
                assert isinstance(value, (str, int, bool, type(None)))
    assert any(ev["etype"] == EventType.KICKOFF.value for ev in events)
    assert any(ev["etype"] == EventType.FULLTIME.value for ev in events)