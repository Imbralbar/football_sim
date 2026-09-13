from __future__ import annotations
import config as C
from core.field import Field, Cell
from core.entities import Player, Team
from core.geometry import sign
from core.geometry import neighbours   # dopisz do importów na górze pliku


def _occupied(teams: list[Team], ignore: Player) -> set[tuple[int, int]]:
    return {(p.pos.x, p.pos.y)
            for t in teams for p in t.players
            if p is not ignore and not p.is_gk}

def try_move(p: Player, target: Cell, field: Field, teams: list[Team]) -> bool:
    """
    Jeden krok o 1 kratkę w stronę celu. Najpierw próbuje 3 "proste" kandydatury
    (jak dotychczas), a jeśli wszystkie zajęte — szuka dowolnej wolnej kratki
    spośród 8 sąsiadujących, wybierając tę najbliższą celowi. Eliminuje
    gridlock w ciasnej formacji (bez tego zawodnicy potrafili "zamarznąć"
    na wiele akcji, bo trzy pierwotne kandydatury bywały permanentnie zajęte).
    """
    if p.pos == target:
        return False

    occ = _occupied(teams, p)
    dx, dy = sign(target.x - p.pos.x), sign(target.y - p.pos.y)

    primary = [Cell(p.pos.x + dx, p.pos.y + dy),
               Cell(p.pos.x + dx, p.pos.y),
               Cell(p.pos.x, p.pos.y + dy)]

    fallback = sorted(neighbours(p.pos), key=lambda c: Field.distance(c, target))

    for c in primary + fallback:
        c = field.clamp(c)
        if c != p.pos and (c.x, c.y) not in occ:
            p.pos = c
            return True
    return False


def formation_target(p: Player, ball_cell: Cell, field: Field,
                      chase: bool, mark_cell: Cell | None = None) -> Cell:
    """
    Pozycja docelowa zawodnika bez piłki — v2.

    Priorytety:
    1. chase=True       -> biegnij wprost na piłkę (jeden z CHASERS)
    2. mark_cell podany -> ustaw się w cieniu między podopiecznym a własną bramką
    3. formacja v2, rozdzielona na dwie osie:
       - głębokość (x) = dynamic_home.x (już przesunięte wg fazy ATTACK/DEFENSE
         przez core.ai.positioning.compute_dynamic_home)
       - szerokość (y) = home.y + FORMATION_LATERAL_FOLLOW[rola] * (ball.y - home.y)
       - w fazie DEFENSE (poza FWD) dodatkowe ściśnięcie do środka o FORMATION_COMPACTNESS
    """
    if p.is_gk:
        return p.pos
    if chase:
        return ball_cell

    base_home = getattr(p, "dynamic_home", None) or p.home
    assert base_home is not None

    if mark_cell is not None:
        own_goal = field.goal_center(p.side.value)
        sx = mark_cell.x + int((own_goal.x - mark_cell.x) * 0.3)
        sy = mark_cell.y + int((own_goal.y - mark_cell.y) * 0.3)
        return field.clamp(Cell(sx, sy))

    lateral = C.FORMATION_LATERAL_FOLLOW.get(p.role.value, 0.4)
    sy = base_home.y + lateral * (ball_cell.y - base_home.y)

    if getattr(p, "phase", None) == C.PHASE_DEFENSE and p.role.value != "FWD":
        center_y = field.center.y
        sy += (center_y - sy) * C.FORMATION_COMPACTNESS

    return field.clamp(Cell(base_home.x, int(sy)))


def carrier_target(carrier: Player, field: Field) -> Cell:
    """Zawodnik z piłką biegnie na bramkę przeciwnika."""
    goal = field.goal_center(carrier.side.opposite().value)
    return field.clamp(goal)


def pick_chasers(defenders: list[Player], ball_cell: Cell) -> set[int]:
    """
    DEPRECATED — zastąpione przez core.ai.pressing.select_pressers(),
    które dodatkowo filtruje wg PRESS_ROLES, PRESS_TRIGGER_DIST oraz
    karencji (frozen_until / defense_cooldown_until). Zostawione tylko
    dla wstecznej kompatybilności, jeśli coś jeszcze je importuje.
    """
    ranked = sorted(defenders, key=lambda p: Field.distance(p.pos, ball_cell))
    return {id(p) for p in ranked[:C.CHASERS]}