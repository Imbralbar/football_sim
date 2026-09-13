from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class EventType(str, Enum):
    """Typy zdarzen podczas meczu pilkarskiego."""
    KICKOFF = "KICKOFF"
    MOVE = "MOVE"
    DUEL = "DUEL"
    PASS = "PASS"
    SHOT = "SHOT"
    SAVE = "SAVE"
    GOAL = "GOAL"
    TURNOVER = "TURNOVER"
    HALFTIME = "HALFTIME"
    FULLTIME = "FULLTIME"


def _serialize_duel_dict(duel_dict: dict | None) -> dict | None:
    """Konwertuje Enumy w slowniku na ich wartosci (stringi lub inty).
    
    Uzywane do serializacji DuelResult splaszczonego do dict,
    aby zagwarantowac ze JSON bedzie zawierac tylko podstawowe typy.
    """
    if duel_dict is None:
        return None
    
    result = {}
    for key, value in duel_dict.items():
        if isinstance(value, Enum):
            result[key] = value.value
        elif isinstance(value, dict):
            result[key] = _serialize_duel_dict(value)
        elif isinstance(value, list):
            result[key] = [
                item.value if isinstance(item, Enum) else item
                for item in value
            ]
        else:
            result[key] = value
    
    return result


@dataclass(frozen=True)
class MatchEvent:
    """Pojedyncze zdarzenie podczas meczu.
    
    Atrybuty:
        action_no: Numer akcji (minuta 1..90+)
        tick: Numer ticku w akcji (0..35)
        etype: Typ zdarzenia (EventType)
        team: Nazwa zespolu (np. "Blues", "Blacks") lub None
        player: Numer zawodnika z piłka lub None
        target: Numer drugiego zawodnika (cel dryblingu/podania/strzału) lub None
        from_cell: Komórka startu (x, y) lub None
        to_cell: Komórka konca (x, y) lub None
        duel: Słownik z danymi o starciu (ze splaszczonego DuelResult) lub None
        note: Dodatkowy opis zdarzenia
    """
    action_no: int
    tick: int
    etype: EventType
    team: str | None = None
    player: int | None = None
    target: int | None = None
    from_cell: tuple[int, int] | None = None
    to_cell: tuple[int, int] | None = None
    duel: dict | None = None
    note: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        """Konwertuje zdarzenie na slownik do JSON.
        
        Zwraca:
            Slownik z wszystkimi atrybutami, gotowy do json.dumps().
        """
        data = asdict(self)
        data["etype"] = self.etype.value
        
        # Serializuj duel dict, aby zagwarantowac ze Enumy sa zapisane jako wartosci
        if data.get("duel") is not None:
            data["duel"] = _serialize_duel_dict(data["duel"])
        
        return data
    
    def describe(self) -> str:
        """Generuje tekstowy opis zdarzenia w formacie gracza.
        
        Zwraca:
            String w formacie: "12' [DUEL] Blues #10 vs Blacks #4 -> BEAT_DEFENDER"
        """
        minute = self.action_no
        etype_str = self.etype.value
        
        base = f"{minute}' [{etype_str}]"
        
        if self.team is None:
            return f"{base} {self.note}".strip()
        
        if self.player is not None:
            player_str = f"{self.team} #{self.player}"
        else:
            player_str = self.team
        
        if self.target is not None:
            player_str += f" vs {self.target}"
        
        parts = [base, player_str]
        
        if self.note:
            parts.append(f"-> {self.note}")
        
        return " ".join(parts)


