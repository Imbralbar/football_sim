from __future__ import annotations
from dataclasses import dataclass
from core.field import Cell
from core.entities import Player


@dataclass
class Ball:
    """Pilka jest albo u zawodnika (carrier), albo lezy wolna na kratce."""
    carrier: Player | None = None
    free_pos: Cell | None = None

    @property
    def cell(self) -> Cell:
        if self.carrier is not None:
            return self.carrier.pos
        assert self.free_pos is not None
        return self.free_pos

    @property
    def is_free(self) -> bool:
        return self.carrier is None

    def give_to(self, player: Player) -> None:
        self.carrier = player
        self.free_pos = None

    def release(self, pos: Cell) -> None:
        self.carrier = None
        self.free_pos = pos