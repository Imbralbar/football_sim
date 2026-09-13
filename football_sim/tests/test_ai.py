from __future__ import annotations

import pytest
from core.ai import decide_action, pick_pass_target, is_under_pressure, AiDecision
from core.entities import Player, Team, Role, Side
from core.field import Field, Cell
from core.ball import Ball
from core.state import GameState
import config as C


@pytest.fixture
def field():
    return Field()


@pytest.fixture
def home_team(field):
    """Druzyna domowa (niebieska, side=LEFT)."""
    players = [
        Player(number=1, role=Role.GK, pos=Cell(2, 8), side=Side.LEFT),
        Player(number=2, role=Role.DEF, pos=Cell(6, 5), side=Side.LEFT),
        Player(number=3, role=Role.DEF, pos=Cell(6, 12), side=Side.LEFT),
        Player(number=7, role=Role.MID, pos=Cell(12, 8), side=Side.LEFT),
        Player(number=10, role=Role.FWD, pos=Cell(18, 8), side=Side.LEFT),
    ]
    return Team(name="Home", side=Side.LEFT, color_key="A", players=players)


@pytest.fixture
def away_team(field):
    """Druzyna gostujaca (czarna, side=RIGHT)."""
    players = [
        Player(number=1, role=Role.GK, pos=Cell(23, 8), side=Side.RIGHT),
        Player(number=4, role=Role.DEF, pos=Cell(19, 5), side=Side.RIGHT),
        Player(number=5, role=Role.DEF, pos=Cell(19, 12), side=Side.RIGHT),
        Player(number=8, role=Role.MID, pos=Cell(13, 8), side=Side.RIGHT),
        Player(number=11, role=Role.FWD, pos=Cell(8, 8), side=Side.RIGHT),
    ]
    return Team(name="Away", side=Side.RIGHT, color_key="B", players=players)


@pytest.fixture
def game_state(field, home_team, away_team):
    """Stan gry."""
    state = GameState(
        field=field,
        home=home_team,
        away=away_team,
        ball=Ball(carrier=None, free_pos=Cell(12, 8)),
        tick=0,
        action_no=1,
    )
    return state


class TestDecideAction:
    """Testy funkcji decide_action()."""

    def test_01_in_penalty_area_shoot(self, game_state):
        """Test 1: Zawodnik w polu karnym przeciwnika -> SHOOT."""
        carrier = game_state.home.by_number(10)  # FWD
        carrier.pos = Cell(22, 8)  # Pole karne przeciwnika
        
        decision, target = decide_action(game_state, carrier)
        
        assert decision == AiDecision.SHOOT
        assert target is None

    def test_02_under_pressure_pass(self, game_state):
        """Test 2: Zawodnik pod presja (obronca 2 kratki) -> PASS."""
        carrier = game_state.home.by_number(7)  # MID
        carrier.pos = Cell(12, 8)
        
        # Obronca 2 kratki od niego
        opp = game_state.away.by_number(8)  # MID
        opp.pos = Cell(14, 8)
        
        decision, target = decide_action(game_state, carrier)
        
        assert decision == AiDecision.PASS
        assert target is not None
        assert target != carrier

    def test_03_def_without_pressure_pass(self, game_state):
        """Test 3: DEF bez presji -> PASS do przodu (MID/FWD)."""
        carrier = game_state.home.by_number(2)  # DEF
        carrier.pos = Cell(6, 5)
        
        # Wsi obroncy daleko
        game_state.away.by_number(4).pos = Cell(15, 5)
        game_state.away.by_number(5).pos = Cell(15, 12)
        game_state.away.by_number(8).pos = Cell(14, 8)  # MID daleko
        
        decision, target = decide_action(game_state, carrier)
        
        assert decision == AiDecision.PASS
        assert target is not None
        # Powinien byc MID lub FWD
        assert target.role in (Role.MID, Role.FWD)

    def test_04_fwd_in_shot_range_shoot(self, game_state):
        """Test 4: FWD w zasiegu strzalu (< SHOT_RANGE) bez presji -> SHOOT."""
        carrier = game_state.home.by_number(10)  # FWD
        # Zmieniamy pozycje, aby byc blizenale sie zdalezie
        # Jesli SHOT_RANGE=8 i pole ma szerokosc 25, bramka na x=24 lub 0
        # Dla LEFT (atakuje w prawo), bramka na x=24
        # Na Cell(18, 8): odleglosc = 24-18 = 6 < 8 -> powinien strzelac
        carrier.pos = Cell(18, 8)
        
        # Wszyscy obroncy daleko
        game_state.away.by_number(4).pos = Cell(5, 5)
        game_state.away.by_number(5).pos = Cell(5, 12)
        game_state.away.by_number(8).pos = Cell(5, 8)  # MID daleko
        
        decision, target = decide_action(game_state, carrier)
        
        assert decision == AiDecision.SHOOT
        assert target is None

    def test_05_continue_dribble_default(self, game_state):
        """Test 5: MID bez presji, daleko od bramki -> CONTINUE_DRIBBLE."""
        carrier = game_state.home.by_number(7)  # MID
        carrier.pos = Cell(12, 8)  # srodek boiska
        
        # Wszyscy obroncy daleko
        game_state.away.by_number(4).pos = Cell(5, 5)
        game_state.away.by_number(5).pos = Cell(5, 12)
        game_state.away.by_number(8).pos = Cell(5, 8)  # MID daleko
        
        decision, target = decide_action(game_state, carrier)
        
        # MID bez specjalnych warunkow -> drybling
        assert decision == AiDecision.CONTINUE_DRIBBLE
        assert target is None


