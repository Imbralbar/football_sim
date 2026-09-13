from __future__ import annotations
from dataclasses import dataclass, field as dcfield
import config as C
from core.field import Field
from core.entities import Team, Player
from core.ball import Ball
from core import movement as mv
from core import ai as ai_pkg


@dataclass
class GameState:
    field: Field
    home: Team
    away: Team
    ball: Ball
    tick: int = 0
    action_no: int = 1
    log: list[str] = dcfield(default_factory=list)

    @property
    def teams(self) -> list[Team]:
        return [self.home, self.away]

    def team_of(self, p: Player) -> Team:
        return self.home if p in self.home.players else self.away

    def opponents_of(self, p: Player) -> Team:
        return self.away if p in self.home.players else self.home

    # ---------------- PĘTLA ----------------
    def step_tick(self) -> None:
        """Jeden tick = 1/36 akcji."""
        self.tick += 1
        carrier = self.ball.carrier

        # --- ruch carriery: WOLNIEJSZY, co CARRIER_MOVE_EVERY ticków ---
        if carrier is not None and self.tick % C.CARRIER_MOVE_EVERY == 0:
            if not carrier.is_gk or carrier.gk_run_active:
                mv.try_move(carrier, mv.carrier_target(carrier, self.field), self.field, self.teams)

        # --- ruch pozostałych (w tym obrońców): SZYBSZY, co PLAYER_MOVE_EVERY ticków ---
        if self.tick % C.PLAYER_MOVE_EVERY == 0:
            ai_pkg.update_phases(self)
            ai_pkg.assign_marking(self)

            ball_cell = self.ball.cell
            defending = (self.opponents_of(carrier) if carrier else self.away)
            pressers  = ai_pkg.select_pressers(self, defending, ball_cell)

            for team in self.teams:
                for p in team.outfield():
                    if p is carrier:
                        continue
                    if p.frozen_until >= self.action_no:
                        continue  # karencja po starciu — stoi w miejscu
                    p.is_presser = (team is defending) and (id(p) in pressers)
                    p.dynamic_home = ai_pkg.compute_dynamic_home(p, self.field, team)
                    target = ai_pkg.formation_target(
                        p, ball_cell, self.field, chase=p.is_presser)
                    mv.try_move(p, target, self.field, self.teams)

        self._update_contacts()

        if self.tick >= C.TICKS_PER_ACTION:
            self.tick = 0
            self.action_no += 1

    def _update_contacts(self) -> None:
        carrier = self.ball.carrier
        if carrier is None:
            for t in self.teams:
                for p in t.players:
                    p.contact_ticks = 0
            return

        opp = self.opponents_of(carrier)
        for p in opp.outfield():
            adjacent = Field.distance(p.pos, carrier.pos) == 1
            if adjacent and not carrier.is_protected(self.action_no, p):   # <- dopisz p
                p.contact_ticks += 1
            else:
                p.contact_ticks = 0

    def pending_duels(self) -> list[Player]:
        """
        Do C.DUEL_MAX_DEFENDERS obrońców, którzy osiągnęli próg kontaktu —
        z wykluczeniem tych w karencji (frozen) lub tuż po stracie piłki.
        Zastępuje dawne pending_duel() (pojedynczy obrońca).
        """
        carrier = self.ball.carrier
        if carrier is None:
            return []
        candidates = [
            p for p in self.opponents_of(carrier).outfield()
            if p.contact_ticks >= C.DUEL_CONTACT_TICKS
            and p.frozen_until < self.action_no
            and p.defense_cooldown_until < self.action_no
        ]
        candidates.sort(key=lambda p: (-p.contact_ticks, p.number))
        return candidates[:C.DUEL_MAX_DEFENDERS]