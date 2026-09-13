from __future__ import annotations

import json
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from core.field import Field, Cell
from core.entities import Player, Team, Role, Side
from core.ball import Ball
from core.state import GameState
from core.events import EventLog, MatchEvent, EventType
from core.match import MatchResult, MatchPhase
from export.replay import (
    TickSnapshot,
    ReplayData,
    capture_tick,
    create_replay_data,
    export_replay,
    load_replay
)


@pytest.fixture
def field():
    """Fixture: boisko z domyslnymi wymiarami z config."""
    return Field()


@pytest.fixture
def team_left(field):
    """Fixture: druzyna po lewej stronie (11 zawodnikow)."""
    team = Team(name="Blues", side=Side.LEFT, color_key="A")
    for i in range(11):
        player = Player(
            number=i + 1,
            role=Role.FWD if i < 2 else Role.MID if i < 6 else Role.DEF if i < 10 else Role.GK,
            pos=Cell(x=5, y=8),
            side=Side.LEFT,
            stats={}
        )
        team.players.append(player)
    return team


@pytest.fixture
def team_right(field):
    """Fixture: druzyna po prawej stronie (11 zawodnikow)."""
    team = Team(name="Blacks", side=Side.RIGHT, color_key="B")
    for i in range(11):
        player = Player(
            number=i + 1,
            role=Role.FWD if i < 2 else Role.MID if i < 6 else Role.DEF if i < 10 else Role.GK,
            pos=Cell(x=19, y=8),
            side=Side.RIGHT,
            stats={}
        )
        team.players.append(player)
    return team


@pytest.fixture
def game_state(field, team_left, team_right):
    """Fixture: stan gry z pilka przy lewej druzynie."""
    ball = Ball(carrier=team_left.players[0], free_pos=None)
    state = GameState(
        field=field,
        home=team_left,
        away=team_right,
        ball=ball,
        tick=0,
        action_no=1
    )
    return state


# TEST 1: capture_tick() zwraca TickSnapshot z 22 zawodnikami
def test_capture_tick_returns_22_players(game_state):
    """Test: capture_tick() tworzy snapshot z 22 zawodnikami."""
    snapshot = capture_tick(game_state)

    assert isinstance(snapshot, TickSnapshot)
    assert len(snapshot.players) == 22
    assert snapshot.action == 1
    assert snapshot.tick == 0


# TEST 2: capture_tick() gdy ball.carrier != None -> ball_carrier_number poprawny
def test_capture_tick_with_carrier(game_state):
    """Test: snapshot zawiera numer nosiciela pilki."""
    snapshot = capture_tick(game_state)

    assert snapshot.ball_carrier_number == game_state.ball.carrier.number
    assert snapshot.ball_carrier_side == game_state.ball.carrier.side.value


# TEST 3: capture_tick() gdy ball.is_free -> ball_carrier_number == None
def test_capture_tick_free_ball(game_state):
    """Test: snapshot z wolna pilka ma ball_carrier_number == None."""
    game_state.ball.carrier = None
    game_state.ball.free_pos = Cell(x=12, y=8)
    snapshot = capture_tick(game_state)

    assert snapshot.ball_carrier_number is None
    assert snapshot.ball_carrier_side is None


# TEST 4: create_replay_data() zwraca ReplayData z poprawnymi metadanymi
def test_create_replay_data(game_state, team_left, team_right):
    """Test: create_replay_data() buduje ReplayData z poprawnym home/away."""
    tick_history = [capture_tick(game_state)]

    events = EventLog()
    match_result = MatchResult(
        home_score=2,
        away_score=1,
        winner="home",
        phase_ended=MatchPhase.FINISHED,
        events=events,
        final_state=game_state,
        total_actions=90
    )

    replay = create_replay_data(match_result, tick_history, rng_seed=42)

    assert isinstance(replay, ReplayData)
    assert replay.home_name == "Blues"
    assert replay.away_name == "Blacks"
    assert replay.final_score_home == 2
    assert replay.final_score_away == 1
    assert replay.winner == "home"
    assert replay.total_actions == 90
    assert replay.rng_seed == 42


# TEST 5: export_replay() tworzy plik .json
def test_export_replay_creates_file(game_state, team_left, team_right):
    """Test: export_replay() zapisuje plik JSON."""
    tick_history = [capture_tick(game_state)]
    events = EventLog()
    match_result = MatchResult(
        home_score=2,
        away_score=1,
        winner="home",
        phase_ended=MatchPhase.FINISHED,
        events=events,
        final_state=game_state,
        total_actions=90
    )

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "test_replay.json"
        export_replay(match_result, tick_history, 42, output_path)

        assert output_path.exists()
        assert output_path.stat().st_size > 0