class TestPickPassTarget:
    """Testy funkcji pick_pass_target()."""

    def test_05_picks_player_closer_to_goal(self, game_state):
        """Test 5: pick_pass_target() wybiera gracza blizej bramki."""
        carrier = game_state.home.by_number(7)  # MID
        carrier.pos = Cell(12, 8)
        
        mid = game_state.home.by_number(7)
        fwd = game_state.home.by_number(10)
        
        fwd.pos = Cell(20, 8)  # Blizej bramki
        mid.pos = Cell(15, 8)  # Dalej od bramki
        
        target = pick_pass_target(game_state, carrier)
        
        # Powinien wybrac FWD (blizej bramki)
        assert target == fwd

    def test_06_no_available_targets(self, game_state):
        """Test 6: pick_pass_target() -> None gdy brak dostepnych celow."""
        # Tylko carrier i bramkarz w druzynie
        game_state.home.players = [
            game_state.home.by_number(1),  # GK
            game_state.home.by_number(7),  # MID (carrier)
        ]
        
        carrier = game_state.home.by_number(7)
        
        target = pick_pass_target(game_state, carrier)
        
        assert target is None

    def test_09_pass_target_excludes_gk(self, game_state):
        """Test 9: pick_pass_target() nie wybiera bramkarza."""
        carrier = game_state.home.by_number(2)  # DEF
        carrier.pos = Cell(6, 5)
        
        # Bramkarz bardzo blisko
        gk = game_state.home.by_number(1)
        gk.pos = Cell(7, 5)
        
        target = pick_pass_target(game_state, carrier)
        
        # Nie powinien wybrac bramkarza
        assert target is not None
        assert not target.is_gk

    def test_10_pass_target_excludes_carrier(self, game_state):
        """Test 10: pick_pass_target() nie wybiera samego siebie."""
        carrier = game_state.home.by_number(7)  # MID
        carrier.pos = Cell(12, 8)
        
        target = pick_pass_target(game_state, carrier)
        
        # Nie powinien wybrac samego siebie
        assert target != carrier


class TestIsUnderPressure:
    """Testy funkcji is_under_pressure()."""

    def test_07_under_pressure_true(self, game_state):
        """Test 7: is_under_pressure() -> True gdy obronca <= threshold."""
        carrier = game_state.home.by_number(10)  # FWD
        carrier.pos = Cell(18, 8)
        
        opp = game_state.away.by_number(4)  # DEF
        opp.pos = Cell(20, 8)  # 2 kratki daleko (threshold = 3)
        
        # Pozostali daleko
        game_state.away.by_number(5).pos = Cell(5, 12)
        game_state.away.by_number(8).pos = Cell(5, 8)
        
        result = is_under_pressure(game_state, carrier, C.THREAT_DISTANCE)
        
        assert result is True

    def test_08_under_pressure_false(self, game_state):
        """Test 8: is_under_pressure() -> False gdy wszystko daleko."""
        carrier = game_state.home.by_number(7)  # MID
        carrier.pos = Cell(12, 8)
        
        # Wszyscy obroncy DALEKO (> THREAT_DISTANCE)
        game_state.away.by_number(4).pos = Cell(5, 5)   # DEF
        game_state.away.by_number(5).pos = Cell(5, 12)  # DEF
        game_state.away.by_number(8).pos = Cell(5, 8)   # MID
        
        result = is_under_pressure(game_state, carrier, C.THREAT_DISTANCE)
        
        assert result is False

    def test_08_under_pressure_ignores_gk(self, game_state):
        """Test 8b: is_under_pressure() ignuruje bramkarza."""
        carrier = game_state.home.by_number(10)  # FWD
        carrier.pos = Cell(22, 8)
        
        # Tylko bramkarz bardzo blisko
        gk = game_state.away.by_number(1)
        gk.pos = Cell(23, 8)
        
        # Pozostali daleko
        game_state.away.by_number(4).pos = Cell(5, 5)
        game_state.away.by_number(5).pos = Cell(5, 12)
        game_state.away.by_number(8).pos = Cell(5, 8)
        
        result = is_under_pressure(game_state, carrier, C.THREAT_DISTANCE)
        
        # Bramkarz nie liczy sie jako presja
        assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])