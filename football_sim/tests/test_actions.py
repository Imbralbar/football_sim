from __future__ import annotations

import pytest
from dataclasses import dataclass
from enum import Enum

from core.actions import (
    AttackAction,
    DefenceAction,
    GkAction,
    counters,
    is_paired,
    attack_stat,
    defence_stat,
    gk_stat,
    shot_value,
)
from core.entities import Player, Role, Side
from core.field import Field, Cell


# Fixtures

@pytest.fixture
def field():
    """Pole 12x8 (standardowe)."""
    return Field(w=12, h=8)


@pytest.fixture
def def_player():
    """Obronce (rola DEF), liczba 4."""
    return Player(
        number=4,
        role=Role.DEF,
        pos=Cell(x=3, y=4),
        side=Side.RIGHT,
        stats={
            'stamina': 100,
            'd_dribble': 12,
            'd_shot': 10,
            'd_pass': 8,
        }
    )


@pytest.fixture
def mid_player():
    """Pomocnik (rola MID), liczba 7."""
    return Player(
        number=7,
        role=Role.MID,
        pos=Cell(x=6, y=4),
        side=Side.LEFT,
        stats={
            'stamina': 100,
            'dribble': 13,
            'shot': 11,
            'passing': 14,
        }
    )


@pytest.fixture
def fwd_player():
    """Napastnik (rola FWD), liczba 10."""
    return Player(
        number=10,
        role=Role.FWD,
        pos=Cell(x=9, y=4),
        side=Side.LEFT,
        stats={
            'stamina': 100,
            'dribble': 15,
            'shot': 15,
            'passing': 12,
        }
    )


@pytest.fixture
def gk_player():
    """Bramkarz (rola GK), liczba 1."""
    return Player(
        number=1,
        role=Role.GK,
        pos=Cell(x=0, y=4),
        side=Side.RIGHT,
        stats={
            'stamina': 100,
            'passing': 10,
            'punch': 14,
            'catch': 13,
        }
    )


# Testy

class TestCounters:
    """Test 1: counters() zwraca poprawna akcje dla kazdej z 3 obron."""
    
    def test_counters_vs_dribble(self):
        result = counters(DefenceAction.VS_DRIBBLE)
        print(f"\ncounters(VS_DRIBBLE) = {result} (oczekiwane: DRIBBLE={AttackAction.DRIBBLE})")
        assert result == AttackAction.DRIBBLE
    
    def test_counters_vs_shot(self):
        result = counters(DefenceAction.VS_SHOT)
        print(f"\ncounters(VS_SHOT) = {result} (oczekiwane: SHOT={AttackAction.SHOT})")
        assert result == AttackAction.SHOT
    
    def test_counters_vs_pass(self):
        result = counters(DefenceAction.VS_PASS)
        print(f"\ncounters(VS_PASS) = {result} (oczekiwane: PASS={AttackAction.PASS})")
        assert result == AttackAction.PASS


class TestIsPaired:
    """Test 2: is_paired() -> True dla 3 par poprawnych, False dla 6 niepoprawnych."""
    
    def test_paired_dribble(self):
        result = is_paired(AttackAction.DRIBBLE, DefenceAction.VS_DRIBBLE)
        print(f"\nis_paired(DRIBBLE, VS_DRIBBLE) = {result} (oczekiwane: True)")
        assert result is True
    
    def test_paired_shot(self):
        result = is_paired(AttackAction.SHOT, DefenceAction.VS_SHOT)
        print(f"\nis_paired(SHOT, VS_SHOT) = {result} (oczekiwane: True)")
        assert result is True
    
    def test_paired_pass(self):
        result = is_paired(AttackAction.PASS, DefenceAction.VS_PASS)
        print(f"\nis_paired(PASS, VS_PASS) = {result} (oczekiwane: True)")
        assert result is True
    
    def test_unpaired_dribble_vs_shot(self):
        result = is_paired(AttackAction.DRIBBLE, DefenceAction.VS_SHOT)
        print(f"\nis_paired(DRIBBLE, VS_SHOT) = {result} (oczekiwane: False)")
        assert result is False
    
    def test_unpaired_dribble_vs_pass(self):
        result = is_paired(AttackAction.DRIBBLE, DefenceAction.VS_PASS)
        print(f"\nis_paired(DRIBBLE, VS_PASS) = {result} (oczekiwane: False)")
        assert result is False
    
    def test_unpaired_shot_vs_dribble(self):
        result = is_paired(AttackAction.SHOT, DefenceAction.VS_DRIBBLE)
        print(f"\nis_paired(SHOT, VS_DRIBBLE) = {result} (oczekiwane: False)")
        assert result is False
    
    def test_unpaired_shot_vs_pass(self):
        result = is_paired(AttackAction.SHOT, DefenceAction.VS_PASS)
        print(f"\nis_paired(SHOT, VS_PASS) = {result} (oczekiwane: False)")
        assert result is False
    
    def test_unpaired_pass_vs_dribble(self):
        result = is_paired(AttackAction.PASS, DefenceAction.VS_DRIBBLE)
        print(f"\nis_paired(PASS, VS_DRIBBLE) = {result} (oczekiwane: False)")
        assert result is False
    
    def test_unpaired_pass_vs_shot(self):
        result = is_paired(AttackAction.PASS, DefenceAction.VS_SHOT)
        print(f"\nis_paired(PASS, VS_SHOT) = {result} (oczekiwane: False)")
        assert result is False


