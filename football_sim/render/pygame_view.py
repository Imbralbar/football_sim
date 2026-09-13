from __future__ import annotations

import os
import json
import pygame

import config as C
from core.field import Field, Cell
from core.entities import Team
from core.ball import Ball
from core.state import GameState

MARGIN_X, MARGIN_Y = C.CELL * 2, int(C.CELL * 1.5)

SPRITES_DIR = C.SPRITES_OUTPUT_DIR
DATA_DIR = C.DATA_DIR
MODULE_ORDER = ["shoes", "legs", "shorts", "jersey", "head", "hair"]
JERSEY_FRAME = pygame.Rect(48, 128, 224, 176)   # ramka z sprite_template_cutter.py


# ────────────────────────────────────────────────────────────────
#  Rejestr Player -> Team (Player w core/entities.py nie trzyma
#  referencji do swojej drużyny)
# ────────────────────────────────────────────────────────────────
_player_team_map: dict[int, object] = {}
_team_json_cache: dict[str, dict] = {}


def register_teams(home_team, away_team) -> None:
    """Wywołaj RAZ w main() zaraz po build_442(...), przed match.play_with_render().
    Bez tego panel kariery i ekran duelu nie będą znały drużyny zawodnika."""
    _player_team_map.clear()
    for team in (home_team, away_team):
        for p in team.players:
            _player_team_map[id(p)] = team


def _load_team_json(color_key: str) -> dict:
    if color_key not in _team_json_cache:
        path = os.path.join(DATA_DIR, C.TEAM_JSON_BY_COLOR_KEY[color_key])
        with open(path, "r", encoding="utf-8") as f:
            _team_json_cache[color_key] = json.load(f)
    return _team_json_cache[color_key]


def _hex_to_rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def get_player_sprite_data(player):
    """(entry_json, team_color_rgb, skin_color_rgb) albo None, gdy brak rejestracji/danych."""
    team = _player_team_map.get(id(player))
    if team is None:
        return None
    team_json = _load_team_json(team.color_key)
    entry = next((p for p in team_json["players"] if p["number"] == player.number), None)
    if entry is None:
        return None
    return entry, _hex_to_rgb(team_json["color"]), _hex_to_rgb(team_json["skin_color"])


