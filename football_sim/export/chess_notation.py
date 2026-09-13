"""
export/chess_notation.py – kompaktowy, czytelny dla człowieka/AI zapis meczu.

Format zaprojektowany do analizy AI (nie do odtwarzania graficznego —
do tego służy export/replay.py + JSON). Docelowo plik .cn ma być
transponowalny do TickSnapshot/JSON, ale to osobny krok (nie teraz).

Zasady:
- Komórka = 2 znaki (litera x, litera y) zamiast {"x":.., "y":..}
- Zapisywane są TYLKO zmiany pozycji względem poprzedniego znanego stanu
- CT: (contact_ticks) logowane tylko gdy > 0 lub gdy spada do 0
  (sygnał diagnostyczny do debugowania dueli)
- Zdarzenia (DEC/DUEL/SHOT/PASS/GOAL) logowane 1:1 z eventami meczu
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.state import GameState
    from core.entities import Player

from core.field import Cell


def encode_cell(c: Cell) -> str:
    return chr(ord('a') + c.x) + chr(ord('a') + c.y)


def decode_cell(code: str) -> Cell:
    return Cell(ord(code[0]) - ord('a'), ord(code[1]) - ord('a'))


def _pid(p: "Player") -> str:
    prefix = "h" if p.side.value == "LEFT" else "a"  # UWAGA: zamień na team_of, patrz niżej
    return f"{prefix}{p.number}"


@dataclass
class ChessNotation:
    """Nagrywa mecz w formacie .cn. Trzyma tylko ostatnie znane pozycje/CT
    do wyliczania delt — nie trzyma pełnej historii w pamięci."""

    lines: list[str] = field(default_factory=list)
    _last_pos: dict[str, str] = field(default_factory=dict)
    _last_ct: dict[str, int] = field(default_factory=dict)
    _last_action: int = -1

    # ---------------- nagłówek ----------------

    def write_header(self, state: "GameState", seed: int) -> None:
        f = state.field
        self.lines.append("# FOOTBALL SIM — chess notation v1")
        self.lines.append(f"FIELD {f.w}x{f.h}")
        self.lines.append(f"SEED {seed}")
        self.lines.append("")

        init_home = " ".join(
            f"{_pid_for(state, p)}={encode_cell(p.pos)}" for p in state.home.players
        )
        init_away = " ".join(
            f"{_pid_for(state, p)}={encode_cell(p.pos)}" for p in state.away.players
        )
        self.lines.append(f"INIT {init_home}")
        self.lines.append(f"INIT {init_away}")

        for p in state.home.players + state.away.players:
            self._last_pos[_pid_for(state, p)] = encode_cell(p.pos)
            self._last_ct[_pid_for(state, p)] = 0

        if state.ball.carrier is not None:
            self.lines.append(f"BALL {_pid_for(state, state.ball.carrier)}")
        self.lines.append("")

    # ---------------- per-tick ----------------

    def record_tick(self, state: "GameState") -> None:
        changed: list[str] = []

        if state.action_no != self._last_action:
            if self._last_action != -1:
                pass  # END dopisywane osobno przez record_action_end()
            self.lines.append(f"A{state.action_no}")
            self._last_action = state.action_no

        for p in state.home.players + state.away.players:
            pid = _pid_for(state, p)
            code = encode_cell(p.pos)
            piece = ""
            if self._last_pos.get(pid) != code:
                piece += f"{pid}={code}"
                self._last_pos[pid] = code

            ct = p.contact_ticks
            last_ct = self._last_ct.get(pid, 0)
            if ct != last_ct and (ct > 0 or last_ct > 0):
                piece += (" " if piece else "") + f"CT:{pid}={ct}"
                self._last_ct[pid] = ct

            if piece:
                changed.append(piece)

        if changed:
            self.lines.append(f"T{state.tick} " + " ".join(changed))

    # ---------------- zdarzenia ----------------

    def record_decision(self, carrier: "Player", state: "GameState",
                         decision: str, target: "Player | None" = None) -> None:
        pid = _pid_for(state, carrier)
        line = f"DEC {pid} {decision}"
        if target is not None:
            line += f">{_pid_for(state, target)}"
        self.lines.append(line)

    def record_duel(self, state: "GameState", attacker: "Player", defender: "Player",
                     attack_total: int, defence_total: int, attacker_wins: bool) -> None:
        a_pid = _pid_for(state, attacker)
        d_pid = _pid_for(state, defender)
        winner = a_pid if attacker_wins else d_pid
        self.lines.append(
            f"DUEL {a_pid}v{d_pid} ATK={attack_total} DEF={defence_total} WIN={winner}"
        )

    def record_shot(self, state: "GameState", shooter: "Player",
                     shot_value: int, result: str) -> None:
        pid = _pid_for(state, shooter)
        self.lines.append(f"SHOT {pid} VAL={shot_value} {result}")

    def record_pass(self, state: "GameState", passer: "Player", target: "Player",
                     result: str) -> None:
        self.lines.append(
            f"PASS {_pid_for(state, passer)}>{_pid_for(state, target)} {result}"
        )

    def record_action_end(self, action_no: int, home_score: int, away_score: int) -> None:
        self.lines.append(f"END A{action_no} SCORE {home_score}-{away_score}")
        self.lines.append("")

    # ---------------- zapis ----------------

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(self.lines))


def _pid_for(state: "GameState", p: "Player") -> str:
    """Prefiks wg PRZYNALEŻNOŚCI DO DRUŻYNY (home/away), nie wg strony boiska
    (side się nie zmienia, ale to home/away chcemy widzieć w zapisie)."""
    prefix = "h" if p in state.home.players else "a"
    return f"{prefix}{p.number}"