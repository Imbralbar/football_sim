from __future__ import annotations
from typing import TYPE_CHECKING
from dataclasses import dataclass
from enum import IntEnum

if TYPE_CHECKING:
    from core.entities import Team, Player

from core.dice import Rng
from core.events import EventLog
import config as C


class PenaltyDirection(IntEnum):
    """Kierunek strzalu/obrony przy karnym."""
    LEFT = 1    # lewo (z punktu widzenia strzelca)
    CENTER = 2  # srodek
    RIGHT = 3   # prawo


@dataclass
class PenaltyResult:
    """Wynik pojedynczego rzutu karnego."""
    shooter: Player
    goalkeeper: Player
    shot_direction: PenaltyDirection
    gk_direction: PenaltyDirection
    scored: bool         # True = gol, False = obroniony/slupek
    hit_post: bool       # True = trafil w slupek
    saved: bool          # True = bramkarz obronił (kierunki sie pokryly)


@dataclass
class ShootoutResult:
    """Wynik pelnej serii karnych."""
    home_goals: int      # ile karnych strzela home
    away_goals: int      # ile karnych strzela away
    winner: str          # "home" | "away"
    rounds_played: int   # ile rund rozegrano (min 5, max bez limitu)
    penalty_results: list[PenaltyResult]  # szczegoly kazdego karnego


def resolve_penalty(
    shooter: Player,
    goalkeeper: Player,
    shot_direction: PenaltyDirection,
    gk_direction: PenaltyDirection,
    rng: Rng
) -> PenaltyResult:
    """
    Rozstrzyga pojedynczy rzut karny.

    Mechanika:
    1. Jesli shot_direction == gk_direction -> bramkarz broni
       -> scored = False, saved = True, hit_post = False

    2. Jesli shot_direction != gk_direction:
       a) Jesli shot_direction in (LEFT, RIGHT):
          - Losuj 1..100
          - Jesli <= POST_CHANCE (5) -> slupek
            -> scored = False, saved = False, hit_post = True
       b) Jesli nie slupek (lub CENTER):
          -> GOL
          -> scored = True, saved = False, hit_post = False

    Args:
        shooter: strzelec
        goalkeeper: bramkarz
        shot_direction: kierunek strzalu (LEFT/CENTER/RIGHT)
        gk_direction: kierunek skoku GK
        rng: generator losowy

    Returns:
        PenaltyResult z pelnym opisem wyniku

    Uwaga: funkcja NIE modyfikuje stanu gry, tylko zwraca wynik
    """
    # Czy kierunki sie pokrywaja? -> obrona
    if shot_direction == gk_direction:
        return PenaltyResult(
            shooter=shooter,
            goalkeeper=goalkeeper,
            shot_direction=shot_direction,
            gk_direction=gk_direction,
            scored=False,
            hit_post=False,
            saved=True
        )

    # Kierunki sie roznia - sprawdzamy slupek (tylko dla LEFT/RIGHT)
    if shot_direction in (PenaltyDirection.LEFT, PenaltyDirection.RIGHT):
        roll = rng.randint(1, 100)
        if roll <= C.POST_CHANCE:  # 5% szansy
            return PenaltyResult(
                shooter=shooter,
                goalkeeper=goalkeeper,
                shot_direction=shot_direction,
                gk_direction=gk_direction,
                scored=False,
                hit_post=True,
                saved=False
            )

    # Brak obrony, brak slupka -> GOL
    return PenaltyResult(
        shooter=shooter,
        goalkeeper=goalkeeper,
        shot_direction=shot_direction,
        gk_direction=gk_direction,
        scored=True,
        hit_post=False,
        saved=False
    )


