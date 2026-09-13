"""
Testy modulu M4 - zasady gry.

12 przypadkow testowych zgodnie z wymaganiami.
"""

from unittest.mock import Mock
import pytest

from core.rules import (
    resolve_pass,
    resolve_shot,
    is_goal,
    is_out_of_bounds,
    PassResult,
    ShotResult
)
from core.entities import Player, Team, Role, Side, Cell
from core.field import Field
from core.ball import Ball
from core.state import GameState


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_rng():
    """Mock generatora losowego."""
    return Mock()


@pytest.fixture
def field():
    """Standardowe boisko 25x17."""
    return Field(w=25, h=17)


@pytest.fixture
def home_team():
    """Druzyna LEFT z bramkarzem i zawodnikami."""
    gk = Player(
        number=1,
        role=Role.GK,
        pos=Cell(-1, 8),
        side=Side.LEFT,
        stats={'catch': 10, 'punch': 8, 'passing': 5, 'stamina': 100}
    )
    p2 = Player(
        number=2,
        role=Role.DEF,
        pos=Cell(5, 8),
        side=Side.LEFT,
        stats={'passing': 7, 'd_pass': 6, 'd_shot': 5, 'dribble': 6, 'shot': 7, 'stamina': 100}
    )
    p3 = Player(
        number=3,
        role=Role.MID,
        pos=Cell(10, 8),
        side=Side.LEFT,
        stats={'passing': 8, 'd_pass': 7, 'd_shot': 6, 'dribble': 7, 'shot': 8, 'stamina': 100}
    )
    return Team(
        name="Home Team",
        side=Side.LEFT,
        color_key="A",
        players=[gk, p2, p3]
    )


@pytest.fixture
def away_team():
    """Druzyna RIGHT z bramkarzem i zawodnikami."""
    gk = Player(
        number=1,
        role=Role.GK,
        pos=Cell(25, 8),
        side=Side.RIGHT,
        stats={'catch': 10, 'punch': 8, 'passing': 5, 'stamina': 100}
    )
    p2 = Player(
        number=2,
        role=Role.DEF,
        pos=Cell(20, 8),
        side=Side.RIGHT,
        stats={'passing': 7, 'd_pass': 6, 'd_shot': 5, 'dribble': 6, 'shot': 7, 'stamina': 100}
    )
    p3 = Player(
        number=3,
        role=Role.MID,
        pos=Cell(15, 8),
        side=Side.RIGHT,
        stats={'passing': 8, 'd_pass': 7, 'd_shot': 6, 'dribble': 7, 'shot': 9, 'stamina': 100}
    )
    return Team(
        name="Away Team",
        side=Side.RIGHT,
        color_key="B",
        players=[gk, p2, p3]
    )


@pytest.fixture
def game_state(field, home_team, away_team):
    """Stan gry z dwoma druzynami."""
    ball = Ball(carrier=None, free_pos=Cell(12, 8))
    return GameState(
        field=field,
        home=home_team,
        away=away_team,
        ball=ball,
        tick=0,
        action_no=0
    )


# ============================================================================
# TEST 1: Podanie bez przeciwnikow -> COMPLETE
# ============================================================================

def test_pass_no_opponents_complete(game_state, mock_rng, home_team):
    """Podanie bez przeciwnikow na trasie -> COMPLETE."""
    passer = home_team.players[1]  # #2 LEFT na (5, 8)
    target = home_team.players[2]  # #3 LEFT na (10, 8)
    
    # Przestaw przeciwnikow poza trase
    game_state.away.players[1].pos = Cell(20, 5)
    game_state.away.players[2].pos = Cell(15, 5)
    
    outcome = resolve_pass(game_state, passer, target, mock_rng)
    
    assert outcome.result == PassResult.COMPLETE
    assert outcome.interceptor is None
    assert outcome.target == target


# ============================================================================
# TEST 2: Podanie z przeciwnikiem na trasie -> INTERCEPTED
# ============================================================================

