"""
core/match.py – Orkiestrator pełnego meczu.

Architektura ticka (w kolejności):
  1. step_tick()          – ruch zawodników + contact_ticks
  2. pending_duel()       – starcie o piłkę (jeśli próg osiągnięty)
  3. _handle_ai_decision  – decyzja AI (RAZ na akcję, nie raz na tick)
  4. is_goal()            – gol geometryczny (wolna piłka za linią)

Dlaczego AI raz na akcję?
  CARRIER_MOVE_EVERY=3 → 12 ticków ruchu na akcję (ticki 0,3,6,...,33).
  Gdyby AI decydowała w każdym ticku ruchu → 12 strzałów na akcję → 130+ goli.
  Jedna decyzja na akcję = jedno zdarzenie na minutę gry. Logiczne i realistyczne.
"""
from __future__ import annotations

from dataclasses import dataclass, field as dcfield
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.entities import Team, Player

from core.state import GameState
from core.ball import Ball
from core.field import Field, Cell   # było: from core.field import Field
from core.events import EventLog, MatchEvent, EventType
from core.dice import Rng
from core.ai import decide_action, AiDecision, pick_pass_target
from core.resolver import resolve_ground_duel, Outcome   # dopisz Outcome
from core.rules import resolve_pass, resolve_shot, is_goal
from core.actions import AttackAction, DefenceAction, shot_value as compute_shot_value
from core import formation
import config as C

HALF_ACTIONS: int = getattr(C, "HALF_ACTIONS", 45)
EXTRA_HALF_ACTIONS: int = getattr(C, "EXTRA_HALF_ACTIONS", 15)



class MatchPhase(str, Enum):
    FIRST_HALF    = "FIRST_HALF"
    SECOND_HALF   = "SECOND_HALF"
    EXTRA_FIRST   = "EXTRA_FIRST"
    EXTRA_SECOND  = "EXTRA_SECOND"
    FINISHED      = "FINISHED"


@dataclass
class MatchResult:
    home_score:    int
    away_score:    int
    winner:        str | None
    phase_ended:   MatchPhase
    events:        EventLog
    final_state:   GameState
    total_actions: int


