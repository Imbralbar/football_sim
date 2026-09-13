from __future__ import annotations

from typing import TYPE_CHECKING
from dataclasses import dataclass, asdict
import json
from pathlib import Path

if TYPE_CHECKING:
    from core.match import MatchResult
    from core.state import GameState


@dataclass
class TickSnapshot:
    """Snapshot stanu gry w jednym ticku."""
    action: int              # numer akcji (minuty) 1..120
    tick: int                # numer ticku w akcji 0..35
    ball_x: int              # pozycja pilki
    ball_y: int
    ball_carrier_number: int | None  # numer zawodnika z pilka (lub None)
    ball_carrier_side: str | None    # "LEFT" | "RIGHT" (lub None)
    players: list[dict]      # lista {"number": 10, "x": 12, "y": 8,
                             #        "side": "LEFT", "role": "FWD"}
                             # dla WSZYSTKICH 22 zawodnikow


@dataclass
class ReplayData:
    """Kompletny zapis meczu do odtworzenia w Unity/Godot."""

    # METADANE
    home_name: str
    away_name: str
    final_score_home: int
    final_score_away: int
    winner: str | None          # "home" | "away" | None
    total_actions: int          # ile akcji rozegrano (90, 120, ...)
    rng_seed: int               # seed RNG (do debugowania)

    # SNAPSHOTY (lista tickow)
    ticks: list[TickSnapshot]

    # ZDARZENIA (z EventLog)
    events: list[dict]          # z EventLog.to_json() -> json.loads()

    # FINALNE POZYCJE ZAWODNIKOW (opcjonalne, duplikat ostatniego ticka)
    final_players: list[dict]


def capture_tick(state: GameState) -> TickSnapshot:
    """
    Robi snapshot aktualnego stanu gry (1 tick).

    Args:
        state: aktualny GameState

    Returns:
        TickSnapshot z pozycjami wszystkich zawodnikow i pilki

    Uwaga: wywolywane PRZED state.step_tick() w match.py
    (albo PO, zalezne od implementacji - konsystencja wazniejsza)
    """
    # Zbierz pozycje wszystkich zawodnikow
    players_data = []
    for team in [state.home, state.away]:
        for player in team.players:
            players_data.append({
                "number": player.number,
                "x": player.pos.x,
                "y": player.pos.y,
                "side": player.side.value,  # "LEFT" | "RIGHT"
                "role": player.role.value   # "GK" | "DEF" | "MID" | "FWD"
            })

    # Pozycja pilki i jej nosiciel
    ball_carrier_number = None
    ball_carrier_side = None
    if state.ball.carrier is not None:
        ball_carrier_number = state.ball.carrier.number
        ball_carrier_side = state.ball.carrier.side.value

    return TickSnapshot(
        action=state.action_no,
        tick=state.tick,
        ball_x=state.ball.cell.x,
        ball_y=state.ball.cell.y,
        ball_carrier_number=ball_carrier_number,
        ball_carrier_side=ball_carrier_side,
        players=players_data
    )


def create_replay_data(
    match_result: MatchResult,
    tick_history: list[TickSnapshot],
    rng_seed: int
) -> ReplayData:
    """
    Buduje strukture ReplayData z wynikow meczu.

    Args:
        match_result: wynik z Match.play()
        tick_history: lista TickSnapshot
        rng_seed: seed

    Returns:
        ReplayData gotowe do JSON
    """
    # Rozpakuj eventy z EventLog
    events_list = json.loads(match_result.events.to_json())

    # Ostatnie pozycje zawodnikow (duplikat ostatniego ticka)
    final_players = tick_history[-1].players if tick_history else []

    return ReplayData(
        home_name=match_result.final_state.home.name,
        away_name=match_result.final_state.away.name,
        final_score_home=match_result.home_score,
        final_score_away=match_result.away_score,
        winner=match_result.winner,
        total_actions=match_result.total_actions,
        rng_seed=rng_seed,
        ticks=tick_history,
        events=events_list,
        final_players=final_players
    )


def export_replay(
    match_result: MatchResult,
    tick_history: list[TickSnapshot],
    rng_seed: int,
    output_path: str | Path
) -> None:
    """
    Eksportuje pelny mecz do JSON.

    Args:
        match_result: wynik z Match.play()
        tick_history: lista TickSnapshot z calego meczu
        rng_seed: seed RNG uzyte w meczu
        output_path: sciezka do pliku .json

    Tworzy ReplayData i zapisuje jako JSON z wcieciami (indent=2).
    Plik moze byc duzy (90 akcji * 36 tickow * ~30 zawodnikow = ~100k linii).
    """
    output_path = Path(output_path)

    # Upewnij sie, ze folder istnieje
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Buduj dane
    replay = create_replay_data(match_result, tick_history, rng_seed)

    # Zapisz do JSON
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(asdict(replay), f, indent=2, ensure_ascii=False)


def load_replay(input_path: str | Path) -> ReplayData:
    """
    Wczytuje replay z pliku JSON.

    Args:
        input_path: sciezka do .json

    Returns:
        ReplayData odtworzone z JSON

    Rzuca FileNotFoundError, json.JSONDecodeError w razie bledow.
    """
    input_path = Path(input_path)

    if not input_path.exists():
        raise FileNotFoundError(f"Plik replay nie istnieje: {input_path}")

    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Konwersja dict -> TickSnapshot dataclass
    ticks = [TickSnapshot(**t) for t in data['ticks']]

    # Zwroc ReplayData
    return ReplayData(
        home_name=data['home_name'],
        away_name=data['away_name'],
        final_score_home=data['final_score_home'],
        final_score_away=data['final_score_away'],
        winner=data['winner'],
        total_actions=data['total_actions'],
        rng_seed=data['rng_seed'],
        ticks=ticks,
        events=data['events'],
        final_players=data['final_players']
    )