# TEST 6: export_replay() -> load_replay() -> identyczne dane (round-trip)
def test_round_trip_export_load(game_state, team_left, team_right):
    """Test: export + load zachowuje dane bez zmian."""
    tick_history = [capture_tick(game_state)]
    events = EventLog()
    match_result = MatchResult(
        home_score=2,
        away_score=1,
        winner="home",
        phase_ended=MatchPhase.FINISHED,
        events=events,
        final_state=game_state,
        total_actions=90
    )

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "test_round_trip.json"

        # Export
        export_replay(match_result, tick_history, 42, output_path)

        # Load
        loaded_replay = load_replay(output_path)

        # Weryfikacja
        assert loaded_replay.home_name == "Blues"
        assert loaded_replay.away_name == "Blacks"
        assert loaded_replay.final_score_home == 2
        assert loaded_replay.final_score_away == 1
        assert loaded_replay.winner == "home"
        assert loaded_replay.rng_seed == 42
        assert len(loaded_replay.ticks) == len(tick_history)


# TEST 7: JSON ma poprawna strukture
def test_json_structure_valid(game_state, team_left, team_right):
    """Test: JSON spelnia strukture i jest parseable."""
    tick_history = [capture_tick(game_state)]
    events = EventLog()
    match_result = MatchResult(
        home_score=1,
        away_score=0,
        winner="home",
        phase_ended=MatchPhase.FINISHED,
        events=events,
        final_state=game_state,
        total_actions=90
    )

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "test_json_structure.json"
        export_replay(match_result, tick_history, 42, output_path)

        # Sparsuj JSON
        with open(output_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Sprawdz klucze
        assert "home_name" in data
        assert "away_name" in data
        assert "final_score_home" in data
        assert "final_score_away" in data
        assert "winner" in data
        assert "total_actions" in data
        assert "rng_seed" in data
        assert "ticks" in data
        assert "events" in data
        assert "final_players" in data


# TEST 8: ticks[0] ma action=1, tick=0
def test_first_tick_has_correct_action_and_tick(game_state):
    """Test: pierwszy snapshot ma action=1, tick=0."""
    game_state.action_no = 1
    game_state.tick = 0
    snapshot = capture_tick(game_state)

    assert snapshot.action == 1
    assert snapshot.tick == 0


# TEST 9: len(ticks) == total_actions * 36
def test_tick_history_length(game_state, team_left, team_right):
    """Test: liczba tickow odpowiada liczbie akcji (90 akcji * 36 tickow)."""
    # Symuluj 3 akcje (x 36 tickow) = 108 tickow
    tick_history = []
    for action in range(1, 4):  # akcje 1, 2, 3
        for t in range(36):
            game_state.action_no = action
            game_state.tick = t
            tick_history.append(capture_tick(game_state))

    events = EventLog()
    match_result = MatchResult(
        home_score=0,
        away_score=0,
        winner=None,
        phase_ended=MatchPhase.FINISHED,
        events=events,
        final_state=game_state,
        total_actions=3
    )

    replay = create_replay_data(match_result, tick_history, 42)

    assert len(replay.ticks) == 3 * 36
    assert len(replay.ticks) == replay.total_actions * 36


# TEST 10: events lista zawiera eventy z EventLog
def test_events_list_from_eventlog(game_state, team_left, team_right):
    """Test: replay zawiera eventy z EventLog."""
    tick_history = [capture_tick(game_state)]

    # Stwórz EventLog z jednym zdarzeniem (gol)
    events = EventLog()
    event = MatchEvent(
        action_no=23,
        tick=15,
        etype=EventType.GOAL,
        team="Blues",
        player=10,
        target=None,
        from_cell=None,
        to_cell=None,
        duel=None,
        note="Gol!"
    )
    events.events.append(event)

    match_result = MatchResult(
        home_score=1,
        away_score=0,
        winner=None,
        phase_ended=MatchPhase.FINISHED,
        events=events,
        final_state=game_state,
        total_actions=23
    )

    replay = create_replay_data(match_result, tick_history, 42)

    assert len(replay.events) == 1
    assert replay.events[0]["etype"] == "GOAL"
    assert replay.events[0]["action_no"] == 23


# DODATKOWY TEST: load_replay() rzuca FileNotFoundError dla nieistniejacego pliku
def test_load_replay_file_not_found():
    """Test: load_replay() rzuca FileNotFoundError dla brakujacego pliku."""
    with pytest.raises(FileNotFoundError):
        load_replay("/nieistniejaca/sciezka/replay.json")


# DODATKOWY TEST: sprawdz, ze wszystkie zawodniki maja poprawne pola
def test_players_have_required_fields(game_state):
    """Test: kazdy zawodnik w snapshot ma number, x, y, side, role."""
    snapshot = capture_tick(game_state)

    for player in snapshot.players:
        assert "number" in player
        assert "x" in player
        assert "y" in player
        assert "side" in player
        assert "role" in player
        assert player["side"] in ["LEFT", "RIGHT"]
        assert player["role"] in ["GK", "DEF", "MID", "FWD"]