class Match:
    def __init__(
        self,
        home: Team,
        away: Team,
        field: Field,
        rng: Rng,
        enable_extra_time: bool = True,
        verbose: bool = False,
    ):
        self.home = home
        self.away = away
        self.field = field
        self.rng = rng
        self.enable_extra_time = enable_extra_time
        self.verbose = verbose
        self.console_log: bool = True   # krótkie logi w terminalu, niezależne od verbose

        self.home_score: int = 0
        self.away_score: int = 0
        self.events = EventLog()

        self.state: GameState | None = None
        self.last_passer: Player | None = None
        self.phase: MatchPhase = MatchPhase.FIRST_HALF
        self.actions_played: int = 0

        # Używane wewnątrz pętli ticka — nie modyfikuj z zewnątrz
        self._action_no: int = 1
        self._scored_this_tick: bool = False
        self._ai_decided_this_action: bool = False  # kluczowy guard!

        # ═══════════════ RECORDER: chess notation ═══════════════
        from export.chess_notation import ChessNotation
        self.notation = ChessNotation()
        self.record_notation: bool = True   # ustaw False, by wyłączyć nagrywanie
        # ══════════════════════════════════════════════════════════

    # ──────────────────────────────────────────────────────────────────────
    # API publiczne
    # ──────────────────────────────────────────────────────────────────────
    def _pid(self, p: Player) -> str:
        return ("h" if p in self.home.players else "a") + str(p.number)

    def _log(self, msg: str) -> None:
        if self.console_log:
            a = self.state.action_no if self.state else "-"
            t = self.state.tick if self.state else "-"
            print(f"[A{a:>3} T{t:>2}] {msg}")

    def play(self) -> MatchResult:
        """Rozgrywa pełny mecz bez renderowania."""
        regular_end = 2 * HALF_ACTIONS

        self._setup_kickoff(self.home, action_no=1)
        self._play_half(1, HALF_ACTIONS, MatchPhase.FIRST_HALF)
        self._emit(EventType.HALFTIME, note=self._score_note())

        self._setup_kickoff(self.away, action_no=HALF_ACTIONS + 1)
        self._play_half(HALF_ACTIONS + 1, regular_end, MatchPhase.SECOND_HALF)
        phase_ended = MatchPhase.SECOND_HALF

        if self.enable_extra_time and self.home_score == self.away_score:
            e1_start = regular_end + 1
            e1_end   = regular_end + EXTRA_HALF_ACTIONS
            e2_start = e1_end + 1
            e2_end   = e1_end + EXTRA_HALF_ACTIONS

            self._setup_kickoff(self.home, action_no=e1_start)
            self._play_half(e1_start, e1_end, MatchPhase.EXTRA_FIRST)
            self._setup_kickoff(self.away, action_no=e2_start)
            self._play_half(e2_start, e2_end, MatchPhase.EXTRA_SECOND)
            phase_ended = MatchPhase.EXTRA_SECOND

        self._emit(EventType.FULLTIME, note=self._score_note())
        self.phase = MatchPhase.FINISHED

        # ═══════════════ RECORDER: zapis pliku .cn ═══════════════
        if self.record_notation:
            import os
            os.makedirs("replays", exist_ok=True)
            self.notation.save(f"replays/match_seed{self.rng.seed}.cn")
            print(f"📝 Notacja zapisana: replays/match_seed{self.rng.seed}.cn")
        # ══════════════════════════════════════════════════════════

        return MatchResult(
            home_score=self.home_score,
            away_score=self.away_score,
            winner=self._determine_winner(),
            phase_ended=phase_ended,
            events=self.events,
            final_state=self.state,
            total_actions=self.actions_played,
        )
    def play_with_render(self, renderer) -> MatchResult:
        """Rozgrywa mecz z wizualizacją pygame."""
        import os
        import pygame
        from export.replay import capture_tick, export_replay
        from player import Human, draw_control_status

        self._setup_kickoff(kicking_team=self.home, action_no=1)

        running = True
        paused  = False
        speed   = 1
        tick_history = []

        for action in range(1, 91):
            self.state.action_no = action
            self._ai_decided_this_action = False        # reset raz na akcję

            for tick in range(C.TICKS_PER_ACTION):
                self.state.tick = tick

                tick_history.append(capture_tick(self.state))

                # ── pygame events ──────────────────────────────────
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        running = False
                        break
                    elif event.type == pygame.KEYDOWN:
                        # A = oddaj AI, P = przejmij sterowanie (jednokierunkowe)
                        if event.key == pygame.K_a:
                            Human.set_ai()
                        elif event.key == pygame.K_p:
                            Human.set_player()
                        elif event.key == pygame.K_ESCAPE:
                            running = False
                            break
                        elif event.key == pygame.K_SPACE:
                            paused = not paused
                        elif event.key == pygame.K_UP:
                            speed = min(speed + 1, 10)
                        elif event.key == pygame.K_DOWN:
                            speed = max(speed - 1, 1)

                if not running:
                    break

                if not paused:
                    # Gracz właśnie przejął ster — pozwól zdecydować w tej akcji
                    if Human.force_redecide:
                        self._ai_decided_this_action = False
                        Human.force_redecide = False

                    self._tick_logic()

                self._render(renderer, action, tick, paused, speed)

                # Status kontroli (nakładka w rogu ekranu)
                screen = pygame.display.get_surface()
                if screen is not None:
                    draw_control_status(screen, position=(10, 10))

                pygame.display.flip()
                renderer.clock.tick(30 * speed)

            # koniec akcji — recorder
            if self.record_notation:
                self.notation.record_action_end(action, self.home_score, self.away_score)

            if not running:
                break

        # ═══════════════ KONIEC MECZU (POZA pętlą for action) ═══════════════
        print(f"\n🏁 KONIEC MECZU!")
        print(f"{self.home.name} {self.home_score} - {self.away_score} {self.away.name}")

        result = MatchResult(
            home_score=self.home_score,
            away_score=self.away_score,
            winner=self._determine_winner(),
            phase_ended=MatchPhase.SECOND_HALF,
            events=self.events,
            final_state=self.state,
            total_actions=90,
        )

        os.makedirs("replays", exist_ok=True)
        replay_path = f"replays/match_seed{self.rng.seed}.json"
        export_replay(result, tick_history, self.rng.seed, replay_path)
        print(f"📁 Replay zapisany: {replay_path}")

        if self.record_notation:
            self.notation.save(f"replays/match_seed{self.rng.seed}.cn")
            print(f"📝 Notacja zapisana: replays/match_seed{self.rng.seed}.cn")

        return result

    # ──────────────────────────────────────────────────────────────────────
    # Pętla wewnętrzna — wspólna logika ticka
    # ──────────────────────────────────────────────────────────────────────

    def _tick_logic(self) -> None:
        """
        Jeden tick logiki meczu — wspólny dla play() i play_with_render().

        Kolejność:
          1. step_tick()  – ruch + contact_ticks
          2. duel         – starcie jeśli próg osiągnięty
          3. AI           – JEDNA decyzja na akcję (guard _ai_decided_this_action)
          4. is_goal      – gol geometryczny (tylko jeśli brak gola w tym ticku)
        """
        state = self.state
        self._scored_this_tick = False

        # 1) Ruch
        state.step_tick()

        # 2) Starcie
        carrier = state.ball.carrier
        defenders = state.pending_duels()
        if defenders and not (carrier is not None and carrier.is_gk and not carrier.gk_run_active):
            self._handle_duel(defenders)

        # 3) Decyzja AI — raz na akcję, tylko w ticku ruchu carriery
        if (not self._scored_this_tick
                and not self._ai_decided_this_action
                and state.ball.carrier is not None
                and state.tick % C.CARRIER_MOVE_EVERY == 0):

            self._handle_ai_decision(state.ball.carrier)
            self._ai_decided_this_action = True     # blokuj kolejne ticki

        # 4) Gol geometryczny (wolna piłka za linią — np. po wybicu GK)
        if not self._scored_this_tick and state.ball.is_free:
            scored, losing_side = is_goal(state)
            if scored:
                conceding = self._team_by_side(losing_side)
                scoring   = self.away if conceding is self.home else self.home
                self._register_goal(scoring, conceding, None, None)

        # ═══════════════ RECORDER: stan ticka ═══════════════
        if self.record_notation:
            self.notation.record_tick(self.state)
        # ══════════════════════════════════════════════════════

    # ──────────────────────────────────────────────────────────────────────
    # Pętla połowy (używana przez play())
    # ──────────────────────────────────────────────────────────────────────

    def _play_half(self, start_action: int, end_action: int,
                   phase: MatchPhase) -> None:
        self.phase = phase
        for _ in range(start_action, end_action + 1):
            self._play_action()
            self.actions_played += 1

    def _play_action(self) -> None:
        """Jedna akcja = TICKS_PER_ACTION ticków."""
        state = self.state
        self._action_no = state.action_no
        self._ai_decided_this_action = False        # reset raz na akcję

        for _ in range(C.TICKS_PER_ACTION):
            self._tick_logic()

        # ═══════════════ RECORDER: koniec akcji ═══════════════
        # UWAGA: self._action_no zostało złapane PRZED pętlą, bo state.action_no
        # po ostatnim ticku już wskazuje na NASTĘPNĄ akcję (patrz step_tick()).
        if self.record_notation:
            self.notation.record_action_end(self._action_no, self.home_score, self.away_score)
        # ══════════════════════════════════════════════════════════

    # ──────────────────────────────────────────────────────────────────────
    # Renderowanie (tylko play_with_render)
    # ──────────────────────────────────────────────────────────────────────

    def _render(self, renderer, action: int, tick: int,
                paused: bool, speed: int) -> None:
        renderer.draw_pitch()
        for team in self.state.teams:
            renderer.draw_team(team, self.state.ball)
        renderer.draw_free_ball(self.state.ball)

        carrier_info = (
            f"nr {self.state.ball.carrier.number}"
            if self.state.ball.carrier else "wolna"
        )
        info = (
            f"Akcja {action:>2}' tick {tick:>2}/36 | "
            f"Wynik: {self.home_score}-{self.away_score} | "
            f"Piłka: {carrier_info} | "
            f"{'PAUZA' if paused else f'Prędkość: {speed}x'}"
        )
        keys = "[SPACJA] pauza  [↑↓] prędkość  [ESC] wyjście"

        img  = renderer.hud.render(info, True, (245, 245, 245))
        img2 = renderer.hud.render(keys, True, (170, 200, 175))
        y0   = self.field.h * renderer.cell
        renderer.screen.blit(img,  (10, y0 + 40))
        renderer.screen.blit(img2, (10, y0 + 60))

    # ──────────────────────────────────────────────────────────────────────
    # Starcie zawodnik–zawodnik
    # ──────────────────────────────────────────────────────────────────────

    def _handle_duel(self, defenders: list[Player]) -> None:
        """
        Starcie o piłkę — do C.DUEL_MAX_DEFENDERS obrońców, sekwencyjnie.
        Każdy uczestnik (niezależnie od wyniku) dostaje karencję frozen_until
        (stoi w miejscu przez DUEL_COOLDOWN_DEFENDER akcji). Jeśli carrier
        przegra którekolwiek starcie, piłka od razu zmienia właściciela
        i traci defense_cooldown_until akcji (nie może bronić/pressować).
        """
        carrier = self.state.ball.carrier
        if carrier is None:
            return

        result = None
        for defender in defenders:
            defence_action = self._pick_defence_action(defender)
            result = resolve_ground_duel(
                carrier, defender, AttackAction.DRIBBLE, defence_action, self.rng,
            )

            # ═══════════════ RECORDER: wynik starcia ═══════════════
            if self.record_notation:
                self.notation.record_duel(
                    self.state, carrier, defender,
                    result.attack_total, result.defence_total, result.attacker_wins,
                )
            # ══════════════════════════════════════════════════════════
            outcome_txt = "BEAT_DEFENDER" if result.attacker_wins else "TURNOVER"
            self._log(f"⚔️  {self._pid(carrier)} vs {self._pid(defender)}  "
                    f"ATK={result.attack_total} DEF={result.defence_total} → "
                    f"{self._pid(carrier) if result.attacker_wins else self._pid(defender)} wygrywa ({outcome_txt})")

            # Karencja dla KAŻDEGO uczestnika starcia, niezależnie od wyniku
            defender.frozen_until = self.state.action_no + C.DUEL_COOLDOWN_DEFENDER
            defender.contact_ticks = 0

            if result.attacker_wins:
                carrier.grant_protection(self.state.action_no, defender)
                if result.outcome == Outcome.BEAT_DEFENDER:
                    self._push_defender_aside(carrier, defender)
                if carrier.is_gk and carrier.gk_run_active:
                    self._advance_gk_dribble_chance(carrier)
                if self.verbose:
                    print(f"  ⚔️  Starcie: {carrier.number} pokonał {defender.number}")
                continue

            # carrier przegrywa
            loser = carrier
            self.state.ball.give_to(defender)
            loser.defense_cooldown_until = self.state.action_no + C.DUEL_COOLDOWN_ATTACKER_LOSS
            self._ai_decided_this_action = False
            if loser.is_gk and loser.gk_run_active:
                defender.shot_bonus_mult = 1.0 + C.GK_LOST_BALL_SHOT_BONUS
                loser.gk_run_active = False
                loser.gk_dribble_chance = 0.0
                self._log(f"🚨 {self._pid(defender)} okradł bramkarza {self._pid(loser)}! "
                        f"Bonus do strzału +{C.GK_LOST_BALL_SHOT_BONUS:.0%}")
            if self.verbose:
                print(f"  ⚔️  Starcie: {defender.number} odebrał piłkę {loser.number}")

            self.events.add_duel(
                action_no=self.state.action_no, tick=self.state.tick,
                team=carrier.side.value, result=result,
            )
            return  # piłka stracona — koniec sekwencji starć w tym ticku

        # Wszyscy obrońcy przegrali — zaloguj ostatni wynik (informacyjnie)
        if result is not None:
            self.events.add_duel(
                action_no=self.state.action_no, tick=self.state.tick,
                team=carrier.side.value, result=result,
            )

    def _pick_defence_action(self, defender: Player) -> DefenceAction:
        if defender.role.value == "DEF":
            return DefenceAction.VS_DRIBBLE
        return (DefenceAction.VS_DRIBBLE
                if self.rng.roll() >= 3
                else DefenceAction.VS_PASS)
    def _push_defender_aside(self, carrier: Player, defender: Player) -> None:
        """
        Fizycznie odsuwa pokonanego obrońcę (BEAT_DEFENDER), żeby carrier
        mógł realnie przejść. Bez tego try_move dalej widzi obrońcę jako
        zajętą kratkę, mimo przegranego starcia — carrier zapętla się w miejscu.
        """
        from core.geometry import sign
        field = self.field

        dx = (sign(carrier.pos.x - defender.pos.x)
            if carrier.pos.x != defender.pos.x
            else (1 if carrier.side.value == "LEFT" else -1))

        # Kandydaci: najpierw bok (nie blokuje dalszej trasy), potem cofnięcie
        candidates = [
            Cell(defender.pos.x, defender.pos.y + 1),
            Cell(defender.pos.x, defender.pos.y - 1),
            Cell(defender.pos.x - dx, defender.pos.y),
        ]
        occ = {(p.pos.x, p.pos.y) for t in self.state.teams
            for p in t.players if p is not defender}

        for c in candidates:
            c = field.clamp(c)
            if (c.x, c.y) not in occ:
                defender.pos = c
                return

    # ──────────────────────────────────────────────────────────────────────
    # Decyzje AI
    # ──────────────────────────────────────────────────────────────────────

    def _handle_ai_decision(self, carrier: Player) -> None:
        if carrier.is_gk:
            self._handle_gk_decision(carrier)
            return

        decision, target = decide_action(self.state, carrier)
        if decision == AiDecision.PASS and target is not None:
            self._handle_pass(carrier, target)
        elif decision == AiDecision.SHOOT:
            self._handle_shot(carrier)
        # CONTINUE_DRIBBLE → nic, carrier biegnie dalej

        # ═══════════════ RECORDER: decyzja AI ═══════════════
        if self.record_notation:
            self.notation.record_decision(carrier, self.state, decision.value, target)
        # ══════════════════════════════════════════════════════
        self._log(f"🏃 {self._pid(carrier)} {decision.value}"
                + (f" > {self._pid(target)}" if target else ""))

    def _handle_gk_decision(self, gk: Player) -> None:
        """
        Decyzja bramkarza trzymającego piłkę (po SAVED).
        Rzut szansą gk.gk_dribble_chance: sukces -> wybiega z piłką (staje się
        normalnym poruszającym się carrierem, podatnym na duel). Porażka -> podaje
        i natychmiast wraca (teleport) na linię bramkową.
        """
        roll = self.rng.randint(1, 100)
        attempt_dribble = roll <= round(gk.gk_dribble_chance * 100)

        if attempt_dribble:
            gk.gk_run_active = True
            self._log(f"🧤🏃 {self._pid(gk)} bramkarz wybiega z piłką "
                    f"(szansa {gk.gk_dribble_chance:.0%})")
            if self.record_notation:
                self.notation.record_decision(gk, self.state, "GK_DRIBBLE")
            return

        gk.gk_run_active = False
        target = pick_pass_target(self.state, gk)
        if target is not None:
            self._handle_pass(gk, target)   # teleport z powrotem dzieje się w _handle_pass
        else:
            self._log(f"🧤 {self._pid(gk)} bramkarz nie ma komu podać, trzyma piłkę")
            if self.record_notation:
                self.notation.record_decision(gk, self.state, "GK_HOLD")

    def _advance_gk_dribble_chance(self, gk: Player) -> None:
        """Po wygranym dryblingu bramkarza: 1. wygrana -> 5%, każda kolejna -> /2."""
        if not gk.gk_has_won_once:
            gk.gk_dribble_chance = C.GK_DRIBBLE_CHANCE_AFTER_WIN
            gk.gk_has_won_once = True
        else:
            gk.gk_dribble_chance /= 2
        if gk.gk_dribble_chance < C.GK_DRIBBLE_MIN_CHANCE:
            gk.gk_dribble_chance = 0.0

    def _handle_pass(self, passer: Player, target: Player) -> None:
        from core.rules import PassResult

        outcome = resolve_pass(self.state, passer, target, self.rng)

        if outcome.result == PassResult.COMPLETE:
            self.state.ball.give_to(target)
            self._ai_decided_this_action = False    # nowy carrier, nowa decyzja
            if self.verbose:
                print(f"  ✅ Podanie: {passer.number} → {target.number}")
            self.last_passer = passer
        else:
            self.state.ball.give_to(outcome.interceptor)
            self._ai_decided_this_action = False    # nowy carrier
            if self.verbose:
                print(f"  ❌ Podanie: {passer.number} → {target.number} "
                      f"(przechwyt {outcome.interceptor.number})")
            self.last_passer = None

        self.events.add_pass(
            action=self.state.action_no,
            passer=passer,
            target=target,
            intercepted=(outcome.result != PassResult.COMPLETE),
        )
        if passer.is_gk:
            passer.pos = self.field.goal_center(passer.side.value)
            passer.gk_run_active = False
            passer.gk_dribble_chance = 0.0
            passer.gk_has_won_once = False
        # ═══════════════ RECORDER: podanie ═══════════════
        if self.record_notation:
            self.notation.record_pass(self.state, passer, target, outcome.result.value)
        # ══════════════════════════════════════════════════════
        self._log(f"🎯 PASS {self._pid(passer)}→{self._pid(target)}: {outcome.result.value}")

    def _handle_shot(self, shooter: Player) -> None:
        from core.rules import ShotResult
        outcome = resolve_shot(self.state, shooter, self.rng)

        if outcome.result == ShotResult.GOAL:
            scoring   = self._team_of(shooter)
            conceding = self._opponents_of(shooter)
            self._register_goal(scoring, conceding, shooter, self.last_passer)
            self.last_passer = None

        elif outcome.result == ShotResult.SAVED:
            self.state.ball.give_to(outcome.goalkeeper)
            outcome.goalkeeper.gk_run_active = False
            outcome.goalkeeper.gk_dribble_chance = C.GK_INITIAL_DRIBBLE_CHANCE
            outcome.goalkeeper.gk_has_won_once = False
            self._ai_decided_this_action = False
            if self.verbose:
                print(f"  🧤 Strzał {shooter.number} obroniony przez {outcome.goalkeeper.number}")
            self.last_passer = None

        elif outcome.result == ShotResult.INTERCEPTED:
            self.state.ball.give_to(outcome.interceptor)
            self._ai_decided_this_action = False
            if self.verbose:
                print(f"  🛡️  Strzał {shooter.number} zablokowany przez {outcome.interceptor.number}")
            self.last_passer = None

        self.events.add_shot(
            action=self.state.action_no, shooter=shooter,
            saved=(outcome.result == ShotResult.SAVED),
        )
        shooter.shot_bonus_mult = 1.0   # jednorazowy bonus zużyty niezależnie od wyniku

        # ═══════════════ RECORDER: strzał ═══════════════
        if self.record_notation:
            val = compute_shot_value(self.state.field, shooter)
            self.notation.record_shot(self.state, shooter, val, outcome.result.value)
        # ══════════════════════════════════════════════════════
        self._log(f"🥅 SHOT {self._pid(shooter)} val={compute_shot_value(self.state.field, shooter)}: {outcome.result.value}")

    # ──────────────────────────────────────────────────────────────────────
    # Gol i wznowienie
    # ──────────────────────────────────────────────────────────────────────

    def _register_goal(
        self,
        scoring_team:  Team,
        conceding_team: Team,
        scorer:  Player | None,
        assist:  Player | None,
    ) -> None:
        if scoring_team is self.home:
            self.home_score += 1
        else:
            self.away_score += 1

        self._scored_this_tick       = True
        self._ai_decided_this_action = True     # nie strzelaj drugi raz w tej akcji

        self._emit(
            EventType.GOAL,
            team=scoring_team.name,
            player=scorer.number if scorer else None,
            target=assist.number if assist else None,
            note=self._score_note(),
        )

        print(f"⚽ GOL dla {scoring_team.name}! "
              f"Wynik: {self.home_score}-{self.away_score}")

        self.last_passer = None
        self._setup_kickoff(kicking_team=conceding_team)

    def _setup_kickoff(
        self,
        kicking_team: Team | None = None,
        action_no:    int | None  = None,
    ) -> None:
        from core.formation import kickoff

        if kicking_team is None:
            kicking_team = self.home

        # Reset pozycji wszystkich zawodników
        for team in (self.home, self.away):
            for player in team.players:
                if player.home is not None:
                    player.pos = player.home
                player.contact_ticks = 0
                player.gk_run_active = False
                player.gk_dribble_chance = 0.0
                player.gk_has_won_once = False
                player.shot_bonus_mult = 1.0

        ball = kickoff(self.field, kicking=kicking_team)

        if self.state is None:
            self.state = GameState(
                field=self.field,
                home=self.home,
                away=self.away,
                ball=ball,
                tick=0,
                action_no=action_no or 1,
            )
        else:
            self.state.ball     = ball
            self.state.tick     = 0
            if action_no is not None:
                self.state.action_no = action_no

        # ═══════════════ RECORDER: nagłówek (tylko przy kickoff nr 1) ═══════════════
        if self.record_notation and action_no == 1:
            self.notation.write_header(self.state, self.rng.seed)
        # ══════════════════════════════════════════════════════════════════════════

    # ──────────────────────────────────────────────────────────────────────
    # Pomocnicze
    # ──────────────────────────────────────────────────────────────────────

    def _team_of(self, player: Player) -> Team:
        return self.home if player in self.home.players else self.away

    def _opponents_of(self, player: Player) -> Team:
        return self.away if player in self.home.players else self.home

    def _team_by_side(self, side: str | None) -> Team:
        """Zwraca drużynę która STRACIŁA bramkę (po stronie 'side')."""
        if side is None:
            return self.away
        return self.home if self.home.side.value == side else self.away

    def _emit(self, etype: EventType, *, team=None, player=None,
              target=None, from_cell=None, to_cell=None,
              duel=None, note="") -> None:
        self.events.add(MatchEvent(
            action_no=self._action_no,
            tick=self.state.tick if self.state else 0,
            etype=etype,
            team=team, player=player, target=target,
            from_cell=from_cell, to_cell=to_cell,
            duel=duel, note=note,
        ))

    def _score_note(self) -> str:
        return f"{self.home_score}-{self.away_score}"

    def _determine_winner(self) -> str | None:
        if self.home_score > self.away_score: return "home"
        if self.away_score > self.home_score: return "away"
        return None