def play_shootout(
    home: Team,
    away: Team,
    rng: Rng,
    event_log: EventLog | None = None,
    home_strategy: list[PenaltyDirection] | None = None,
    away_strategy: list[PenaltyDirection] | None = None,
    gk_home_strategy: list[PenaltyDirection] | None = None,
    gk_away_strategy: list[PenaltyDirection] | None = None
) -> ShootoutResult:
    """
    Rozgrywa pelna serie rzutow karnych.

    Zasady:
    1. Kazda druzyna wybiera 5 strzelcow (outfield, numery rosnaco)
    2. Strzelaja na zmiane: home, away, home, away, ...
    3. Po 5 rundach (10 karnych):
       - Jesli roznica > pozostale karne -> koniec (wczesne zwyciestwo)
       - Jesli wynik rozny -> koniec, zwyciezca ustalony
       - Jesli remis -> sudden death (runda po rundzie do pierwszej roznicy)

    Args:
        home: druzyna domowa
        away: druzyna goscinna
        rng: generator losowy
        event_log: opcjonalny log zdarzen (dodaje add_penalty)
        home_strategy: lista kierunkow strzalu dla home (None = losuj)
        away_strategy: lista kierunkow strzalu dla away (None = losuj)
        gk_home_strategy: lista kierunkow skoku GK home (None = losuj)
        gk_away_strategy: lista kierunkow skoku GK away (None = losuj)

    Returns:
        ShootoutResult z wynikiem, zwyciezca, szczegolami

    Strategia:
    - Jesli podana lista (np. home_strategy = [LEFT, CENTER, RIGHT, ...]):
      uzyj kolejnych elementow dla kolejnych strzelcow
    - Jesli None lub lista sie skonczyla -> losuj kierunek (1..3)
    - GK strategy dziala tak samo

    Wybor strzelcow:
    - outfield() zwraca zawodnikow bez bramkarza
    - Sortuj po numerze (2, 3, 4, ..., 11)
    - Pierwsze 5 to podstawowa piatka
    - Jesli sudden death > 5 rund -> powtarzaj liste strzelcow
      (6. karny = znowu gracz nr 2, 7. = nr 3, itd.)

    Wczesne zwyciestwo:
    - Po rundzie X sprawdz: czy lider ma wiecej golow niz
      przeciwnik moze strzelic w pozostalych rundach?
    - Przyklad: po 3 rundach 3-0, pozostaly 2 rundy -> max 2 gole
      -> home wygral, koniec (rounds_played = 3, nie 5)
    """
    # Wybierz strzelcow (5 z pola, sortuj po numerze rosnaco)
    shooters_home = sorted(home.outfield(), key=lambda p: p.number)[:5]
    shooters_away = sorted(away.outfield(), key=lambda p: p.number)[:5]

    gk_home = home.gk()
    gk_away = away.gk()

    home_goals = 0
    away_goals = 0
    penalty_results: list[PenaltyResult] = []
    round_num = 1
    winner = None

    while True:
        # --- Runda: home strzela ---
        shooter_idx_home = (round_num - 1) % len(shooters_home)
        shooter_home = shooters_home[shooter_idx_home]

        # Kierunek strzalu home
        if home_strategy and (round_num - 1) < len(home_strategy):
            shot_dir_home = home_strategy[round_num - 1]
        else:
            shot_dir_home = PenaltyDirection(rng.randint(1, 3))

        # Kierunek obrony GK away
        if gk_away_strategy and (round_num - 1) < len(gk_away_strategy):
            gk_dir_away = gk_away_strategy[round_num - 1]
        else:
            gk_dir_away = PenaltyDirection(rng.randint(1, 3))

        # Rozstrzygnij karny
        result_home = resolve_penalty(
            shooter_home, gk_away,
            shot_dir_home, gk_dir_away,
            rng
        )
        penalty_results.append(result_home)

        if result_home.scored:
            home_goals += 1

        # Log zdarzen
        if event_log:
            event_log.add_penalty(
                round=round_num,
                shooter=shooter_home,
                direction=shot_dir_home.name,
                gk_direction=gk_dir_away.name,
                scored=result_home.scored,
                hit_post=result_home.hit_post
            )

        # --- Runda: away strzela ---
        shooter_idx_away = (round_num - 1) % len(shooters_away)
        shooter_away = shooters_away[shooter_idx_away]

        # Kierunek strzalu away
        if away_strategy and (round_num - 1) < len(away_strategy):
            shot_dir_away = away_strategy[round_num - 1]
        else:
            shot_dir_away = PenaltyDirection(rng.randint(1, 3))

        # Kierunek obrony GK home
        if gk_home_strategy and (round_num - 1) < len(gk_home_strategy):
            gk_dir_home = gk_home_strategy[round_num - 1]
        else:
            gk_dir_home = PenaltyDirection(rng.randint(1, 3))

        # Rozstrzygnij karny
        result_away = resolve_penalty(
            shooter_away, gk_home,
            shot_dir_away, gk_dir_home,
            rng
        )
        penalty_results.append(result_away)

        if result_away.scored:
            away_goals += 1

        # Log zdarzen
        if event_log:
            event_log.add_penalty(
                round=round_num,
                shooter=shooter_away,
                direction=shot_dir_away.name,
                gk_direction=gk_dir_home.name,
                scored=result_away.scored,
                hit_post=result_away.hit_post
            )

        # --- Sprawdzenie warunkow zakonczenia PO PEŁNEJ RUNDZIE ---
        
        # Wczesne zwyciestwo (sprawdzaj zawsze od rundy 1)
        remaining_rounds = 5 - round_num
        if remaining_rounds >= 0:
            # Czy home juz niemozliwie sie straci?
            if home_goals > away_goals + remaining_rounds:
                winner = "home"
                break
            # Czy away juz niemozliwie sie straci?
            if away_goals > home_goals + remaining_rounds:
                winner = "away"
                break

        # Po dokladnie 5 rundach
        if round_num == 5:
            if home_goals != away_goals:
                # Rozne wyniki -> koniec (nie idziemy do sudden death)
                winner = "home" if home_goals > away_goals else "away"
                break
            # else: remis 5-5 -> sudden death (kontynuuj do rundy 6+)

        # W sudden death (round_num > 5): jesli rozne wyniki -> koniec
        if round_num > 5 and home_goals != away_goals:
            winner = "home" if home_goals > away_goals else "away"
            break

        round_num += 1

    return ShootoutResult(
        home_goals=home_goals,
        away_goals=away_goals,
        winner=winner,
        rounds_played=round_num,
        penalty_results=penalty_results
    )