def test_pass_with_opponent_intercepted(game_state, mock_rng, home_team, away_team):
    """Podanie z przeciwnikiem na trasie -> INTERCEPTED."""
    passer = home_team.players[1]  # #2 LEFT na (5, 8)
    target = home_team.players[2]  # #3 LEFT na (10, 8)
    opponent = away_team.players[2]  # #3 RIGHT
    
    # Postaw przeciwnika na trasie
    opponent.pos = Cell(7, 8)
    
    # Mock: przeciwnik wygrywa przechwyt (obronca >> atakujacy w AIR)
    mock_rng.roll.side_effect = [3, 8]  # atakujacy slabo, obronca dobrze
    
    outcome = resolve_pass(game_state, passer, target, mock_rng)
    
    assert outcome.result == PassResult.INTERCEPTED
    assert outcome.interceptor == opponent
    assert outcome.target == target


# ============================================================================
# TEST 3: Podanie z 2 przeciwnikami, 1. nie przechwycil, 2. przechwycil
# ============================================================================

def test_pass_two_opponents_second_intercepts(game_state, mock_rng, home_team, away_team):
    """1. przeciwnik nie przechwycil, 2. przechwycil -> INTERCEPTED przez 2."""
    passer = home_team.players[1]  # #2 LEFT na (5, 8)
    target = home_team.players[2]  # #3 LEFT na (10, 8)
    opp1 = away_team.players[1]    # #2 RIGHT
    opp2 = away_team.players[2]    # #3 RIGHT
    
    # Postaw dwoch przeciwnikow na trasie
    opp1.pos = Cell(6, 8)
    opp2.pos = Cell(8, 8)
    
    # Mock: 1. atakujacy wygrywa, 2. obronca wygrywa
    mock_rng.roll.side_effect = [
        8, 3,  # 1. starcie: atakujacy wygrywa (podanie leci dalej)
        3, 8   # 2. starcie: obronca wygrywa (przechwyt)
    ]
    
    outcome = resolve_pass(game_state, passer, target, mock_rng)
    
    assert outcome.result == PassResult.INTERCEPTED
    assert outcome.interceptor == opp2
    assert outcome.target == target


# ============================================================================
# TEST 4: Strzal bez przeciwnikow, bramkarz broni -> SAVED
# ============================================================================

def test_shot_no_opponents_saved(game_state, mock_rng, away_team):
    """Strzal bez przeciwnikow, bramkarz broni -> SAVED."""
    shooter = away_team.players[2]  # #3 RIGHT na (15, 8)
    shooter.stats['shot'] = 10
    
    # Przestaw przeciwnikow z pola poza trase
    game_state.home.players[1].pos = Cell(5, 5)
    game_state.home.players[2].pos = Cell(10, 5)
    
    # Mock: placement + gk_action losowania + duel (bramkarz wygrywa)
    mock_rng.roll.side_effect = [
        6,   # placement (PLACED)
        6,   # gk_action (CATCH)
        3, 8 # duel: strzal << obrona
    ]
    
    outcome = resolve_shot(game_state, shooter, mock_rng)
    
    assert outcome.result == ShotResult.SAVED
    assert outcome.interceptor is None
    assert outcome.goalkeeper == game_state.home.gk()


# ============================================================================
# TEST 5: Strzal bez przeciwnikow, bramkarz nie broni -> GOAL
# ============================================================================

def test_shot_no_opponents_goal(game_state, mock_rng, away_team):
    """Strzal bez przeciwnikow, bramkarz nie broni -> GOAL."""
    shooter = away_team.players[2]  # #3 RIGHT na (15, 8)
    shooter.stats['shot'] = 10
    
    # Przestaw przeciwnikow z pola poza trase
    game_state.home.players[1].pos = Cell(5, 5)
    game_state.home.players[2].pos = Cell(10, 5)
    
    # Mock: placement + gk_action losowania + duel (strzelec wygrywa)
    mock_rng.roll.side_effect = [
        6,   # placement (PLACED)
        6,   # gk_action (CATCH)
        9, 2 # duel: strzal >> obrona
    ]
    
    outcome = resolve_shot(game_state, shooter, mock_rng)
    
    assert outcome.result == ShotResult.GOAL
    assert outcome.interceptor is None
    assert outcome.goalkeeper == game_state.home.gk()


