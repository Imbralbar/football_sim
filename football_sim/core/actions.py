from __future__ import annotations

from enum import IntEnum, Enum
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.entities import Player
    from core.field import Field

import config as C


class AttackAction(IntEnum):
    """Akcje ataku dostepne dla gracza z pilka."""
    DRIBBLE = 5
    SHOT = 6
    PASS = 7


class DefenceAction(IntEnum):
    """Akcje obrony dostepne dla obroniajacego gracza."""
    VS_DRIBBLE = 2
    VS_SHOT = 3
    VS_PASS = 4


class GkAction(IntEnum):
    """Akcje dostepne dla bramkarza."""
    PUNCH = 8
    CATCH = 9


class ShotPlacement(IntEnum):
    """Typ umieszczenia strzalu."""
    POWER = 8      # mocny -> paruje z PUNCH
    PLACED = 9     # umieszczony -> paruje z CATCH


class DuelContext(str, Enum):
    """Kontekst starcia (przy nodze vs w powietrzu)."""
    GROUND = "GROUND"  # pilka przy nodze - przewaga atakujacego
    AIR = "AIR"        # pilka w powietrzu - przewaga obroncy


def counters(defence: DefenceAction) -> AttackAction:
    """
    Zwraca akcje ataku, ktora dana obrona paruje.
    
    Uzywa C.PAIRS: 2<->5, 3<->6, 4<->7.
    Rzuca ValueError gdy defence nie jest prawidlowa obrona.
    """
    if defence not in C.PAIRS:
        raise ValueError(f"Nieznana akcja obrony: {defence}")
    return AttackAction(C.PAIRS[defence])


def is_paired(attack: AttackAction, defence: DefenceAction) -> bool:
    """
    True gdy obrona jest sparowana z akcja ataku (brak kary -6).
    """
    try:
        return counters(defence) == attack
    except ValueError:
        return False

def attack_stat(p: Player, action: AttackAction) -> int:
    """
    DRIBBLE -> stats['dribble'] (dla bramkarza: C.GK_DRIBBLE_STAT — v0.6, drybling po obronie)
    SHOT    -> stats['shot']
    PASS    -> stats['passing']

    Rzuca ValueError gdy gracz jest bramkarzem i action == SHOT
    (bramkarz nigdy nie oddaje strzału z gry).
    """
    if p.is_gk:
        if action == AttackAction.SHOT:
            raise ValueError("Bramkarz nie moze wykonywac akcji SHOT")
        if action == AttackAction.DRIBBLE:
            return C.GK_DRIBBLE_STAT

    mapping = {
        AttackAction.DRIBBLE: 'dribble',
        AttackAction.SHOT: 'shot',
        AttackAction.PASS: 'passing',
    }
    return p.stats[mapping[action]]


def defence_stat(p: Player, defence: DefenceAction) -> int:
    """
    Zwraca statystyke obrony dla gracza i akcji.
    
    VS_DRIBBLE -> stats['d_dribble']
    VS_SHOT -> stats['d_shot']
    VS_PASS -> stats['d_pass']
    
    Rzuca ValueError gdy gracz jest bramkarzem.
    """
    if p.is_gk:
        raise ValueError("Bramkarz nie moze wykonywac klasycznej obrony")
    
    mapping = {
        DefenceAction.VS_DRIBBLE: 'd_dribble',
        DefenceAction.VS_SHOT: 'd_shot',
        DefenceAction.VS_PASS: 'd_pass',
    }
    stat_key = mapping[defence]
    return p.stats[stat_key]


def gk_stat(p: Player, action: GkAction) -> int:
    """
    Zwraca statystyke bramkarza dla akcji.
    
    PUNCH -> stats['punch']
    CATCH -> stats['catch']
    
    Rzuca ValueError gdy gracz nie jest bramkarzem.
    """
    if not p.is_gk:
        raise ValueError(f"Gracz {p.number} nie jest bramkarzem")
    
    mapping = {
        GkAction.PUNCH: 'punch',
        GkAction.CATCH: 'catch',
    }
    stat_key = mapping[action]
    return p.stats[stat_key]


def shot_value(field: Field, shooter: Player) -> int:
    """
    Wartość strzału. W polu karnym = 15, poza nim: stats['shot'] - kratki poza polem.

    Bonus jednorazowy (v0.6): jeśli shooter.shot_bonus_mult != 1.0
    (np. po odebraniu piłki bramkarzowi w trakcie dryblingu), wynik jest
    przez niego mnożony. Reset mnożnika po użyciu leży po stronie match.py.
    """
    opp_side = shooter.side.opposite().value

    if field.in_penalty_area(shooter.pos, opp_side):
        base = 15
    else:
        distance = field.distance_to_goal(shooter.pos, opp_side)
        cells_outside = max(0, distance - C.PENALTY_DEPTH)
        base = max(0, shooter.stats['shot'] - cells_outside)

    bonus_mult = getattr(shooter, "shot_bonus_mult", 1.0)
    return max(0, round(base * bonus_mult))