from __future__ import annotations
import pygame
import config as C
from core.field import Field, Cell
from core.entities import Team
from core.ball import Ball
from core.state import GameState

MARGIN_X, MARGIN_Y = C.CELL * 2, int(C.CELL * 1.5)


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