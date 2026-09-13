"""
player.py — tryb HUMAN vs AI dla Football Sim (v0.6)

Uruchomienie:
    python player.py                     # sterujesz Blues (home, Side.LEFT)
    python player.py --side away
    python player.py --seed 7
    python player.py --no-air            # bez pytań o przechwyty w powietrzu
    python player.py --panel 300         # węższa kolumna decyzji

Nie modyfikuje ŻADNEGO pliku silnika. Podmienia w locie 4 funkcje:
    core.match.decide_action             -> punkt 1
    core.match.resolve_ground_duel       -> punkty 2 i 3
    core.rules.resolve_gk_save           -> punkty 4 i 5
    core.rules.resolve_air_interception  -> punkt 6 (opcjonalny)

RNG: wszystkie rzuty k10 zapadają WEWNĄTRZ resolverów, czyli PO Twoim
wyborze. Determinizm seeda pozostaje nienaruszony.

Decyzje rysowane są w osobnej kolumnie po PRAWEJ stronie okna —
boisko pozostaje w pełni widoczne podczas wybierania.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

import pygame

import config as C
from core.actions import (
    AttackAction, DefenceAction, GkAction, ShotPlacement,
    attack_stat, defence_stat, gk_stat, is_paired, shot_value,
)
from core.ai import AiDecision, decide_action as _orig_decide_action
from core.dice import Rng
from core.entities import Player, Side, Team
from core.field import Field
from core.formation import build_442
from core.match import Match
from core.resolver import (
    resolve_air_interception as _orig_air,
    resolve_gk_save as _orig_gk_save,
    resolve_ground_duel as _orig_ground_duel,
)
from render.pygame_view import PitchView


# ══════════════════════════════════════════════════════════════════
#  1. STAN STEROWNIKA
# ══════════════════════════════════════════════════════════════════
class Human:
    """Kto jest 'mój' + log decyzji.

    Rozpoznawanie po id(), NIE po ==, bo Player jest dataclass
    i porównanie == sprawdza pola (dwaj zawodnicy o tych samych
    statystykach byliby 'równi').
    """

    my_ids: set[int] = set()
    team_name: str = ""
    ask_air: bool = True
    log: list[str] = []

    @classmethod
    def bind(cls, team: Team) -> None:
        cls.my_ids = {id(p) for p in team.players}
        cls.team_name = team.name

    @classmethod
    def owns(cls, p: Player | None) -> bool:
        return p is not None and id(p) in cls.my_ids

    @classmethod
    def note(cls, txt: str) -> None:
        cls.log.append(txt)
        print(f"   👤 {txt}")


# ══════════════════════════════════════════════════════════════════
#  2. PANEL BOCZNY — decyzje OBOK boiska, nie na nim
# ══════════════════════════════════════════════════════════════════
PANEL_W = 380                      # nadpisywane przez --panel

COL_PANEL   = (14, 17, 24)
COL_BORDER  = (240, 200, 60)
COL_TITLE   = (255, 255, 255)
COL_AI      = (110, 235, 130)
COL_SEL_BG  = (44, 50, 66)
COL_SEL     = (255, 235, 120)
COL_OPT     = (198, 200, 208)
COL_DETAIL  = (140, 145, 158)
COL_GOOD    = (120, 230, 140)
COL_BAD     = (235, 120, 120)
COL_FOOT    = (128, 132, 146)


@dataclass
class Opt:
    """Jedna opcja wyboru.

    hotkey = cyfra POKAZANA w etykiecie i JEDNOCZEŚNIE wciskana na
    klawiaturze. Dla akcji jest to kod z config.PAIRS (5/6/7, 2/3/4,
    8/9), dla listy odbiorców podania — pozycja 1..9.
    """
    hotkey: int
    label: str
    detail: str = ""       # np. "stat 15  •  dystans 4"
    comment: str = ""      # np. "✓ -6 dla rywala"
    color: tuple = COL_OPT


def _key_codes(digit: int) -> list[int]:
    """Kody klawisza dla cyfry: górny rząd + klawiatura numeryczna.
    Różne wersje pygame nazywają numpad K_KP5 albo K_KP_5 — bierzemy oba."""
    out = []
    for name in (f"K_{digit}", f"K_KP{digit}", f"K_KP_{digit}"):
        code = getattr(pygame, name, None)
        if code is not None:
            out.append(code)
    return out


def _wrap(txt: str, width: int) -> list[str]:
    words, lines, cur = txt.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 <= width:
            cur = f"{cur} {w}".strip()
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]


def modal(title: str, ai_line: str, options: list[Opt], default: int = 0) -> int:
    """Blokująca pętla wyboru = 'zamrożenie czasu'.

    Silnik stoi w środku _tick_logic(); przerysowujemy zamrożoną klatkę
    boiska i dorysowujemy kolumnę decyzji po prawej.
    Zwraca INDEKS wybranej opcji. ESC = default (zostawia decyzję AI).
    """
    screen = pygame.display.get_surface()
    if screen is None:
        return _modal_console(title, ai_line, options, default)

    snap = screen.copy()
    W, H = screen.get_size()
    px, pw = W - PANEL_W + 6, PANEL_W - 14

    f_title = pygame.font.SysFont("consolas", 17, bold=True)
    f_opt   = pygame.font.SysFont("consolas", 16, bold=True)
    f_body  = pygame.font.SysFont("consolas", 14)
    f_small = pygame.font.SysFont("consolas", 13)

    hotmap: dict[int, int] = {}
    for i, o in enumerate(options):
        for code in _key_codes(o.hotkey):
            hotmap[code] = i

    idx = default if 0 <= default < len(options) else 0
    clock = pygame.time.Clock()
    char_w = max(1, pw // 8)

    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit()
                sys.exit(0)
            if ev.type == pygame.KEYDOWN:
                if ev.key in hotmap:                    # ← cyfra = kod akcji
                    return hotmap[ev.key]
                if ev.key in (pygame.K_UP, pygame.K_LEFT):
                    idx = (idx - 1) % len(options)
                elif ev.key in (pygame.K_DOWN, pygame.K_RIGHT):
                    idx = (idx + 1) % len(options)
                elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                    return idx
                elif ev.key == pygame.K_ESCAPE:
                    return default

        screen.blit(snap, (0, 0))
        pygame.draw.rect(screen, COL_PANEL, (px, 8, pw, H - 16))
        pygame.draw.rect(screen, COL_BORDER, (px, 8, pw, H - 16), 2)

        y = 20
        for line in _wrap(title, char_w):
            screen.blit(f_title.render(line, True, COL_TITLE), (px + 12, y))
            y += 20
        y += 4

        if ai_line:
            pygame.draw.line(screen, (60, 66, 82), (px + 10, y), (px + pw - 10, y))
            y += 8
            for line in _wrap(ai_line, char_w):
                screen.blit(f_body.render(line, True, COL_AI), (px + 12, y))
                y += 17
        y += 10
        pygame.draw.line(screen, (60, 66, 82), (px + 10, y), (px + pw - 10, y))
        y += 12

        for i, o in enumerate(options):
            sel = (i == idx)
            rows = 1 + bool(o.detail) + bool(o.comment)
            box_h = 8 + rows * 18
            if sel:
                pygame.draw.rect(screen, COL_SEL_BG, (px + 8, y - 4, pw - 16, box_h))
                pygame.draw.rect(screen, COL_BORDER, (px + 8, y - 4, pw - 16, box_h), 1)
            screen.blit(f_opt.render(f"[{o.hotkey}] {o.label}", True,
                                     COL_SEL if sel else COL_OPT), (px + 14, y))
            y += 18
            if o.detail:
                screen.blit(f_small.render(f"     {o.detail}", True, COL_DETAIL),
                            (px + 14, y))
                y += 18
            if o.comment:
                screen.blit(f_small.render(f"     {o.comment}", True, o.color),
                            (px + 14, y))
                y += 18
            y += 10

        foot = ["↑↓  zmiana pozycji", "cyfra  wybór natychmiast",
                "ENTER  zatwierdź", "ESC  zostaw decyzję AI"]
        fy = H - 22 - 15 * len(foot)
        for line in foot:
            screen.blit(f_small.render(line, True, COL_FOOT), (px + 12, fy))
            fy += 15

        pygame.display.flip()
        clock.tick(30)


def _modal_console(title, ai_line, options, default) -> int:
    """Fallback, gdy nie ma powierzchni pygame (np. tryb headless)."""
    print("\n" + "═" * 64)
    print(f" {title}")
    if ai_line:
        print(f" {ai_line}")
    for o in options:
        print(f"  [{o.hotkey}] {o.label:<28} {o.detail:<26} {o.comment}")
    valid = {str(o.hotkey): i for i, o in enumerate(options)}
    raw = input(" Wciśnij cyfrę (ENTER = AI): ").strip()
    return valid.get(raw, default)


# ══════════════════════════════════════════════════════════════════
#  3. OPISY I PODPOWIEDZI
# ══════════════════════════════════════════════════════════════════
PL_ATTACK = {AttackAction.DRIBBLE: "DRYBLING",
             AttackAction.SHOT:    "STRZAŁ",
             AttackAction.PASS:    "PODANIE"}
PL_DEF    = {DefenceAction.VS_DRIBBLE: "NA DRYBLING",
             DefenceAction.VS_SHOT:    "NA STRZAŁ",
             DefenceAction.VS_PASS:    "NA PODANIE"}
PL_GK     = {GkAction.PUNCH: "PIĄSTKOWANIE", GkAction.CATCH: "ŁAPANIE"}
PL_PLACE  = {ShotPlacement.POWER: "MOCNY", ShotPlacement.PLACED: "UMIESZCZONY"}
GK_PAIR   = {ShotPlacement.POWER: GkAction.PUNCH,
             ShotPlacement.PLACED: GkAction.CATCH}


def tag(p: Player) -> str:
    return f"#{p.number} {p.role.value}"


def pair_comment(paired: bool, i_am_defender: bool) -> tuple[str, tuple]:
    """Kara MISMATCH_PENALTY zawsze obciąża stronę BRONIĄCĄ (patrz resolver.py)."""
    if paired:
        return ("✓ sparowane — bez kary", COL_OPT)
    if i_am_defender:
        return (f"✗ {C.MISMATCH_PENALTY} dla mnie", COL_BAD)
    return (f"✓ {C.MISMATCH_PENALTY} dla rywala", COL_GOOD)


# ══════════════════════════════════════════════════════════════════
#  PUNKT 1 — mój zawodnik ma piłkę: co z nią zrobić
# ══════════════════════════════════════════════════════════════════
def patched_decide_action(state, carrier):
    ai_decision, ai_target = _orig_decide_action(state, carrier)
    if not Human.owns(carrier):
        return ai_decision, ai_target

    opp_side = carrier.side.opposite().value
    dist   = state.field.distance_to_goal(carrier.pos, opp_side)
    in_box = state.field.in_penalty_area(carrier.pos, opp_side)
    sv     = shot_value(state.field, carrier)
    threats = sum(1 for o in state.opponents_of(carrier).outfield()
                  if state.field.distance(carrier.pos, o.pos) <= C.THREAT_DISTANCE)

    opts = [
        Opt(5, "DRYBLING", "biegnij dalej z piłką"),
        Opt(6, "STRZAŁ",
            f"wartość {sv}" + ("  •  pole karne" if in_box else f"  •  dystans {dist}"),
            color=COL_GOOD if sv >= 12 else COL_OPT),
        Opt(7, "PODANIE", "wybierzesz odbiorcę"),
    ]
    order = [AiDecision.CONTINUE_DRIBBLE, AiDecision.SHOOT, AiDecision.PASS]

    ai_line = ("AI proponuje: " + ai_decision.value
               + (f" → #{ai_target.number}" if ai_target else ""))
    title = f"⚽ MASZ PIŁKĘ — {tag(carrier)}  •  rywali blisko: {threats}"

    choice = order[modal(title, ai_line, opts, order.index(ai_decision))]

    if choice is not AiDecision.PASS:
        Human.note(f"akcja: {choice.value}")
        return choice, None

    target = choose_pass_target(state, carrier, ai_target)
    if target is None:
        Human.note("brak odbiorcy → drybling")
        return AiDecision.CONTINUE_DRIBBLE, None
    Human.note(f"podanie → #{target.number}")
    return AiDecision.PASS, target


def choose_pass_target(state, carrier, ai_target):
    """Lista kolegów posortowana od najbliższego bramce rywala. Hotkeye 1-9."""
    opp_side = carrier.side.opposite().value
    my_dist = state.field.distance_to_goal(carrier.pos, opp_side)
    mates = [p for p in state.team_of(carrier).outfield() if p is not carrier]
    if not mates:
        return None

    mates.sort(key=lambda p: state.field.distance_to_goal(p.pos, opp_side))
    mates = mates[:9]

    opts, default = [], 0
    for i, p in enumerate(mates):
        gain = my_dist - state.field.distance_to_goal(p.pos, opp_side)
        far  = state.field.distance(carrier.pos, p.pos)
        marked = sum(1 for o in state.opponents_of(carrier).outfield()
                     if state.field.distance(p.pos, o.pos) <= 1)
        col = COL_GOOD if (gain >= C.PASS_MIN_GAIN and marked == 0) else (
              COL_BAD if marked else COL_OPT)
        opts.append(Opt(i + 1, tag(p),
                        f"dystans {far}  •  zysk {gain:+d}",
                        f"kryty ×{marked}" if marked else "wolny", col))
        if ai_target is not None and p is ai_target:
            default = i

    ai_line = (f"AI wybrało: #{ai_target.number}" if ai_target
               else "AI nie znalazło dobrego odbiorcy")
    return mates[modal(f"🎯 ODBIORCA PODANIA od {tag(carrier)}", ai_line, opts, default)]


# ══════════════════════════════════════════════════════════════════
#  PUNKTY 2 i 3 — starcie o piłkę (kontekst GROUND)
# ══════════════════════════════════════════════════════════════════
def patched_ground_duel(attacker, defender, attack, defence, rng):
    # ── PUNKT 3: mój obrońca atakuje rywala z piłką ──
    if Human.owns(defender) and not Human.owns(attacker):
        order = [DefenceAction.VS_DRIBBLE, DefenceAction.VS_SHOT, DefenceAction.VS_PASS]
        opts = []
        for d in order:
            cmt, col = pair_comment(is_paired(attack, d), i_am_defender=True)
            opts.append(Opt(int(d), f"OBRONA {PL_DEF[d]}",
                            f"stat {defence_stat(defender, d)}", cmt, col))
        ai_line = (f"AI atakuje: {PL_ATTACK[attack]} ({int(attack)}), "
                   f"stat {attack_stat(attacker, attack)}")
        title = f"🛡 TWOJA OBRONA — {tag(defender)} vs {tag(attacker)}"
        defence = order[modal(title, ai_line, opts, order.index(defence))]
        Human.note(f"obrona {PL_DEF[defence]} vs {PL_ATTACK[attack]}")

    # ── PUNKT 2: mój zawodnik z piłką jest atakowany ──
    elif Human.owns(attacker) and not Human.owns(defender):
        pool = [AttackAction.DRIBBLE, AttackAction.PASS]
        if not attacker.is_gk:                    # GK nigdy nie strzela (actions.py)
            pool.insert(1, AttackAction.SHOT)
        opts = []
        for a in pool:
            cmt, col = pair_comment(is_paired(a, defence), i_am_defender=False)
            det = f"stat {attack_stat(attacker, a)}"
            if a is not AttackAction.DRIBBLE:
                det += "  •  nie mijasz rywala"
            opts.append(Opt(int(a), PL_ATTACK[a], det, cmt, col))
        ai_line = (f"AI broni: {PL_DEF[defence]} ({int(defence)}), "
                   f"stat {defence_stat(defender, defence)}")
        title = f"⚔ ATAKUJĄ CIĘ — {tag(attacker)} vs {tag(defender)}"
        attack = pool[modal(title, ai_line, opts, pool.index(AttackAction.DRIBBLE))]
        Human.note(f"atak {PL_ATTACK[attack]} vs obrona {PL_DEF[defence]}")

    return _orig_ground_duel(attacker, defender, attack, defence, rng)


# ══════════════════════════════════════════════════════════════════
#  PUNKTY 4 i 5 — strzał vs bramkarz
# ══════════════════════════════════════════════════════════════════
def patched_gk_save(shooter, gk, shot_val, placement, gk_choice, rng):
    placement = ShotPlacement(placement)
    gk_choice = GkAction(gk_choice)

    # ── PUNKT 5: mój bramkarz broni ──
    if Human.owns(gk):
        order = [GkAction.PUNCH, GkAction.CATCH]
        opts = []
        for g in order:
            cmt, col = pair_comment(GK_PAIR[placement] == g, i_am_defender=True)
            det = f"stat {gk_stat(gk, g)}"
            if g is GkAction.CATCH and C.GK_TIE_CATCH_FAILS:
                det += "  •  remis = piłka wypada"
            opts.append(Opt(int(g), PL_GK[g], det, cmt, col))
        ai_line = f"Strzał: {PL_PLACE[placement]} ({int(placement)}), wartość {shot_val}"
        title = f"🧤 TWÓJ BRAMKARZ {tag(gk)} vs {tag(shooter)}"
        gk_choice = order[modal(title, ai_line, opts, order.index(gk_choice))]
        Human.note(f"bramkarz: {PL_GK[gk_choice]}")

    # ── PUNKT 4: mój strzelec sam na sam ──
    elif Human.owns(shooter):
        order = [ShotPlacement.POWER, ShotPlacement.PLACED]
        opts = []
        for pl in order:
            cmt, col = pair_comment(GK_PAIR[pl] == gk_choice, i_am_defender=False)
            opts.append(Opt(int(pl), f"STRZAŁ {PL_PLACE[pl]}",
                            f"wartość {shot_val}", cmt, col))
        ai_line = (f"Bramkarz wybrał: {PL_GK[gk_choice]} ({int(gk_choice)}), "
                   f"stat {gk_stat(gk, gk_choice)}")
        title = f"🥅 SAM NA SAM — {tag(shooter)} vs bramkarz #{gk.number}"
        placement = order[modal(title, ai_line, opts, order.index(placement))]
        Human.note(f"strzał {PL_PLACE[placement]} vs {PL_GK[gk_choice]}")

    return _orig_gk_save(shooter, gk, shot_val, placement, gk_choice, rng)


# ══════════════════════════════════════════════════════════════════
#  PUNKT 6 — przechwyt na trajektorii (kontekst AIR)
# ══════════════════════════════════════════════════════════════════
def patched_air(attacker, defender, attack, defence, rng, attack_value=None):
    if Human.ask_air and Human.owns(defender) and not Human.owns(attacker):
        order = [DefenceAction.VS_DRIBBLE, DefenceAction.VS_SHOT, DefenceAction.VS_PASS]
        opts = []
        for d in order:
            cmt, col = pair_comment(is_paired(attack, d), i_am_defender=True)
            opts.append(Opt(int(d), f"OBRONA {PL_DEF[d]}",
                            f"stat {defence_stat(defender, d)}", cmt, col))
        val = attack_value if attack_value is not None else attack_stat(attacker, attack)
        ai_line = (f"{PL_ATTACK[attack]} o wartości {val}  •  "
                   f"masz bonus +{C.AIR_INTERCEPT_BONUS} (piłka w powietrzu)")
        title = f"✋ PRZECHWYT — {tag(defender)} na trajektorii"
        defence = order[modal(title, ai_line, opts, order.index(defence))]
        Human.note(f"przechwyt: {PL_DEF[defence]}")

    return _orig_air(attacker, defender, attack, defence, rng, attack_value)


# ══════════════════════════════════════════════════════════════════
#  4. INSTALACJA PATCHY
# ══════════════════════════════════════════════════════════════════
def install() -> None:
    """Podmienia nazwy TAM, GDZIE SĄ UŻYWANE.

    match.py robi `from core.resolver import resolve_ground_duel`, więc
    trzyma własne wiązanie nazwy — patchujemy core.match, nie core.resolver.
    """
    import core.match as m
    m.decide_action = patched_decide_action
    m.resolve_ground_duel = patched_ground_duel
    print("✅ punkty 1-3 aktywne  (piłka przy nodze, atak i obrona)")

    import core.rules as r
    ok = []
    if hasattr(r, "resolve_gk_save"):
        r.resolve_gk_save = patched_gk_save
        ok.append("4-5 strzał vs bramkarz")
    if hasattr(r, "resolve_air_interception"):
        r.resolve_air_interception = patched_air
        ok.append("6 przechwyt")
    if ok:
        print(f"✅ punkty {', '.join(ok)}")
    else:
        print("⚠️  core.rules nie importuje resolverów po nazwie —\n"
              "    punkty 4-6 nieaktywne. Sprawdź nagłówek core/rules.py.")


# ══════════════════════════════════════════════════════════════════
#  5. MAIN
# ══════════════════════════════════════════════════════════════════
def main() -> None:
    global PANEL_W

    ap = argparse.ArgumentParser(description="Football Sim — tryb gracza")
    ap.add_argument("--side", default="home", choices=["home", "away"])
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--panel", type=int, default=380, help="szerokość kolumny decyzji")
    ap.add_argument("--no-air", action="store_true", help="wyłącz pytania o przechwyty")
    ap.add_argument("--extra-time", action="store_true")
    args = ap.parse_args()

    PANEL_W = args.panel

    field = Field()
    home = build_442(field, "Blues", Side.LEFT, "A")
    away = build_442(field, "Blacks", Side.RIGHT, "B")
    rng = Rng(seed=args.seed)

    Human.bind(home if args.side == "home" else away)
    Human.ask_air = not args.no_air
    install()

    match = Match(home, away, field, rng,
                  enable_extra_time=args.extra_time, verbose=False)
    match.console_log = True

    pygame.init()
    view = PitchView(field)
    view.screen = pygame.display.set_mode(
        (field.w * view.cell + 200 + PANEL_W, field.h * view.cell + 100))
    pygame.display.set_caption(f"Football Sim — grasz jako {Human.team_name}")
    view.clock = pygame.time.Clock()

    print(f"\n🎮 Sterujesz: {Human.team_name}  |  seed={args.seed}  |  ruch prowadzi AI")
    print("   Czas zatrzymuje się przy każdej Twojej decyzji.")
    print("   Mecz: [SPACJA] pauza  [↑↓] prędkość  [ESC] wyjście\n")

    result = match.play_with_render(view)

    print(f"\n{'=' * 54}")
    print(f"WYNIK: {result.home_score} - {result.away_score}")
    print(f"Twoich decyzji w meczu: {len(Human.log)}")
    print("=" * 54)
    pygame.quit()


if __name__ == "__main__":
    main()