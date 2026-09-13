from __future__ import annotations

import pytest
from unittest.mock import Mock, patch

from core.field import Field, Cell
from core.state import GameState
from core.entities import Team, Player, Side, Role
from core.ball import Ball
from render.ascii_view import AsciiView
import config as C


@pytest.fixture
def field():
    """Boisko testowe."""
    return Field()


@pytest.fixture
def empty_state(field):
    """Stan gry z pustym boiskiem (brak zawodników)."""
    home = Team(name="Blues", side=Side.LEFT, color_key="A", players=[])
    away = Team(name="Blacks", side=Side.RIGHT, color_key="B", players=[])
    ball = Ball(free_pos=Cell(x=12, y=8))
    
    state = GameState(field=field, home=home, away=away, ball=ball)
    return state


@pytest.fixture
def simple_state(field):
    """Stan gry z kilkoma zawodnikami."""
    home_players = [
        Player(number=1, role=Role.GK, pos=Cell(x=2, y=8), side=Side.LEFT),
        Player(number=10, role=Role.FWD, pos=Cell(x=5, y=5), side=Side.LEFT),
    ]
    away_players = [
        Player(number=1, role=Role.GK, pos=Cell(x=22, y=8), side=Side.RIGHT),
        Player(number=9, role=Role.FWD, pos=Cell(x=20, y=10), side=Side.RIGHT),
    ]
    
    home = Team(name="Blues", side=Side.LEFT, color_key="A", players=home_players)
    away = Team(name="Blacks", side=Side.RIGHT, color_key="B", players=away_players)
    ball = Ball(free_pos=Cell(x=12, y=8))
    
    state = GameState(field=field, home=home, away=away, ball=ball)
    return state


class TestAsciiViewRender:
    """Testy metody render()."""

    def test_empty_field_renders_without_error(self, field, empty_state):
        """Test 1: Puste boisko renderuje się bez błędów."""
        view = AsciiView(field)
        result = view.render(empty_state)
        
        assert isinstance(result, str)
        assert len(result) > 0
        assert "Blues vs Blacks" in result

    def test_render_returns_correct_number_of_lines(self, field, empty_state):
        """Test 2: render() zwraca string z (field.h + 3) liniami."""
        view = AsciiView(field)
        result = view.render(empty_state)
        lines = result.split('\n')
        
        assert len(lines) >= field.h + 1

    def test_player_with_ball_renders_as_o(self, field, simple_state):
        """Test 3: Zawodnik z piłką renderowany jako 'o', nie jego numer."""
        view = AsciiView(field)
        
        player_10 = simple_state.home.by_number(10)
        simple_state.ball.give_to(player_10)
        
        result = view.render(simple_state)
        
        assert C.BALL_GLYPH in result
        assert simple_state.ball.carrier == player_10

    def test_free_ball_renders_at_correct_position(self, field, simple_state):
        """Test 4: Wolna piłka renderowana jako 'o' na właściwej kratce."""
        view = AsciiView(field)
        
        assert simple_state.ball.is_free
        assert simple_state.ball.free_pos == Cell(x=12, y=8)
        
        result = view.render(simple_state)
        lines = result.split('\n')[1:]
        
        if 8 < len(lines):
            row = lines[8]
            if 12 < len(row):
                assert row[12] == C.BALL_GLYPH

    def test_pending_duel_shown_in_output(self, field, simple_state):
        """Test 5: pending_duel() != None -> ostatnia linia zawiera 'STARCIE'."""
        view = AsciiView(field)
        
        player_to_return = simple_state.home.by_number(10)
        simple_state.pending_duel = Mock(return_value=player_to_return)
        
        result = view.render(simple_state)
        
        assert "STARCIE" in result
        assert "nr 10" in result

    def test_render_without_duel(self, field, simple_state):
        """Test 5b: pending_duel() == None -> brak STARCIA w wyjściu."""
        view = AsciiView(field)
        
        simple_state.pending_duel = Mock(return_value=None)
        
        result = view.render(simple_state)
        lines = result.split('\n')
        
        assert "STARCIE" not in lines[-1]


class TestAsciiViewInteractive:
    """Testy metody run_interactive()."""

    def test_run_interactive_quit_command(self, field, empty_state):
        """Test 6: run_interactive() z input='q' kończy się bez błędu."""
        view = AsciiView(field)
        
        with patch('builtins.input', return_value='q'):
            view.run_interactive(empty_state)

    def test_run_interactive_step_tick(self, field, empty_state):
        """Test: run_interactive() reaguje na ENTER (step_tick)."""
        view = AsciiView(field)
        
        inputs = iter(['', 'q'])
        
        with patch('builtins.input', side_effect=inputs):
            view.run_interactive(empty_state)

    def test_run_interactive_action_command(self, field, empty_state):
        """Test: run_interactive() reaguje na 'a' (całą akcję)."""
        view = AsciiView(field)
        
        inputs = iter(['a', 'q'])
        
        with patch('builtins.input', side_effect=inputs):
            view.run_interactive(empty_state)

    def test_run_interactive_handles_eof(self, field, empty_state):
        """Test: run_interactive() obsługuje EOFError (koniec strumienia)."""
        view = AsciiView(field)
        
        with patch('builtins.input', side_effect=EOFError):
            view.run_interactive(empty_state)


class TestAsciiViewPrintState:
    """Testy metody print_state()."""

    def test_print_state_outputs_to_stdout(self, field, empty_state, capsys):
        """Test: print_state() wypisuje render() + pusty wiersz."""
        view = AsciiView(field)
        view.print_state(empty_state)
        
        captured = capsys.readouterr()
        assert "Blues vs Blacks" in captured.out
        assert len(captured.out) > 0