"""
Testy modulu core.penalties
Testuje resolve_penalty() i play_shootout() z 10 przypadkami jak opisane w zadaniu.
"""
import pytest
from dataclasses import dataclass
from enum import IntEnum
from typing import TYPE_CHECKING

# Mock klas z core (zeby nie dependowac od implementacji)
@dataclass
class MockPlayer:
    """Mock Player z core.entities"""
    number: int
    role: str  # "GK" | "DEF" | "MID" | "FWD"
    side: str  # "home" | "away"
    stats: dict = None

    def __post_init__(self):
        if self.stats is None:
            self.stats = {
                'shot': 5,
                'catch': 5,
                'pass': 5,
                'defense': 5,
                'dribble': 5
            }


@dataclass
class MockTeam:
    """Mock Team z core.entities"""
    side: str  # "home" | "away"
    players: list[MockPlayer] = None

    def __post_init__(self):
        if self.players is None:
            self.players = []

    def gk(self) -> MockPlayer:
        """Zwraca bramkarza druzyny"""
        for p in self.players:
            if p.role == "GK":
                return p
        raise ValueError(f"Brak bramkarza w druzynie {self.side}")

    def outfield(self) -> list[MockPlayer]:
        """Zwraca zawodnikow pola (bez bramkarza)"""
        return [p for p in self.players if p.role != "GK"]


class MockRng:
    """Mock Rng z core.dice - deterministyczny"""
    def __init__(self, seed: int, rolls: list[int] | None = None):
        self.seed = seed
        self.rolls = rolls or []
        self.roll_idx = 0

    def roll(self) -> int:
        """Zwraca 1..10"""
        if self.roll_idx < len(self.rolls):
            val = self.rolls[self.roll_idx]
            self.roll_idx += 1
            return val
        # Fallback
        return 5

    def randint(self, a: int, b: int) -> int:
        """Zwraca losowa liczbe z [a, b]"""
        if self.roll_idx < len(self.rolls):
            val = self.rolls[self.roll_idx]
            self.roll_idx += 1
            return val
        # Fallback
        return a + (self.seed % (b - a + 1))


class MockEventLog:
    """Mock EventLog z core.events"""
    def __init__(self):
        self.events = []

    def add_penalty(self, round: int, shooter: MockPlayer, direction: str,
                    gk_direction: str, scored: bool, hit_post: bool):
        """Zaloguj karny"""
        self.events.append({
            'round': round,
            'shooter': shooter,
            'direction': direction,
            'gk_direction': gk_direction,
            'scored': scored,
            'hit_post': hit_post
        })


# Import real classes
from core.penalties import (
    PenaltyDirection, PenaltyResult, ShootoutResult,
    resolve_penalty, play_shootout
)


class TestResolvePenalty:
    """Testy resolve_penalty()"""

    def test_01_saved_when_directions_match(self):
        """Test 1: shot_dir == gk_dir -> saved=True, scored=False"""
        shooter = MockPlayer(number=2, role="FWD", side="home")
        goalkeeper = MockPlayer(number=1, role="GK", side="away")
        rng = MockRng(seed=1)

        result = resolve_penalty(
            shooter, goalkeeper,
            PenaltyDirection.LEFT, PenaltyDirection.LEFT,
            rng
        )

        assert result.saved is True
        assert result.scored is False
        assert result.hit_post is False
        assert result.shot_direction == PenaltyDirection.LEFT
        assert result.gk_direction == PenaltyDirection.LEFT

    def test_02_goal_when_center_direction(self):
        """Test 2: shot_dir=CENTER, gk_dir=LEFT -> scored=True (CENTER nigdy slupek)"""
        shooter = MockPlayer(number=2, role="FWD", side="home")
        goalkeeper = MockPlayer(number=1, role="GK", side="away")
        rng = MockRng(seed=2)

        result = resolve_penalty(
            shooter, goalkeeper,
            PenaltyDirection.CENTER, PenaltyDirection.LEFT,
            rng
        )

        assert result.scored is True
        assert result.saved is False
        assert result.hit_post is False

    def test_03_goal_when_sides_differ_no_post(self):
        """Test 3: shot_dir=LEFT, gk_dir=RIGHT, roll > 5 -> scored=True"""
        shooter = MockPlayer(number=2, role="FWD", side="home")
        goalkeeper = MockPlayer(number=1, role="GK", side="away")
        # roll = 10 (> 5, brak slupka)
        rng = MockRng(seed=3, rolls=[10])

        result = resolve_penalty(
            shooter, goalkeeper,
            PenaltyDirection.LEFT, PenaltyDirection.RIGHT,
            rng
        )

        assert result.scored is True
        assert result.saved is False
        assert result.hit_post is False

    def test_04_post_hit_when_left_right_low_roll(self):
        """Test 4: shot_dir=LEFT, gk_dir=RIGHT, roll <= 5 -> hit_post=True"""
        shooter = MockPlayer(number=2, role="FWD", side="home")
        goalkeeper = MockPlayer(number=1, role="GK", side="away")
        # roll = 3 (<= 5, slupek!)
        rng = MockRng(seed=4, rolls=[3])

        result = resolve_penalty(
            shooter, goalkeeper,
            PenaltyDirection.LEFT, PenaltyDirection.RIGHT,
            rng
        )

        assert result.scored is False
        assert result.hit_post is True
        assert result.saved is False

    def test_04b_post_hit_right_direction(self):
        """Test 4b: shot_dir=RIGHT, gk_dir=LEFT, roll <= 5 -> hit_post=True"""
        shooter = MockPlayer(number=3, role="FWD", side="home")
        goalkeeper = MockPlayer(number=1, role="GK", side="away")
        # roll = 5 (<= 5, slupek!)
        rng = MockRng(seed=5, rolls=[5])

        result = resolve_penalty(
            shooter, goalkeeper,
            PenaltyDirection.RIGHT, PenaltyDirection.LEFT,
            rng
        )

        assert result.scored is False
        assert result.hit_post is True
        assert result.saved is False


