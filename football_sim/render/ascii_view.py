from __future__ import annotations

from core.field import Field, Cell
from core.state import GameState
from core.entities import Team, Player, Side
from core.ball import Ball
import config as C


class AsciiView:
    """Renderer ASCII - wypisuje boisko w terminalu."""

    def __init__(self, field: Field):
        """field: geometria boiska (25x17)."""
        self.field = field

    def render(self, state: GameState) -> str:
        """
        Zwraca wieloliniowy string - snapshot boiska.

        Format:
        - Linia 1: nagłówek z akcją, tickiem, nr piłki
        - Linie 2..(h+1): boisko (w x h kratek)
        - Ostatnia linia: info o starciu (jeśli pending_duel())

        Znaki na boisku:
        - '.' = pusta kratka
        - cyfra 1-11 = zawodnik drużyny A (home, LEFT)
        - cyfra 1-11 = zawodnik drużyny B (away, RIGHT)
        - 'o' = piłka wolna LUB piłka u zawodnika (zakrywa numer)
        """
        lines = []

        # === NAGŁÓWEK ===
        ball_info = "wolna"
        if state.ball.carrier:
            ball_info = f"nr {state.ball.carrier.number} ({state.ball.carrier.side.name})"
        
        header = (
            f"Akcja {state.action_no:2d}' tick {state.tick:2d}/36 | "
            f"piłka: {ball_info} | {state.home.name} vs {state.away.name}"
        )
        lines.append(header)

        # === BOISKO ===
        # Zainicjalizuj siatką
        grid = [['.' for _ in range(self.field.w)] for _ in range(self.field.h)]

        # Umieść zawodników
        for team in [state.home, state.away]:
            for player in team.players:
                x, y = player.pos.x, player.pos.y
                if self.field.inside(player.pos):
                    # Sprawdź, czy gracz ma piłkę
                    if state.ball.carrier == player:
                        grid[y][x] = C.BALL_GLYPH  # 'o'
                    else:
                        grid[y][x] = str(player.number)

        # Umieść wolną piłkę (jeśli nie ma carrier)
        if state.ball.is_free:
            x, y = state.ball.cell.x, state.ball.cell.y
            if self.field.inside(state.ball.cell):
                grid[y][x] = C.BALL_GLYPH  # 'o'

        # Opcjonalnie: zaznacz znaczniki pola (linie poziome/pionowe)
        # Dla uproszczenia: rysujemy '+' na środkowej linii
        mid_x = self.field.w // 2
        for y in range(self.field.h):
            if grid[y][mid_x] == '.':
                grid[y][mid_x] = '+'

        # Konwertuj grid na string
        for row in grid:
            lines.append(''.join(row))

        # === INFO O STARCIU ===
        duel_player = state.pending_duel()
        if duel_player:
            lines.append(f">>> STARCIE: zawodnik nr {duel_player.number} ({duel_player.side.name}) "
                        f"[contact_ticks: {duel_player.contact_ticks}]")

        return '\n'.join(lines)

    def print_state(self, state: GameState) -> None:
        """Wypisz render(state) na stdout + pusta linia."""
        print(self.render(state))
        print()

    def run_interactive(self, state: GameState) -> None:
        """
        Pętla interaktywna w terminalu (bez curses).

        Komendy:
        - '' (ENTER) -> step_tick(), wypisz nowy stan
        - 'a' -> całą akcję (36 ticków), wypisz końcowy stan
        - 'q' -> wyjście
        """
        while True:
            # Czyszczenie ekranu
            print('\n' * 50)
            
            # Wypisz aktualny stan
            print(self.render(state))
            print()

            # Poproś o komendę
            try:
                cmd = input("Komenda (ENTER=tick, 'a'=akcja, 'q'=wyjście): ").strip().lower()
            except EOFError:
                # Koniec strumienia wejścia (np. w testach)
                break

            if cmd == 'q':
                break
            elif cmd == 'a':
                # Całą akcję (36 ticków)
                for _ in range(C.TICKS_PER_ACTION):
                    state.step_tick()
            elif cmd == '':
                # Jeden tick
                state.step_tick()
            else:
                print("Nieznana komenda. Spróbuj jeszcze raz.")
                continue