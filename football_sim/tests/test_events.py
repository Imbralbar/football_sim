from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum

import pytest

from core.events import EventLog, EventType, MatchEvent


# Mock DuelResult dla testu (symuluje strukture z resolver.py)
class Outcome(str, Enum):
    """Wynik starcia."""
    BEAT_DEFENDER = "BEAT_DEFENDER"
    INTERCEPTED = "INTERCEPTED"
    DRAW = "DRAW"


@dataclass(frozen=True)
class MockDuelResult:
    """Mock DuelResult do testowania add_duel()."""
    outcome: Outcome
    attacker_num: int = 0
    defender_num: int = 0
    
    def describe(self) -> str:
        return f"{self.outcome.value}: {self.attacker_num} vs {self.defender_num}"


def test_add_zdarzenia_rosnie_lista():
    """Test 1: add() dodaje zdarzenie, len(events) rosnie."""
    log = EventLog()
    assert len(log.events) == 0
    
    event1 = MatchEvent(
        action_no=1,
        tick=0,
        etype=EventType.KICKOFF,
        team="Blues"
    )
    log.add(event1)
    assert len(log.events) == 1
    
    event2 = MatchEvent(
        action_no=2,
        tick=5,
        etype=EventType.MOVE,
        team="Blues",
        player=10,
        from_cell=(5, 5),
        to_cell=(6, 5)
    )
    log.add(event2)
    assert len(log.events) == 2
    assert log.events[0] is event1
    assert log.events[1] is event2


def test_by_type_filtruje_gole():
    """Test 2: by_type(EventType.GOAL) filtruje poprawnie."""
    log = EventLog()
    
    log.add(MatchEvent(
        action_no=10,
        tick=15,
        etype=EventType.SHOT,
        team="Blues",
        player=9
    ))
    log.add(MatchEvent(
        action_no=12,
        tick=8,
        etype=EventType.GOAL,
        team="Blues",
        player=9,
        note="Header"
    ))
    log.add(MatchEvent(
        action_no=45,
        tick=20,
        etype=EventType.GOAL,
        team="Blacks",
        player=7
    ))
    log.add(MatchEvent(
        action_no=50,
        tick=10,
        etype=EventType.MOVE,
        team="Blues",
        player=5
    ))
    
    goals = log.by_type(EventType.GOAL)
    assert len(goals) == 2
    assert all(ev.etype == EventType.GOAL for ev in goals)
    assert goals[0].player == 9
    assert goals[1].player == 7


def test_by_action_zwraca_akcje():
    """Test 3: by_action(12) zwraca tylko zdarzenia z minuty 12."""
    log = EventLog()
    
    log.add(MatchEvent(action_no=11, tick=0, etype=EventType.MOVE, team="Blues"))
    log.add(MatchEvent(action_no=12, tick=5, etype=EventType.DUEL, team="Blues"))
    log.add(MatchEvent(action_no=12, tick=10, etype=EventType.MOVE, team="Blacks"))
    log.add(MatchEvent(action_no=12, tick=20, etype=EventType.PASS, team="Blues"))
    log.add(MatchEvent(action_no=13, tick=0, etype=EventType.SHOT, team="Blacks"))
    
    action_12 = log.by_action(12)
    assert len(action_12) == 3
    assert all(ev.action_no == 12 for ev in action_12)
    assert action_12[0].tick == 5
    assert action_12[1].tick == 10
    assert action_12[2].tick == 20


def test_to_json_zwraca_poprawny_json():
    """Test 4: to_json() zwraca poprawny JSON (json.loads nie rzuca wyjatku)."""
    log = EventLog()
    
    log.add(MatchEvent(
        action_no=1,
        tick=0,
        etype=EventType.KICKOFF,
        team="Blues",
        from_cell=(4, 4),
        to_cell=(5, 5),
        note="Start meczu"
    ))
    log.add(MatchEvent(
        action_no=5,
        tick=12,
        etype=EventType.SHOT,
        team="Blues",
        player=9,
        target=1,
        note="Strong kick"
    ))
    
    json_str = log.to_json(indent=2)
    
    # Sprawdz czy to poprawny JSON
    try:
        parsed = json.loads(json_str)
    except json.JSONDecodeError as e:
        pytest.fail(f"to_json() nie zwrocila poprawnego JSON: {e}")
    
    # Sprawdz strukture
    assert isinstance(parsed, list)
    assert len(parsed) == 2
    assert parsed[0]["action_no"] == 1
    assert parsed[0]["etype"] == "KICKOFF"
    assert parsed[0]["team"] == "Blues"
    assert parsed[1]["action_no"] == 5
    assert parsed[1]["etype"] == "SHOT"


def test_add_duel_zapisuje_enumy_jako_wartosci():
    """Test 5: add_duel() zapisuje Enumy jako stringi/inty, nie jako obiekty Enum."""
    log = EventLog()
    
    duel_result = MockDuelResult(
        outcome=Outcome.BEAT_DEFENDER,
        attacker_num=10,
        defender_num=4
    )
    
    log.add_duel(
        action_no=8,
        tick=12,
        team="Blues",
        result=duel_result
    )
    
    assert len(log.events) == 1
    event = log.events[0]
    assert event.etype == EventType.DUEL
    assert event.action_no == 8
    assert event.tick == 12
    assert event.team == "Blues"
    
    # Sprawdz czy duel jest slownikiem i czy zawiera serializowane wartosci
    assert isinstance(event.duel, dict)
    assert event.duel["outcome"] == "BEAT_DEFENDER"  # .value z Enum
    assert event.duel["attacker_num"] == 10  # int bez zmian
    assert event.duel["defender_num"] == 4   # int bez zmian
    
    # Sprawdz ze to sie prawidlowo serializuje do JSON
    json_str = log.to_json()
    parsed = json.loads(json_str)
    
    assert len(parsed) == 1
    assert parsed[0]["duel"]["outcome"] == "BEAT_DEFENDER"
    assert isinstance(parsed[0]["duel"]["outcome"], str)  # string, nie Enum
    assert isinstance(parsed[0]["duel"]["attacker_num"], int)