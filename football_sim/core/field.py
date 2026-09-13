from __future__ import annotations
from dataclasses import dataclass
import config as C


@dataclass(frozen=True)
class Cell:
    x: int
    y: int


@dataclass(frozen=True)
class Field:
    w: int = C.FIELD_W
    h: int = C.FIELD_H

    @property
    def center(self) -> Cell:
        return Cell(self.w // 2, self.h // 2)

    def inside(self, c: Cell) -> bool:
        return 0 <= c.x < self.w and 0 <= c.y < self.h

    def clamp(self, c: Cell) -> Cell:
        return Cell(max(0, min(self.w - 1, c.x)),
                    max(0, min(self.h - 1, c.y)))

    # ---------- strefy ----------
    def _band(self, size: int) -> range:
        start = (self.h - size) // 2
        return range(start, start + size)

    def penalty_rows(self) -> range:
        return self._band(C.PENALTY_H)

    def goal_area_rows(self) -> range:
        return self._band(C.GOAL_AREA_H)

    def goal_rows(self) -> range:
        return self._band(C.GOAL_H)

    def in_penalty_area(self, c: Cell, side: str) -> bool:
        if c.y not in self.penalty_rows():
            return False
        return c.x < C.PENALTY_DEPTH if side == "LEFT" \
            else c.x >= self.w - C.PENALTY_DEPTH

    def goal_center(self, side: str) -> Cell:
        return Cell(-1 if side == "LEFT" else self.w, self.h // 2)

    # ---------- metryka ----------
    @staticmethod
    def distance(a: Cell, b: Cell) -> int:
        """Chebyshev - ruch 8-kierunkowy, 1 kratka = 1 krok."""
        return max(abs(a.x - b.x), abs(a.y - b.y))

    def distance_to_goal(self, c: Cell, side: str) -> int:
        return self.distance(c, self.goal_center(side))