# ────────────────────────────────────────────────────────────────
#  Kompozytor sprite'ów z modułów PNG (sprites_output/)
# ────────────────────────────────────────────────────────────────
def _tint(surface, color):
    tinted = surface.copy()
    overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    overlay.fill((*color, 255))
    tinted.blit(overlay, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return tinted


class PlayerSpriteBuilder:
    def __init__(self):
        self._modules = {}
        self._composed = {}

    def _load(self, module, name):
        key = (module, name)
        if key not in self._modules:
            path = os.path.join(SPRITES_DIR, module, name)
            self._modules[key] = pygame.image.load(path).convert_alpha()
        return self._modules[key]

    def build(self, entry, team_color, skin_color, font=None):
        cache_key = (tuple(team_color), tuple(skin_color),
                     tuple(entry.get(m) for m in MODULE_ORDER), entry.get("number"))
        if cache_key in self._composed:
            return self._composed[cache_key]

        canvas = pygame.Surface((320, 640), pygame.SRCALPHA)
        for module in MODULE_ORDER:
            name = entry.get(module)
            if not name:
                continue
            img = self._load(module, name)
            if module in ("shorts", "jersey"):
                img = _tint(img, team_color)
            elif module in ("legs", "head"):
                img = _tint(img, skin_color)
            canvas.blit(img, (0, 0))

        if font and entry.get("number") is not None:
            num_surf = font.render(str(entry["number"]), True, (255, 255, 255))
            canvas.blit(num_surf, num_surf.get_rect(center=JERSEY_FRAME.center))

        self._composed[cache_key] = canvas
        return canvas


sprite_builder = PlayerSpriteBuilder()


# ────────────────────────────────────────────────────────────────
#  ZADANIE 1 — Panel kariery (prawy dolny róg HUD)
# ────────────────────────────────────────────────────────────────
class CareerPanel:
    """Wołane z PitchView.draw_hud(): career_panel.update(); career_panel.draw(screen, carrier)."""

    def __init__(self):
        self._grass_offset = 0
        self._font = None          # <-- ZMIENIONE: nie tworzymy fontu tutaj

    def _ensure_font(self):        # <-- DODANE
        if self._font is None:
            self._font = pygame.font.SysFont(None, 16)

    def update(self):
        self._grass_offset = (self._grass_offset + C.GRASS_SCROLL_SPEED) % (C.GRASS_STRIPE_WIDTH * 2)

    def _draw_grass(self, screen, rect):
        x = rect.left - C.GRASS_STRIPE_WIDTH * 2 + self._grass_offset
        idx = 0
        while x < rect.right:
            color = C.GRASS_COLOR_LIGHT if idx % 2 == 0 else C.GRASS_COLOR_DARK
            pygame.draw.rect(screen, color, pygame.Rect(x, rect.top, C.GRASS_STRIPE_WIDTH, rect.height).clip(rect))
            x += C.GRASS_STRIPE_WIDTH
            idx += 1

    def draw(self, screen, carrier):
        """carrier = st.ball.carrier (Player albo None)."""
        if carrier is None:
            return
        self._ensure_font()        # <-- DODANE, wywołane dopiero przy realnym rysowaniu
        data = get_player_sprite_data(carrier)
        if data is None:
            return
        entry, team_color, skin_color = data

        w, h = screen.get_size()
        rect = pygame.Rect(
            w - C.CAREER_PANEL_WIDTH - C.CAREER_PANEL_MARGIN,
            h - C.CAREER_PANEL_HEIGHT - C.CAREER_PANEL_MARGIN,
            C.CAREER_PANEL_WIDTH, C.CAREER_PANEL_HEIGHT,
        )
        pygame.draw.rect(screen, C.CAREER_PANEL_BG_COLOR, rect)
        pygame.draw.rect(screen, C.CAREER_PANEL_BORDER_COLOR, rect, C.CAREER_PANEL_BORDER_WIDTH)

        grass_rect = pygame.Rect(rect.left, rect.bottom - C.GRASS_STRIP_HEIGHT, rect.width, C.GRASS_STRIP_HEIGHT)
        self._draw_grass(screen, grass_rect)

        sprite = sprite_builder.build(entry, team_color, skin_color, font=self._font)
        scale = C.CAREER_PANEL_SPRITE_SCALE
        scaled = pygame.transform.smoothscale(sprite, (int(sprite.get_width() * scale), int(sprite.get_height() * scale)))

        clip_rect = pygame.Rect(rect.left, rect.top, rect.width, rect.height)
        sprite_rect = scaled.get_rect(centerx=rect.centerx, bottom=rect.bottom - C.GRASS_STRIP_HEIGHT + scaled.get_height() // 6)
        prev_clip = screen.get_clip()
        screen.set_clip(clip_rect)
        screen.blit(scaled, sprite_rect)
        screen.set_clip(prev_clip)


career_panel = CareerPanel()


# ────────────────────────────────────────────────────────────────
#  ZADANIE 2 — Ekran duelu (blokujący, 1-2s), wywoływany z player.py
# ────────────────────────────────────────────────────────────────
def show_duel_intro(screen, attacker, defender, panel_width=0, duration_ms=None) -> None:
    """Zastępuje boisko split-screenem na czas trwania.
    panel_width = szerokość panelu decyzji z player.py (PANEL_W), żeby duel
    nie wchodził w obszar, w którym zaraz pojawi się modal()."""
    if screen is None:
        return
    duration_ms = duration_ms or C.DUEL_SCREEN_DURATION_MS

    a_data = get_player_sprite_data(attacker)
    d_data = get_player_sprite_data(defender)
    if a_data is None or d_data is None:
        return

    pre_snapshot = screen.copy()   # <-- klatka boiska sprzed duelu, do przywrócenia na końcu

    font = pygame.font.SysFont("consolas", 22, bold=True)
    vs_font = pygame.font.SysFont("consolas", 44, bold=True)
    ball_font = pygame.font.SysFont("consolas", 18, bold=True)

    a_sprite = sprite_builder.build(*a_data)
    d_sprite = sprite_builder.build(*d_data)

    w, h = screen.get_size()
    usable_w = max(1, w - panel_width)     # <-- boisko bez obszaru panelu decyzji

    label_y = h - C.DUEL_LABEL_MARGIN_BOTTOM
    sprite_bottom = label_y - C.DUEL_SPRITE_BOTTOM_GAP
    max_sprite_h = int(h * C.DUEL_SPRITE_HEIGHT_RATIO)

    def _fit(sprite):
        scale = max_sprite_h / sprite.get_height()
        return pygame.transform.smoothscale(
            sprite, (int(sprite.get_width() * scale), int(sprite.get_height() * scale))
        )

    a_scaled, d_scaled = _fit(a_sprite), _fit(d_sprite)

    a_cx = usable_w // 4
    d_cx = usable_w * 3 // 4
    mid_x = usable_w // 2

    a_rect = a_scaled.get_rect(centerx=a_cx, bottom=sprite_bottom)
    d_rect = d_scaled.get_rect(centerx=d_cx, bottom=sprite_bottom)

    ball_center = (a_rect.centerx + C.DUEL_BALL_OFFSET_X, a_rect.bottom - C.DUEL_BALL_OFFSET_Y)

    clock = pygame.time.Clock()
    start = pygame.time.get_ticks()
    while pygame.time.get_ticks() - start < duration_ms:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit()
                raise SystemExit(0)

        screen.fill(C.DUEL_SPLIT_BG_COLOR)
        screen.blit(a_scaled, a_rect)
        screen.blit(d_scaled, d_rect)

        # piłka zawsze przy atakującym (tak działa resolve_ground_duel w core/match.py)
        pygame.draw.circle(screen, (250, 250, 250), ball_center, C.DUEL_BALL_RADIUS)
        ball_img = ball_font.render(C.BALL_GLYPH, True, (20, 20, 20))
        screen.blit(ball_img, ball_img.get_rect(center=ball_center))

        pygame.draw.line(screen, C.DUEL_DIVIDER_COLOR, (mid_x, 0), (mid_x, h), 2)
        vs_surf = vs_font.render("VS", True, C.DUEL_VS_COLOR)
        screen.blit(vs_surf, vs_surf.get_rect(center=(mid_x, h // 2)))

        screen.blit(font.render(f"#{attacker.number} {attacker.role.value}", True, C.DUEL_LABEL_COLOR),
                    (a_cx - 60, label_y))
        screen.blit(font.render(f"#{defender.number} {defender.role.value}", True, C.DUEL_LABEL_COLOR),
                    (d_cx - 60, label_y))

        pygame.display.flip()
        clock.tick(60)

    # przywróć dokładnie tę klatkę boiska, która była przed duelem —
    # inaczej kolejny modal() z player.py zrobi snapshot z duelu zamiast z boiska
    screen.blit(pre_snapshot, (0, 0))
    pygame.display.flip()

# ────────────────────────────────────────────────────────────────
#  ORYGINALNA KLASA — bez zmian logiki, tylko dopisek w draw_hud()
# ────────────────────────────────────────────────────────────────
class PitchView:
    """Warstwa wizualna. TYLKO czyta GameState - nie modyfikuje logiki."""

    def __init__(self, field: Field) -> None:
        pygame.init()
        self.f = field
        self.cell = C.CELL
        self.ox, self.oy = MARGIN_X, MARGIN_Y
        w = field.w * self.cell + MARGIN_X * 2
        h = field.h * self.cell + MARGIN_Y * 2 + 40
        self.screen = pygame.display.set_mode((w, h))
        pygame.display.set_caption("Football Sim - modul 1")
        self.font = pygame.font.SysFont("consolas",
                                        int(self.cell * 0.62), bold=True)
        self.hud = pygame.font.SysFont("consolas", 15)
        self.show_grid = True
        self.clock = pygame.time.Clock()

    # ---------- przeliczanie wspolrzednych ----------
    def px(self, x: int, y: int) -> tuple[int, int]:
        return self.ox + x * self.cell, self.oy + y * self.cell

    def pxc(self, c: Cell) -> tuple[int, int]:
        x, y = self.px(c.x, c.y)
        return x + self.cell // 2, y + self.cell // 2

    def rect(self, x: int, y: int, w: int, h: int) -> pygame.Rect:
        px, py = self.px(x, y)
        return pygame.Rect(px, py, w * self.cell, h * self.cell)

    # ---------- boisko ----------
    def draw_pitch(self) -> None:
        f = self.f
        self.screen.fill(C.COL_BG)
        for x in range(f.w):
            col = C.COL_GRASS_A if (x // 2) % 2 == 0 else C.COL_GRASS_B
            pygame.draw.rect(self.screen, col, self.rect(x, 0, 1, f.h))
        if self.show_grid:
            for x in range(f.w + 1):
                p = self.px(x, 0)
                pygame.draw.line(self.screen, (60, 130, 75), p,
                                 (p[0], self.oy + f.h * self.cell), 1)
            for y in range(f.h + 1):
                p = self.px(0, y)
                pygame.draw.line(self.screen, (60, 130, 75), p,
                                 (self.ox + f.w * self.cell, p[1]), 1)
        L = C.COL_LINE
        pygame.draw.rect(self.screen, L, self.rect(0, 0, f.w, f.h), 3)
        mid = f.w // 2
        pygame.draw.line(self.screen, L, self.px(mid, 0), self.px(mid, f.h), 3)
        cc = self.pxc(Cell(mid, f.h // 2))
        pygame.draw.circle(self.screen, L, cc, int(2.3 * self.cell), 3)
        pygame.draw.circle(self.screen, L, cc, 4)
        for side in ("LEFT", "RIGHT"):
            self._box(side, C.PENALTY_DEPTH, list(f.penalty_rows()))
            self._box(side, C.GOAL_AREA_DEPTH, list(f.goal_area_rows()))
            self._goal(side)
            sx = (C.PENALTY_SPOT_DEPTH if side == "LEFT"
                  else f.w - 1 - C.PENALTY_SPOT_DEPTH)
            pygame.draw.circle(self.screen, L, self.pxc(Cell(sx, f.h // 2)), 4)

    def _box(self, side: str, depth: int, rows: list[int]) -> None:
        x = 0 if side == "LEFT" else self.f.w - depth
        pygame.draw.rect(self.screen, C.COL_LINE,
                         self.rect(x, rows[0], depth, len(rows)), 3)

    def _goal(self, side: str) -> None:
        rows = list(self.f.goal_rows())
        x = -1 if side == "LEFT" else self.f.w
        r = self.rect(x, rows[0], 1, len(rows))
        pygame.draw.rect(self.screen, (215, 215, 215), r)
        pygame.draw.rect(self.screen, (90, 90, 90), r, 2)

    # ---------- zawodnicy i pilka ----------
    def draw_team(self, team: Team, ball: Ball) -> None:
        """Zawodnik z pilka: znak 'o' ZAKRYWA jego numer (pkt 3.2 v0.2)."""
        color = C.COL_TEAM_A if team.color_key == "A" else C.COL_TEAM_B
        rad = int(self.cell * 0.40)
        for p in team.players:
            cx, cy = self.pxc(p.pos)
            has_ball = (ball.carrier is p)
            pygame.draw.circle(self.screen, C.COL_CHIP, (cx, cy), rad)
            pygame.draw.circle(self.screen, color, (cx, cy), rad,
                               3 if has_ball else 2)
            if p.contact_ticks > 0:
                pygame.draw.circle(self.screen, C.COL_CONTACT,
                                   (cx, cy), rad + 3, 2)
            glyph = C.BALL_GLYPH if has_ball else str(p.number)
            img = self.font.render(glyph, True, color)
            self.screen.blit(img, img.get_rect(center=(cx, cy)))

    def draw_free_ball(self, ball: Ball) -> None:
        if not ball.is_free:
            return
        cx, cy = self.pxc(ball.cell)
        pygame.draw.circle(self.screen, (250, 250, 250), (cx, cy),
                           int(self.cell * 0.30))
        img = self.font.render(C.BALL_GLYPH, True, (20, 20, 20))
        self.screen.blit(img, img.get_rect(center=(cx, cy)))

    def draw_hud(self, st: GameState) -> None:
        duel = st.pending_duel()
        info = (f"Akcja {st.action_no:>2}'  tick {st.tick:>2}/"
                f"{C.TICKS_PER_ACTION}   "
                f"pilka: {'nr ' + str(st.ball.carrier.number) if st.ball.carrier else 'wolna'}   "
                f"{'STARCIE! nr ' + str(duel.number) if duel else ''}")
        keys = "[SPACJA] tick   [A] cala akcja   [G] siatka   [ESC] wyjscie"
        y = self.f.h * self.cell + MARGIN_Y + 8
        self.screen.blit(self.hud.render(info, True, (245, 245, 245)),
                         (MARGIN_X, y))
        self.screen.blit(self.hud.render(keys, True, (170, 200, 175)),
                         (MARGIN_X, y + 18))

        # ZADANIE 1 — panel kariery (prawy dolny róg)          <-- DODANE
        career_panel.update()                                   # <-- DODANE
        career_panel.draw(self.screen, st.ball.carrier)          # <-- DODANE

    # ---------- petla ----------
    def run(self, st: GameState) -> None:
        running = True
        while running:
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    running = False
                elif e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_ESCAPE:
                        running = False
                    elif e.key == pygame.K_g:
                        self.show_grid = not self.show_grid
                    elif e.key == pygame.K_SPACE:
                        st.step_tick()
                    elif e.key == pygame.K_a:
                        for _ in range(C.TICKS_PER_ACTION):
                            st.step_tick()
            self.draw_pitch()
            for t in st.teams:
                self.draw_team(t, st.ball)
            self.draw_free_ball(st.ball)
            self.draw_hud(st)
            pygame.display.flip()
            self.clock.tick(30)
        pygame.quit()