from __future__ import annotations
from core.field import Field, Cell
from core.entities import Player, Team, Role, Side
from core.ball import Ball

# 4-4-2 dla druzyny grajacej w PRAWO (Side.LEFT broni lewej bramki)
_LAYOUT = {
    Role.DEF: (4,  [2, 6, 10, 14], [2, 3, 4, 5]),
    Role.MID: (9,  [2, 6, 10, 14], [6, 7, 8, 9]),
    Role.FWD: (11, [6, 10],        [10, 11]),
}


def build_442(field: Field, name: str, side: Side, color_key: str) -> Team:
    players: list[Player] = []
    mirror = (side is Side.RIGHT)

    def mx(x: int) -> int:
        return (field.w - 1 - x) if mirror else x

    players.append(Player(1, Role.GK, field.goal_center(side.value), side))

    for role, (x, rows, numbers) in _LAYOUT.items():
        for num, y in zip(numbers, rows):
            c = Cell(mx(x), y)
            players.append(Player(num, role, c, side, home=c))

    return Team(name=name, side=side, color_key=color_key, players=players)


def kickoff(field: Field, kicking: Team) -> Ball:
    """Pilke posiada zawodnik nr 10, stoi na srodku boiska (pkt 4.1)."""
    striker = kicking.by_number(10)
    striker.pos = field.center

    partner = kicking.by_number(11)
    dx = -1 if kicking.side is Side.LEFT else 1
    partner.pos = Cell(field.center.x + dx, field.center.y + 2)

    ball = Ball()
    ball.give_to(striker)
    return ball