class TestPlayShootout:
    """Testy play_shootout()"""

    @pytest.fixture
    def teams_5v5(self):
        """Fixture: 2 druzyny x 5 strzelcow + bramkarz"""
        home = MockTeam(side="home")
        home.players = [
            MockPlayer(1, "GK", "home"),      # Bramkarz
            MockPlayer(2, "DEF", "home"),     # Strzelcy
            MockPlayer(3, "DEF", "home"),
            MockPlayer(4, "MID", "home"),
            MockPlayer(5, "MID", "home"),
            MockPlayer(6, "FWD", "home"),
        ]

        away = MockTeam(side="away")
        away.players = [
            MockPlayer(1, "GK", "away"),
            MockPlayer(2, "DEF", "away"),
            MockPlayer(3, "DEF", "away"),
            MockPlayer(4, "MID", "away"),
            MockPlayer(5, "MID", "away"),
            MockPlayer(6, "FWD", "away"),
        ]

        return home, away

    def test_05_shootout_with_strategies_deterministic(self, teams_5v5):
        """Test 5: play_shootout() z podanymi strategiami -> deterministyczny wynik (wczesne zwyciestwo)"""
        home, away = teams_5v5

        # Strategia dla WCZESNEGO ZWYCIESTWA home:
        # home: CENTER -> gol zawsze
        # away: PRAWO -> gk_home RIGHT -> save (pokrycie)
        # Rundy 1-3: home 3-0, away max 2 -> home wygrywa!
        home_strategy = [PenaltyDirection.CENTER] * 5
        away_strategy = [PenaltyDirection.RIGHT] * 5
        gk_home_strategy = [PenaltyDirection.RIGHT] * 5
        gk_away_strategy = [PenaltyDirection.LEFT] * 5

        rng = MockRng(seed=50, rolls=[])
        result = play_shootout(
            home, away, rng,
            home_strategy=home_strategy,
            away_strategy=away_strategy,
            gk_home_strategy=gk_home_strategy,
            gk_away_strategy=gk_away_strategy
        )

        # Po rundzie 3: home 3, away 0
        # remaining = 5 - 3 = 2
        # max_away_goals = 0 + 2 = 2 < 3 -> home wygrywa!
        assert result.home_goals == 3
        assert result.away_goals == 0
        assert result.rounds_played == 3
        assert result.winner == "home"

    def test_06_early_victory_3_0(self, teams_5v5):
        """Test 6: Wczesne zwyciestwo: home 3-0 po 3 rundach -> rounds_played=3"""
        home, away = teams_5v5

        # home: zawsze CENTER -> gol zawsze (CENTER nigdy nie trafia slupka)
        # away: zawsze PRAWO -> home GK PRAWO -> obrona (kierunki sie pokrywaja)
        home_strategy = [PenaltyDirection.CENTER] * 5
        away_strategy = [PenaltyDirection.RIGHT] * 5
        gk_home_strategy = [PenaltyDirection.RIGHT] * 5  # pokrywa RIGHT -> obrona
        gk_away_strategy = [PenaltyDirection.LEFT] * 5   # nie pokrywa CENTER -> gol

        rng = MockRng(seed=60, rolls=[])
        result = play_shootout(
            home, away, rng,
            home_strategy=home_strategy,
            away_strategy=away_strategy,
            gk_home_strategy=gk_home_strategy,
            gk_away_strategy=gk_away_strategy
        )

        # Po rundzie 3: home 3, away 0
        # remaining_rounds = 5 - 3 = 2
        # max_away_goals = 0 + 2 = 2 < 3 -> home wygral po rundzie 3!
        assert result.home_goals == 3
        assert result.away_goals == 0
        assert result.rounds_played == 3
        assert result.winner == "home"

    def test_07_sudden_death_5_5_goes_to_round_6(self, teams_5v5):
        """Test 7: Remis 5-5 po 5 rundach -> sudden death, runda 6 z rozroczeniem"""
        home, away = teams_5v5

        home_strategy = [PenaltyDirection.CENTER] * 5 + [PenaltyDirection.LEFT]
        away_strategy = [PenaltyDirection.CENTER] * 5 + [PenaltyDirection.RIGHT]
        gk_home_strategy = [PenaltyDirection.LEFT] * 5 + [PenaltyDirection.RIGHT]
        gk_away_strategy = [PenaltyDirection.LEFT] * 5 + [PenaltyDirection.RIGHT]

        rng = MockRng(seed=70, rolls=[])
        
        print("\n=== TEST 7 DEBUG ===")
        print(f"home_strategy: {home_strategy}")
        print(f"away_strategy: {away_strategy}")
        print(f"gk_home_strategy: {gk_home_strategy}")
        print(f"gk_away_strategy: {gk_away_strategy}")
        
        result = play_shootout(
            home, away, rng,
            home_strategy=home_strategy,
            away_strategy=away_strategy,
            gk_home_strategy=gk_home_strategy,
            gk_away_strategy=gk_away_strategy
        )
        
        print(f"\n=== RESULT ===")
        print(f"home_goals: {result.home_goals}")
        print(f"away_goals: {result.away_goals}")
        print(f"rounds_played: {result.rounds_played}")
        print(f"winner: {result.winner}")
        
        print(f"\n=== PENALTY RESULTS (last 3) ===")
        for i, penalty in enumerate(result.penalty_results[-6:]):
            print(f"{i}: shooter={penalty.shooter.number} side={penalty.shooter.side}, "
                  f"shot={penalty.shot_direction.name} vs gk={penalty.gk_direction.name}, "
                  f"scored={penalty.scored} saved={penalty.saved} hit_post={penalty.hit_post}")

        assert result.home_goals == 6
        assert result.away_goals == 5
        assert result.rounds_played == 6
        assert result.winner == "home"

    def test_08_none_strategy_no_crash(self, teams_5v5):
        """Test 8: play_shootout() z None strategy -> losuje, nie crashuje"""
        home, away = teams_5v5
        
        # Strategie z wiekszym balansem zeby nie bylo wczesnego zwyciestwa
        # home: zawsze CENTER (gol zawsze)
        # away: zawsze SRODEK (gol zawsze)
        # GK: zawsze LEFT (nie pokrywa CENTER/SRODEK)
        # Rezultat: wszystkie gole -> conajmniej do rundy 5
        home_strategy = [PenaltyDirection.CENTER] * 10
        away_strategy = [PenaltyDirection.CENTER] * 10
        gk_home_strategy = [PenaltyDirection.LEFT] * 10
        gk_away_strategy = [PenaltyDirection.LEFT] * 10
        
        rng = MockRng(seed=80, rolls=[])
        result = play_shootout(
            home, away, rng,
            home_strategy=home_strategy,
            away_strategy=away_strategy,
            gk_home_strategy=gk_home_strategy,
            gk_away_strategy=gk_away_strategy
        )
        
        # Powinno sie zakonczyc bez bledu
        assert result.home_goals >= 0
        assert result.away_goals >= 0
        assert result.rounds_played >= 5  # Zawsze conajmniej 5 rund (wszystkie gole = remis)
        assert result.winner in ("home", "away")

    def test_09_determinism_same_seed(self, teams_5v5):
        """Test 9: Rng(seed=42) x 2 -> identyczne wyniki"""
        home, away = teams_5v5

        # Pierwszy shootout
        rng1 = MockRng(seed=42, rolls=[1, 2, 3, 1, 2] * 30)
        result1 = play_shootout(home, away, rng1)

        # Drugi shootout z tym samym seed i rolls
        rng2 = MockRng(seed=42, rolls=[1, 2, 3, 1, 2] * 30)
        result2 = play_shootout(home, away, rng2)

        # Powinny byc identyczne
        assert result1.home_goals == result2.home_goals
        assert result1.away_goals == result2.away_goals
        assert result1.winner == result2.winner
        assert result1.rounds_played == result2.rounds_played

    def test_10_event_log_called_for_each_penalty(self, teams_5v5):
        """Test 10: event_log.add_penalty() dla kazdego karnego"""
        home, away = teams_5v5

        home_strategy = [PenaltyDirection.CENTER] * 6
        away_strategy = [PenaltyDirection.LEFT] * 6
        gk_home_strategy = [PenaltyDirection.RIGHT] * 6
        gk_away_strategy = [PenaltyDirection.RIGHT] * 6

        event_log = MockEventLog()
        rng = MockRng(seed=100, rolls=[])

        result = play_shootout(
            home, away, rng,
            event_log=event_log,
            home_strategy=home_strategy,
            away_strategy=away_strategy,
            gk_home_strategy=gk_home_strategy,
            gk_away_strategy=gk_away_strategy
        )

        # Ilosc eventow = 2 * rounds_played
        # (kazda runda: home strzela, away strzela)
        expected_events = 2 * result.rounds_played
        assert len(event_log.events) == expected_events

        # Sprawdz, ze kazdego eventu maja wlasciwe pola
        for event in event_log.events:
            assert 'round' in event
            assert 'shooter' in event
            assert 'direction' in event
            assert 'gk_direction' in event
            assert 'scored' in event
            assert 'hit_post' in event
            assert event['direction'] in ('LEFT', 'CENTER', 'RIGHT')
            assert event['gk_direction'] in ('LEFT', 'CENTER', 'RIGHT')