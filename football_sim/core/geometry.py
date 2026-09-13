from __future__ import annotations
from core.field import Cell


def line(a: Cell, b: Cell) -> list[Cell]:
    """Linia prosta Bresenhama - trajektoria podania i strzalu.
    Zwraca kratki OD a DO b wlacznie."""
    x0, y0, x1, y1 = a.x, a.y, b.x, b.y
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    out: list[Cell] = []
    while True:
        out.append(Cell(x0, y0))
        if x0 == x1 and y0 == y1:
            return out
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x0 += sx
        if e2 < dx:
            err += dx
            y0 += sy


def neighbours(c: Cell) -> list[Cell]:
    """8 kratek stycznych."""
    return [Cell(c.x + dx, c.y + dy)
            for dx in (-1, 0, 1) for dy in (-1, 0, 1)
            if not (dx == 0 and dy == 0)]


def sign(v: int) -> int:
    return (v > 0) - (v < 0)