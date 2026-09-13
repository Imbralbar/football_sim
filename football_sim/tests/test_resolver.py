"""Testy rozstrzygania starc.

Rzuty k10 sa wymuszane przez StubRng (lista zadanych wartosci),
a statystyki przez monkeypatch funkcji pobierajacych staty w module
resolver - dzieki temu testy sprawdzaja WYLACZNIE logike rozstrzygania
i sa niezalezne od konwencji kluczy w Player.stats.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

import pytest

from core import resolver
from core.actions import AttackAction, DefenceAction, DuelContext, GkAction, ShotPlacement
from core.resolver import (
    Outcome,
    resolve_air_interception,
    resolve_gk_save,
    resolve_ground_duel,
)


# --------------------------------------------------------------------------
# narzedzia testowe
# --------------------------------------------------------------------------
class StubRng:
    """Rng zwracajacy zadana liste wartosci; liczy zuzyte rzuty."""

    def __init__(self, values: list[int]) -> None:
        self._values = list(values)
        self.rolls_made = 0

    def roll(self) -> int:
        if self.rolls_made >= len(self._values):
            raise AssertionError("wykonano wiecej rzutow niz przewidziano")
        value = self._values[self.rolls_made]
        self.rolls_made += 1
        return value


class SeededRng:
    """Deterministyczny Rng na bazie random.Random - do testu powtarzalnosci."""

    def __init__(self, seed: int) -> None:
        self._rnd = random.Random(seed)
        self.rolls_made = 0

    def roll(self) -> int:
        self.rolls_made += 1
        return self._rnd.randint(1, 10)


@dataclass
class StubPlayer:
    """Minimalny zamiennik Player - resolver uzywa tylko .number i .is_gk."""

    number: int
    is_gk: bool = False


@pytest.fixture
def stats(monkeypatch):
    """Wymusza staly odczyt statystyk: atak 15, obrona 15, bramkarz 20."""
    values = {"attack": 15, "defence": 15, "gk": 20}
    monkeypatch.setattr(resolver, "get_attack_stat", lambda p, a: values["attack"])
    monkeypatch.setattr(resolver, "get_defence_stat", lambda p, d: values["defence"])
    monkeypatch.setattr(resolver, "get_gk_stat", lambda p, a: values["gk"])
    return values


@pytest.fixture
def attacker() -> StubPlayer:
    return StubPlayer(number=10)


@pytest.fixture
def defender() -> StubPlayer:
    return StubPlayer(number=4)


@pytest.fixture
def keeper() -> StubPlayer:
    return StubPlayer(number=1, is_gk=True)


# --------------------------------------------------------------------------
# 1-4. GROUND
# --------------------------------------------------------------------------
def test_01_ground_paired_bez_kary(stats, attacker, defender):
    """Sparowanie DRIBBLE(5) <-> VS_DRIBBLE(2) nie daje kary."""
    rng = StubRng([7, 3])
    result = resolve_ground_duel(
        attacker, defender, AttackAction.DRIBBLE, DefenceAction.VS_DRIBBLE, rng
    )
    assert result.mismatch_penalty == 0
    assert result.context == DuelContext.GROUND
    assert result.context_bonus == 0
    assert result.defence_total == 15 + 3


def test_02_ground_mismatch_kara_minus_6(stats, attacker, defender):
    """DRIBBLE(5) vs VS_SHOT(3) - brak sparowania -> -6 dla obroncy."""
    rng = StubRng([7, 3])
    result = resolve_ground_duel(
        attacker, defender, AttackAction.DRIBBLE, DefenceAction.VS_SHOT, rng
    )
    assert result.mismatch_penalty == -6
    assert result.defence_total == 15 + 3 - 6


def test_03_ground_remis_dla_atakujacego(stats, attacker, defender):
    """GROUND: remis w totalach -> wygrywa atakujacy, was_tie zapamietane."""
    rng = StubRng([5, 5])  # 15+5=20 vs 15+5=20
    result = resolve_ground_duel(
        attacker, defender, AttackAction.PASS, DefenceAction.VS_PASS, rng
    )
    assert result.attack_total == result.defence_total == 20
    assert result.was_tie is True
    assert result.attacker_wins is True
    assert result.outcome == Outcome.PASS_COMPLETED


def test_04_ground_remis_przy_dryblingu_to_keep_ball(stats, attacker, defender):
    """Remis przy DRIBBLE: pilka zostaje, ale obronca NIE zostal miniety."""
    rng = StubRng([5, 5])
    result = resolve_ground_duel(
        attacker, defender, AttackAction.DRIBBLE, DefenceAction.VS_DRIBBLE, rng
    )
    assert result.was_tie is True
    assert result.attacker_wins is True
    assert result.outcome == Outcome.KEEP_BALL
    assert result.outcome != Outcome.BEAT_DEFENDER


# --------------------------------------------------------------------------
# 5-8. AIR
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "attack, defence",
    [
        (AttackAction.PASS, DefenceAction.VS_PASS),   # sparowane
        (AttackAction.PASS, DefenceAction.VS_SHOT),   # niesparowane
        (AttackAction.SHOT, DefenceAction.VS_SHOT),   # sparowane
        (AttackAction.SHOT, DefenceAction.VS_DRIBBLE),  # niesparowane
    ],
)
def test_05_air_zawsze_bonus_3(stats, attacker, defender, attack, defence):
    """AIR: obronca zawsze dostaje +3, niezaleznie od sparowania."""
    rng = StubRng([6, 6])
    result = resolve_air_interception(attacker, defender, attack, defence, rng)
    assert result.context == DuelContext.AIR
    assert result.context_bonus == 3


def test_06_air_remis_dla_obroncy(stats, attacker, defender):
    """AIR: remis w totalach -> wygrywa obronca (przechwyt)."""
    rng = StubRng([8, 5])  # 15+8=23 vs 15+5+3=23
    result = resolve_air_interception(
        attacker, defender, AttackAction.PASS, DefenceAction.VS_PASS, rng
    )
    assert result.attack_total == result.defence_total == 23
    assert result.was_tie is True
    assert result.attacker_wins is False
    assert result.outcome == Outcome.PASS_INTERCEPTED


def test_07_air_attack_value_nadpisuje_stat(stats, attacker, defender):
    """attack_value nadpisuje statystyke ataku (np. shot_value())."""
    stats["attack"] = 99  # gdyby resolver czytal stat, test by tego dowiodl
    rng = StubRng([4, 4])
    result = resolve_air_interception(
        attacker, defender, AttackAction.SHOT, DefenceAction.VS_SHOT, rng,
        attack_value=15,
    )
    assert result.attack_stat == 15
    assert result.attack_total == 15 + 4


def test_08_air_dribble_rzuca_valueerror(stats, attacker, defender):
    """Drybling nie moze byc przechwycony w powietrzu."""
    rng = StubRng([4, 4])
    with pytest.raises(ValueError):
        resolve_air_interception(
            attacker, defender, AttackAction.DRIBBLE, DefenceAction.VS_DRIBBLE, rng
        )


# --------------------------------------------------------------------------
# 9-11. bramkarz
# --------------------------------------------------------------------------
def test_09_gk_gol_gdy_strzelec_przebija(stats, attacker, keeper):
    """15+10=25 vs 20+4=24 przy sparowaniu -> GOAL."""
    rng = StubRng([10, 4])
    result = resolve_gk_save(
        attacker, keeper, shot_value=15,
        placement=ShotPlacement.POWER, gk_choice=GkAction.PUNCH, rng=rng,
    )
    assert result.mismatch_penalty == 0
    assert result.context_bonus == 0  # brak AIR_INTERCEPT_BONUS dla GK
    assert (result.attack_total, result.defence_total) == (25, 24)
    assert result.attacker_wins is True
    assert result.outcome == Outcome.GOAL


def test_10_gk_remis_catch_vs_punch(stats, attacker, keeper):
    """Remis: CATCH -> SAVE_LOOSE (nie lapie przy 9), PUNCH -> SAVE_PUNCHED."""
    rng_catch = StubRng([10, 5])  # 15+10=25 vs 20+5=25
    caught = resolve_gk_save(
        attacker, keeper, shot_value=15,
        placement=ShotPlacement.PLACED, gk_choice=GkAction.CATCH, rng=rng_catch,
    )
    assert caught.was_tie is True
    assert caught.attacker_wins is False
    assert caught.outcome == Outcome.SAVE_LOOSE

    rng_punch = StubRng([10, 5])
    punched = resolve_gk_save(
        attacker, keeper, shot_value=15,
        placement=ShotPlacement.POWER, gk_choice=GkAction.PUNCH, rng=rng_punch,
    )
    assert punched.was_tie is True
    assert punched.attacker_wins is False
    assert punched.outcome == Outcome.SAVE_PUNCHED


def test_11_gk_save_wymaga_bramkarza(stats, attacker, defender):
    """Zawodnik z pola nie moze bronic strzalu jako bramkarz."""
    rng = StubRng([5, 5])
    with pytest.raises(ValueError):
        resolve_gk_save(
            attacker, defender, shot_value=15,
            placement=ShotPlacement.POWER, gk_choice=GkAction.PUNCH, rng=rng,
        )


# --------------------------------------------------------------------------
# 12-13. powtarzalnosc i budzet rzutow
# --------------------------------------------------------------------------
def test_12_determinizm_dla_tego_samego_seeda(stats, attacker, defender):
    """Ten sam seed + te same argumenty -> identyczny DuelResult."""
    first = resolve_ground_duel(
        attacker, defender, AttackAction.DRIBBLE, DefenceAction.VS_DRIBBLE,
        SeededRng(1234),
    )
    second = resolve_ground_duel(
        attacker, defender, AttackAction.DRIBBLE, DefenceAction.VS_DRIBBLE,
        SeededRng(1234),
    )
    assert first == second
    assert first.describe() == second.describe()


def test_13_dokladnie_dwa_rzuty_na_rozstrzygniecie(stats, attacker, defender, keeper):
    """Kazde rozstrzygniecie zuzywa dokladnie 2 rzuty: atak, potem obrona."""
    ground_rng = StubRng([9, 2])
    ground = resolve_ground_duel(
        attacker, defender, AttackAction.PASS, DefenceAction.VS_PASS, ground_rng
    )
    assert ground_rng.rolls_made == 2
    assert (ground.attack_roll, ground.defence_roll) == (9, 2)

    air_rng = StubRng([9, 2])
    air = resolve_air_interception(
        attacker, defender, AttackAction.PASS, DefenceAction.VS_PASS, air_rng
    )
    assert air_rng.rolls_made == 2
    assert (air.attack_roll, air.defence_roll) == (9, 2)

    gk_rng = StubRng([9, 2])
    save = resolve_gk_save(
        attacker, keeper, shot_value=15,
        placement=ShotPlacement.PLACED, gk_choice=GkAction.CATCH, rng=gk_rng,
    )
    assert gk_rng.rolls_made == 2
    assert (save.attack_roll, save.defence_roll) == (9, 2)