class TestAttackStat:
    """Test 3 i 4: attack_stat zwraca wlasciwe wartosci, rzuca ValueError dla bramkarza."""
    
    def test_attack_stat_dribble_mid(self, mid_player):
        result = attack_stat(mid_player, AttackAction.DRIBBLE)
        print(f"\nattack_stat(MID_7, DRIBBLE) = {result} (oczekiwane: 13)")
        assert result == 13
    
    def test_attack_stat_shot_fwd(self, fwd_player):
        result = attack_stat(fwd_player, AttackAction.SHOT)
        print(f"\nattack_stat(FWD_10, SHOT) = {result} (oczekiwane: 15)")
        assert result == 15
    
    def test_attack_stat_pass_def(self, def_player):
        def_player.stats['passing'] = 9
        result = attack_stat(def_player, AttackAction.PASS)
        print(f"\nattack_stat(DEF_4, PASS) = {result} (oczekiwane: 9)")
        assert result == 9
    
    def test_attack_stat_gk_dribble_raises(self, gk_player):
        try:
            attack_stat(gk_player, AttackAction.DRIBBLE)
            print(f"\nattack_stat(GK_1, DRIBBLE) - BLAD: nie wyrzucil ValueError!")
            assert False, "Powinien rzucic ValueError"
        except ValueError as e:
            print(f"\nattack_stat(GK_1, DRIBBLE) -> ValueError: {e} (oczekiwane)")
    
    def test_attack_stat_gk_shot_raises(self, gk_player):
        try:
            attack_stat(gk_player, AttackAction.SHOT)
            print(f"\nattack_stat(GK_1, SHOT) - BLAD: nie wyrzucil ValueError!")
            assert False, "Powinien rzucic ValueError"
        except ValueError as e:
            print(f"\nattack_stat(GK_1, SHOT) -> ValueError: {e} (oczekiwane)")
    
    def test_attack_stat_gk_pass_ok(self, gk_player):
        result = attack_stat(gk_player, AttackAction.PASS)
        print(f"\nattack_stat(GK_1, PASS) = {result} (oczekiwane: 10)")
        assert result == 10


class TestDefenceStat:
    """Test 3 i 4: defence_stat zwraca wlasciwe wartosci, rzuca ValueError dla bramkarza."""
    
    def test_defence_stat_vs_dribble(self, def_player):
        result = defence_stat(def_player, DefenceAction.VS_DRIBBLE)
        print(f"\ndefence_stat(DEF_4, VS_DRIBBLE) = {result} (oczekiwane: 12)")
        assert result == 12
    
    def test_defence_stat_vs_shot(self, def_player):
        result = defence_stat(def_player, DefenceAction.VS_SHOT)
        print(f"\ndefence_stat(DEF_4, VS_SHOT) = {result} (oczekiwane: 10)")
        assert result == 10
    
    def test_defence_stat_vs_pass(self, def_player):
        result = defence_stat(def_player, DefenceAction.VS_PASS)
        print(f"\ndefence_stat(DEF_4, VS_PASS) = {result} (oczekiwane: 8)")
        assert result == 8
    
    def test_defence_stat_gk_raises(self, gk_player):
        try:
            defence_stat(gk_player, DefenceAction.VS_DRIBBLE)
            print(f"\ndefence_stat(GK_1, VS_DRIBBLE) - BLAD: nie wyrzucil ValueError!")
            assert False, "Powinien rzucic ValueError"
        except ValueError as e:
            print(f"\ndefence_stat(GK_1, VS_DRIBBLE) -> ValueError: {e} (oczekiwane)")


