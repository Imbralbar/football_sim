from __future__ import annotations
from dataclasses import dataclass, field as dcfield
from enum import Enum
import config as C
from core.field import Cell


class Role(str, Enum):
    GK = "GK"
    DEF = "DEF"
    MID = "MID"
    FWD = "FWD"


class Side(str, Enum):
    LEFT = "LEFT"     # broni lewej bramki, atakuje w prawo
    RIGHT = "RIGHT"

    def opposite(self) -> "Side":
        return Side.RIGHT if self is Side.LEFT else Side.LEFT


@dataclass
class Player:
    number: int
    role: Role
    pos: Cell
    side: Side
    home: Cell | None = None
    stats: dict = dcfield(default_factory=dict)
    style: str | None = None   # NOWE: hak na unikalne style zawodników (etap 2)

    def __post_init__(self) -> None:
        if self.home is None:
            self.home = self.pos
        if not self.stats:
            self.stats = dict(C.BASE_STATS[self.role.value])
        self.stamina: int = self.stats["stamina"]
        self.contact_ticks: int = 0      # licznik stycznosci z carrierem
        self.protected_until: int = -1   # numer akcji, do ktorej trwa ochrona
        self.protected_against: set[int] = set()   # NOWE: id() konkretnych obrońców objętych ochroną
        # GK: drybling po obronie (v0.6)
        self.gk_run_active: bool = False
        self.gk_dribble_chance: float = 0.0
        self.gk_has_won_once: bool = False
        self.shot_bonus_mult: float = 1.0

        # ── NOWE: świadomość taktyczna (core/ai/positioning.py) ──
        self.phase: str = C.PHASE_NEUTRAL          # "ATTACK" | "DEFENSE" | "NEUTRAL"
        self.marking_target: "Player | None" = None
        self.is_presser: bool = False
        self.dynamic_home: Cell = self.home        # przesuwana linia obrony
        # ── NOWE: karencje po starciu (duele wieloosobowe) ──
        self.frozen_until: int = -1             # numer akcji, do której zawodnik STOI w miejscu
        self.defense_cooldown_until: int = -1   # numer akcji, od której wolno mu znów bronić/pressować
        
    @property
    def is_gk(self) -> bool:
        return self.role is Role.GK

    def is_protected(self, action_no: int, defender: "Player | None" = None) -> bool:
        if action_no > self.protected_until:
            return False
        if C.PROTECTION_SCOPE == "ALL" or defender is None:
            return True
        return id(defender) in self.protected_against

    def grant_protection(self, action_no: int, defender: "Player | None" = None) -> None:
        self.protected_until = action_no + C.PROTECTION_ACTIONS
        if C.PROTECTION_SCOPE == "PAIR" and defender is not None:
            self.protected_against = {id(defender)}
        else:
            self.protected_against = set()

    def to_dict(self) -> dict:
        """Eksport do JSON dla Unity/Godot."""
        return {"number": self.number, "role": self.role.value,
                "x": self.pos.x, "y": self.pos.y,
                "side": self.side.value, "stamina": self.stamina}


@dataclass
class Team:
    name: str
    side: Side
    color_key: str                     # "A" = niebiescy, "B" = czarni
    players: list[Player] = dcfield(default_factory=list)
    style: dict = dcfield(default_factory=lambda: dict(C.TEAM_STYLE_DEFAULT))  # NOWE

    def gk(self) -> Player:
        return next(p for p in self.players if p.is_gk)

    def by_number(self, n: int) -> Player:
        return next(p for p in self.players if p.number == n)

    def outfield(self) -> list[Player]:
        return [p for p in self.players if not p.is_gk]