# ============================================================================
# TEST 6: Strzal z zawodnikiem na trasie -> INTERCEPTED
# ============================================================================

def test_shot_with_opponent_intercepted(game_state, mock_rng, away_team, home_team):
    """Strzal z zawodnikiem na trasie, przechwyt -> INTERCEPTED."""
    shooter = away_team.players[2]  # #3 RIGHT na (15, 8)
    shooter.stats['shot'] = 10
    blocker = home_team.players[2]  # #3 LEFT
    
    # Postaw zawodnika na trasie
    blocker.pos = Cell(10, 8)
    
    # Mock: obronca wygrywa (blok)
    mock_rng.roll.side_effect = [3, 8]
    
    outcome = resolve_shot(game_state, shooter, mock_rng)
    
    assert outcome.result == ShotResult.INTERCEPTED
    assert outcome.interceptor == blocker
    assert outcome.goalkeeper == game_state.home.gk()


# ============================================================================
# TEST 7: is_goal() gdy ball.cell.x == -1 i y w goal_rows() -> (True, "LEFT")
# ============================================================================

def test_is_goal_left_side(game_state):
    """Pilka w bramce LEFT (x=-1, y w goal_rows) -> gol dla RIGHT."""
    game_state.ball.free_pos = Cell(-1, 8)
    
    is_gol, side = is_goal(game_state)
    
    assert is_gol is True
    assert side == "LEFT"


# ============================================================================
# TEST 8: is_goal() gdy ball.cell.x == 25 i y w goal_rows() -> (True, "RIGHT")
# ============================================================================

def test_is_goal_right_side(game_state):
    """Pilka w bramce RIGHT (x=25, y w goal_rows) -> gol dla LEFT."""
    game_state.ball.free_pos = Cell(25, 8)
    
    is_gol, side = is_goal(game_state)
    
    assert is_gol is True
    assert side == "RIGHT"


# ============================================================================
# TEST 9: is_goal() gdy ball.cell.x == -1 ale y poza goal_rows() -> (False, None)
# ============================================================================

def test_is_goal_outside_goal_rows(game_state):
    """Pilka za linia, ale poza bramka (y poza goal_rows) -> nie gol."""
    game_state.ball.free_pos = Cell(-1, 2)  # poza goal_rows (7,8,9)
    
    is_gol, side = is_goal(game_state)
    
    assert is_gol is False
    assert side is None


# ============================================================================
# TEST 10: is_out_of_bounds() gdy ball.cell.x == -1 -> True
# ============================================================================

def test_is_out_of_bounds_true(game_state):
    """Pilka poza boiskiem (x=-1) -> aut."""
    game_state.ball.free_pos = Cell(-1, 8)
    
    assert is_out_of_bounds(game_state) is True


# ============================================================================
# TEST 11: is_out_of_bounds() gdy ball.cell w srodku boiska -> False
# ============================================================================

def test_is_out_of_bounds_false(game_state):
    """Pilka w srodku boiska -> nie aut."""
    game_state.ball.free_pos = Cell(12, 8)
    
    assert is_out_of_bounds(game_state) is False


# ============================================================================
# TEST 12: resolve_pass() gdy target == passer.pos (podanie do siebie)
# ============================================================================

def test_pass_to_self_complete(game_state, mock_rng, home_team):
    """Podanie do siebie (0 kratek trajektorii) -> COMPLETE."""
    passer = home_team.players[1]  # #2 LEFT na (5, 8)
    target = home_team.players[1]  # ten sam zawodnik
    
    outcome = resolve_pass(game_state, passer, target, mock_rng)
    
    assert outcome.result == PassResult.COMPLETE
    assert outcome.interceptor is None
    assert outcome.target == target