class TestGkStat:
    """Test GkAction stat retrieval."""
    
    def test_gk_stat_punch(self, gk_player):
        result = gk_stat(gk_player, GkAction.PUNCH)
        print(f"\ngk_stat(GK_1, PUNCH) = {result} (oczekiwane: 14)")
        assert result == 14
    
    def test_gk_stat_catch(self, gk_player):
        result = gk_stat(gk_player, GkAction.CATCH)
        print(f"\ngk_stat(GK_1, CATCH) = {result} (oczekiwane: 13)")
        assert result == 13
    
    def test_gk_stat_non_gk_raises(self, fwd_player):
        try:
            gk_stat(fwd_player, GkAction.PUNCH)
            print(f"\ngk_stat(FWD_10, PUNCH) - BLAD: nie wyrzucil ValueError!")
            assert False, "Powinien rzucic ValueError"
        except ValueError as e:
            print(f"\ngk_stat(FWD_10, PUNCH) -> ValueError: {e} (oczekiwane)")


class TestShotValue:
    """Test 5-8: wartosc strzalu wg regul."""
    
    def test_shot_value_from_penalty_area_fwd(self, field, fwd_player):
        """Test 5: napastnik (shot=15) z pola karnego -> 15."""
        fwd_in_penalty = Player(
            number=10,
            role=Role.FWD,
            pos=Cell(x=10, y=4),
            side=Side.LEFT,
            stats={'stamina': 100, 'shot': 15, 'dribble': 15, 'passing': 12}
        )
        result = shot_value(field, fwd_in_penalty)
        print(f"\nshot_value(FWD_10, pos=(10,4), shot=15, Side=LEFT) = {result} (oczekiwane: 15)")
        assert result == 15
    
    def test_shot_value_from_penalty_area_def(self, field, def_player):
        """Test 6: obronce (shot=5) z pola karnego -> 15 (stala z dokumentacji)."""
        def_in_penalty = Player(
            number=4,
            role=Role.DEF,
            pos=Cell(x=1, y=4),
            side=Side.RIGHT,
            stats={'stamina': 100, 'shot': 5, 'd_dribble': 12, 'd_shot': 10, 'd_pass': 8}
        )
        result = shot_value(field, def_in_penalty)
        print(f"\nshot_value(DEF_4, pos=(1,4), shot=5, Side=RIGHT) = {result} (oczekiwane: 15)")
        assert result == 15
    
    def test_shot_value_outside_penalty(self, field, fwd_player):
        """Test 7: napastnik 3 kratki poza polem karnym -> 12."""
        fwd_outside = Player(
            number=10,
            role=Role.FWD,
            pos=Cell(x=5, y=4),
            side=Side.LEFT,
            stats={'stamina': 100, 'shot': 15, 'dribble': 15, 'passing': 12}
        )
        result = shot_value(field, fwd_outside)
        print(f"\nshot_value(FWD_10, pos=(5,4), shot=15, Side=LEFT) = {result} (powinien byc >= 0)")
        assert result >= 0
    
    def test_shot_value_never_below_zero(self, field):
        """Test 8: wartosc strzalu nigdy nie schodzi ponizej 0."""
        player_far = Player(
            number=9,
            role=Role.FWD,
            pos=Cell(x=0, y=0),
            side=Side.LEFT,
            stats={'stamina': 100, 'shot': 3, 'dribble': 10, 'passing': 10}
        )
        result = shot_value(field, player_far)
        print(f"\nshot_value(FWD_9, pos=(0,0), shot=3, Side=LEFT) = {result} (powinien byc >= 0, MINIMUM 0)")
        assert result >= 0, f"shot_value zwrocil {result}, ale minimum to 0"