@dataclass
class EventLog:
    """Logi wszystkich zdarzen podczas meczu.
    
    Przechowuje sekwencje wszystkich zdarzen i umozliwia filtrowanie,
    podsumowanie oraz eksport do JSON.
    """
    events: list[MatchEvent] = field(default_factory=list)
    
    def add(self, ev: MatchEvent) -> None:
        """Dodaje zdarzenie do logu.
        
        Argumenty:
            ev: Zdarzenie do dodania
        """
        self.events.append(ev)
    
    def add_duel(self, action_no: int, tick: int, team: str,
                 result: Any) -> None:
        """Dodaje zdarzenie starcia na podstawie DuelResult.
        
        Konwertuje DuelResult do slownika (splaszczonego), zapisujac
        Enumy jako ich wartosci (.value), aby zagwarantowac
        ze sie zserializuja prawidlowo do JSON.
        
        Argumenty:
            action_no: Numer akcji (minuta)
            tick: Numer ticku w akcji
            team: Zespol atakujacy
            result: DuelResult (obiekt z outcome i innymi polami)
        """
        duel_dict = asdict(result)
        # Serializuj Enumy w DuelResult
        duel_dict = _serialize_duel_dict(duel_dict)
        
        event = MatchEvent(
            action_no=action_no,
            tick=tick,
            etype=EventType.DUEL,
            team=team,
            duel=duel_dict
        )
        self.add(event)
    
    def goals(self) -> list[MatchEvent]:
        """Zwraca liste wszystkich goli.
        
        Zwraca:
            Lista MatchEvent z etype == GOAL
        """
        return [ev for ev in self.events if ev.etype == EventType.GOAL]
    
    def by_type(self, etype: EventType) -> list[MatchEvent]:
        """Filtruje zdarzenia po typie.
        
        Argumenty:
            etype: Typ zdarzenia do filtrowania
            
        Zwraca:
            Lista zdarzen danego typu
        """
        return [ev for ev in self.events if ev.etype == etype]
    
    def by_action(self, action_no: int) -> list[MatchEvent]:
        """Filtruje zdarzenia po numerze akcji (minucie).
        
        Argumenty:
            action_no: Numer akcji do filtrowania
            
        Zwraca:
            Lista zdarzen z danej akcji
        """
        return [ev for ev in self.events if ev.action_no == action_no]
    
    def to_json(self, indent: int = 2) -> str:
        """Eksportuje caly przebieg meczu do JSON.
        
        Gotowe do importu w Unity/Godot dla animacji.
        
        Argumenty:
            indent: Liczba spacji do wciec (domyslnie 2)
            
        Zwraca:
            String zawierajacy poprawny JSON z lista wszystkich zdarzen
        """
        events_dicts = [ev.to_dict() for ev in self.events]
        return json.dumps(events_dicts, indent=indent)
    
    def summary(self) -> str:
        """Generuje tekstowe podsumowanie meczu.
        
        Zwraca:
            String z liczba akcji, strza;ow, goli, starc itd.
        """
        total_actions = max((ev.action_no for ev in self.events), default=0)
        total_events = len(self.events)
        goal_count = len(self.goals())
        shot_count = len(self.by_type(EventType.SHOT))
        duel_count = len(self.by_type(EventType.DUEL))
        
        return (
            f"Liczba akcji: {total_actions}, "
            f"Zdarzenia: {total_events}, "
            f"Gole: {goal_count}, "
            f"Strzaly: {shot_count}, "
            f"Starcia: {duel_count}"
        )
    def add_pass(
        self,
        action: int,
        passer: Player,
        target: Player,
        intercepted: bool
    ) -> None:
        """Dodaje event podania."""
        from core.field import Cell
        
        ev = MatchEvent(
            action_no=action,
            tick=0,  # opcjonalnie: mozna przekazac tick
            etype=EventType.PASS,
            team=passer.side.value,
            player=passer.number,
            target=target.number,
            from_cell=(passer.pos.x, passer.pos.y),
            to_cell=(target.pos.x, target.pos.y),
            duel=None,
            note=f"{'Intercepted' if intercepted else 'Complete'}"
        )
        self.add(ev)

    def add_shot(
        self,
        action: int,
        shooter: Player,
        saved: bool
    ) -> None:
        """Dodaje event strzalu."""
        ev = MatchEvent(
            action_no=action,
            tick=0,
            etype=EventType.SHOT,
            team=shooter.side.value,
            player=shooter.number,
            target=None,
            from_cell=(shooter.pos.x, shooter.pos.y),
            to_cell=None,
            duel=None,
            note=f"{'Saved' if saved else 'Goal or blocked'}"
        )
        self.add(ev)

    def add_goal(
        self,
        action: int,
        scorer: Player,
        assist: Player | None
    ) -> None:
        """Dodaje event gola."""
        assist_note = f"Assist: {assist.number}" if assist else "No assist"
        
        ev = MatchEvent(
            action_no=action,
            tick=0,
            etype=EventType.GOAL,
            team=scorer.side.value,
            player=scorer.number,
            target=assist.number if assist else None,
            from_cell=(scorer.pos.x, scorer.pos.y),
            to_cell=None,
            duel=None,
            note=assist_note
        )
        self.add(ev)  