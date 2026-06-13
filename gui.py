"""
gui_pygame.py -- Pygame GUI for the Knight's Tour algorithms.

Controls:
  Click board      : Set start square
  Solve button     : Run selected algorithm (background thread)
  Space / Play     : Play / pause animation
  Left / Right     : Step backward / forward through path
  R                : Reset
"""

import pygame
import sys
import threading
from knights_tour import (
    solve_plain,
    solve_heuristic,
    solve_genetic,
    BOARD_SIZE,
    MAX_GENERATIONS,
)

# --- Layout ------------------------------------------------------------------
CELL      = 72
MARGIN    = 20
INFO_H    = 62
PANEL_W   = 270
PANEL_PAD = 16

BOARD_PX  = CELL * BOARD_SIZE          # 576
WIN_W     = MARGIN + BOARD_PX + PANEL_PAD + PANEL_W + MARGIN
WIN_H     = INFO_H + MARGIN + BOARD_PX + MARGIN

BOARD_X   = MARGIN
BOARD_Y   = INFO_H + MARGIN
PANEL_X   = BOARD_X + BOARD_PX + PANEL_PAD

FPS = 60

# --- Palette -----------------------------------------------------------------
BG        = ( 18,  22,  34)
LIGHT_SQ  = (234, 210, 168)
DARK_SQ   = (165, 117,  71)
VISIT_L   = (168, 215, 168)
VISIT_D   = ( 80, 148,  80)
CUR_L     = (255, 220,  60)
CUR_D     = (200, 158,  20)
NUM_COL   = ( 25,  55,  25)
PANEL_BG  = ( 24,  30,  46)
DIVIDER   = ( 55,  68,  95)
TEXT_PRI  = (218, 228, 245)
TEXT_DIM  = ( 95, 110, 145)
BTN_BASE  = ( 45,  65, 110)
BTN_HOVER = ( 65,  95, 158)
BTN_ACT   = ( 28,  98,  65)
BTN_TEXT  = (220, 232, 252)
INFO_BG   = ( 12,  16,  26)
COL_RED   = (200,  60,  60)
COL_YEL   = (210, 170,  30)
COL_GRN   = ( 48, 185, 100)
COORD_COL = (130, 100,  60)
KN_FILL   = ( 40,  55, 180)
KN_SHADE  = ( 25,  35, 120)
KN_EYE    = (255, 228,  60)
KN_OUT    = ( 14,  18,  50)

# --- Font helper -------------------------------------------------------------
def make_font(size, bold=False):
    """Try system fonts in order, fall back to pygame built-in."""
    for name in ("freesans", "liberationsans", "dejavusans", "ubuntu", "arial"):
        try:
            f = pygame.font.SysFont(name, size, bold=bold)
            if f:
                return f
        except Exception:
            pass
    return pygame.font.Font(None, size + 6)   # built-in bitmap font

# --- Knight drawing ----------------------------------------------------------
def draw_knight(surf, cx, cy, size):
    s = size // 2
    body = [
        (cx - s*6//10, cy + s),
        (cx + s*6//10, cy + s),
        (cx + s,       cy - s//5),
        (cx + s*3//10, cy - s),
        (cx - s//10,   cy - s),
        (cx - s,       cy - s//5),
    ]
    pygame.draw.polygon(surf, KN_FILL, body)
    pygame.draw.polygon(surf, KN_OUT,  body, 2)

    hx, hy, hr = cx + s//6, cy - s, s//2 + 2
    pygame.draw.circle(surf, KN_FILL, (hx, hy), hr)
    pygame.draw.circle(surf, KN_OUT,  (hx, hy), hr, 2)

    snout = pygame.Rect(hx - 2, hy - hr - hr//3, hr//2 + 4, hr//3 + 3)
    pygame.draw.ellipse(surf, KN_FILL, snout)
    pygame.draw.ellipse(surf, KN_OUT,  snout, 2)

    ex, ey = hx + hr//2, hy - hr//5
    pygame.draw.circle(surf, KN_EYE, (ex, ey), max(3, hr//4))
    pygame.draw.circle(surf, KN_OUT, (ex, ey), max(3, hr//4), 1)

# --- Button ------------------------------------------------------------------
class Button:
    def __init__(self, rect, label, base=BTN_BASE):
        self.rect    = pygame.Rect(rect)
        self.label   = label
        self.base    = base
        self.active  = False
        self.hovered = False
        self.enabled = True

    def update(self, mouse):
        self.hovered = self.rect.collidepoint(mouse) and self.enabled

    def clicked(self, pos):
        return self.rect.collidepoint(pos) and self.enabled

    def draw(self, surf, font):
        if not self.enabled:
            color = (35, 42, 60)
        elif self.active:
            color = BTN_ACT
        elif self.hovered:
            color = BTN_HOVER
        else:
            color = self.base
        pygame.draw.rect(surf, color,   self.rect, border_radius=7)
        pygame.draw.rect(surf, DIVIDER, self.rect, 1, border_radius=7)
        tc = TEXT_DIM if not self.enabled else BTN_TEXT
        t  = font.render(self.label, True, tc)
        surf.blit(t, t.get_rect(center=self.rect.center))

# --- App ---------------------------------------------------------------------
class KnightTourApp:
    ALGOS  = ["Heuristic Backtracking", "Plain Backtracking", "Genetic Algorithm"]
    SPEEDS = [("Slow", 3), ("Medium", 10), ("Fast", 25)]

    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIN_W, WIN_H))
        pygame.display.set_caption("♞  Knight's Tour")
        self.clock  = pygame.time.Clock()

        # Fonts -- all using the safe helper
        self.f_lg    = make_font(21, bold=True)
        self.f_md    = make_font(15)
        self.f_sm    = make_font(12)
        self.f_num   = make_font(12, bold=True)
        self.f_coord = make_font(11)

        # State
        self.algo_idx  = 0
        self.start     = (0, 0)
        self.path      = []
        self.anim_step = 0
        self.anim_acc  = 0.0
        self.anim_spd  = 10.0
        self.playing   = False
        self.solved    = False
        self.solving   = False
        self.status    = "Click a square, then press Solve."
        self.ga_gen    = 0
        self._thread   = None

        # Buttons
        bw = PANEL_W - PANEL_PAD * 2
        bx = PANEL_X + PANEL_PAD

        self.algo_btns = [
            Button((bx, BOARD_Y + 24 + i * 40, bw, 32), name)
            for i, name in enumerate(self.ALGOS)
        ]
        self.algo_btns[0].active = True

        cy = BOARD_Y + 220
        self.btn_solve = Button((bx, cy,      bw, 36), "Solve")
        self.btn_play  = Button((bx, cy + 46, bw, 36), "Play / Pause")
        self.btn_reset = Button((bx, cy + 92, bw, 36), "Reset")

        sy = BOARD_Y + 385
        sw = (bw - 8) // 3
        self.spd_btns = [
            Button((bx + i * (sw + 4), sy, sw, 28), lbl)
            for i, (lbl, _) in enumerate(self.SPEEDS)
        ]
        self.spd_btns[1].active = True

    # -- Coordinates ----------------------------------------------------------
    def cell_rect(self, col, row):
        return pygame.Rect(BOARD_X + col * CELL, BOARD_Y + row * CELL, CELL, CELL)

    def mouse_to_cell(self, mx, my):
        col = (mx - BOARD_X) // CELL
        row = (my - BOARD_Y) // CELL
        if 0 <= col < BOARD_SIZE and 0 <= row < BOARD_SIZE:
            return col, row
        return None

    # -- Solve ----------------------------------------------------------------
    def start_solve(self):
        if self.solving:
            return
        self.path = []; self.anim_step = 0; self.anim_acc = 0.0
        self.playing = False; self.solved = False; self.ga_gen = 0
        self.solving = True; self.status = "Solving..."

        algo = self.ALGOS[self.algo_idx]
        start = self.start

        def run():
            try:
                if algo == "Heuristic Backtracking":
                    p = solve_heuristic(start)
                    self.path = p or []
                    self.status = f"Done -- {len(self.path)}/64 squares."
                elif algo == "Plain Backtracking":
                    self.status = "Plain Backtracking running (may be slow)..."
                    p = solve_plain(start)
                    self.path = p or []
                    self.status = (f"Done -- {len(self.path)}/64 squares."
                                   if p else "No solution from this square.")
                elif algo == "Genetic Algorithm":
                    def cb(gen, fitness, path):
                        self.ga_gen    = gen
                        self.path      = path[:]
                        self.anim_step = min(self.anim_step, max(0, len(self.path) - 1))
                        self.status    = f"Gen {gen} -- best {fitness}/64"
                    p, gen, ok = solve_genetic(start, MAX_GENERATIONS, cb)
                    self.path  = p
                    self.status = (f"Solved at gen {gen}!" if ok
                                   else f"Best: {len(p)}/64 after {gen} gen.")
            finally:
                self.solved = True; self.solving = False
        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()

    # -- Drawing --------------------------------------------------------------
    def _draw_board(self):
        path    = self.path
        step    = self.anim_step
        visited = set(path[:step + 1]) if path else set()
        current = path[step] if path and step < len(path) else None

        # Coordinate labels
        files = "abcdefgh"
        for col in range(BOARD_SIZE):
            lbl = self.f_coord.render(files[col], True, COORD_COL)
            self.screen.blit(lbl, (BOARD_X + col*CELL + CELL//2 - lbl.get_width()//2,
                                   BOARD_Y + BOARD_PX + 3))
        for row in range(BOARD_SIZE):
            lbl = self.f_coord.render(str(BOARD_SIZE - row), True, COORD_COL)
            self.screen.blit(lbl, (BOARD_X - lbl.get_width() - 4,
                                   BOARD_Y + row*CELL + CELL//2 - lbl.get_height()//2))

        # Squares
        for row in range(BOARD_SIZE):
            for col in range(BOARD_SIZE):
                light = (col + row) % 2 == 0
                pos   = (col, row)
                rect  = self.cell_rect(col, row)
                if pos == current:
                    color = CUR_L if light else CUR_D
                elif pos in visited:
                    color = VISIT_L if light else VISIT_D
                elif not path and pos == self.start:
                    color = CUR_L if light else CUR_D
                else:
                    color = LIGHT_SQ if light else DARK_SQ
                pygame.draw.rect(self.screen, color, rect)
                pygame.draw.rect(self.screen, BG,    rect, 1)

        # Move numbers
        for idx in range(step + 1):
            if idx >= len(path): break
            col, row = path[idx]
            rect = self.cell_rect(col, row)
            num  = self.f_num.render(str(idx + 1), True, NUM_COL)
            self.screen.blit(num, num.get_rect(center=(rect.centerx, rect.centery + 12)))

        # Knight
        target = current if current else (self.start if not path else None)
        if target:
            col, row = target
            rect = self.cell_rect(col, row)
            draw_knight(self.screen, rect.centerx, rect.centery - 4, CELL - 18)

    def _draw_panel(self):
        mouse = pygame.mouse.get_pos()
        bx    = PANEL_X + PANEL_PAD

        pr = pygame.Rect(PANEL_X - 4, BOARD_Y - 4, PANEL_W + 8, BOARD_PX + 8)
        pygame.draw.rect(self.screen, PANEL_BG, pr, border_radius=10)
        pygame.draw.rect(self.screen, DIVIDER,  pr, 1, border_radius=10)

        # Algorithm buttons
        lbl = self.f_sm.render("ALGORITHM", True, TEXT_DIM)
        self.screen.blit(lbl, (bx, BOARD_Y + 5))
        for btn in self.algo_btns:
            btn.enabled = not self.solving
            btn.update(mouse); btn.draw(self.screen, self.f_md)

        # Divider
        pygame.draw.line(self.screen, DIVIDER, (PANEL_X+4, BOARD_Y + 150), (PANEL_X+PANEL_W-4, BOARD_Y + 150))

        # Start square
        self.screen.blit(self.f_sm.render("START SQUARE  (click board)", True, TEXT_DIM),
                         (bx, BOARD_Y + 160))
        sv = self.f_lg.render(f"col {self.start[0]}   row {self.start[1]}", True, TEXT_PRI)
        self.screen.blit(sv, (bx, BOARD_Y + 180))

        # Control buttons
        self.btn_solve.enabled = not self.solving
        self.btn_play.enabled  = bool(self.path)
        self.btn_reset.enabled = not self.solving
        for btn in (self.btn_solve, self.btn_play, self.btn_reset):
            btn.update(mouse); btn.draw(self.screen, self.f_md)

        # Speed
        self.screen.blit(self.f_sm.render("SPEED", True, TEXT_DIM), (bx, BOARD_Y + 365))
        for btn in self.spd_btns:
            btn.update(mouse); btn.draw(self.screen, self.f_sm)

        # Status section
        dy2 = BOARD_Y + 435
        pygame.draw.line(self.screen, DIVIDER, (PANEL_X+4, dy2), (PANEL_X+PANEL_W-4, dy2))
        self.screen.blit(self.f_sm.render("STATUS", True, TEXT_DIM), (bx, dy2 + 10))

        sc = (COL_YEL if self.solving
              else (COL_GRN if self.solved and len(self.path) == 64
                    else TEXT_PRI))
        
        # word-wrap status
        words = self.status.split()
        line, ty = "", dy2 + 30
        max_w = PANEL_W - PANEL_PAD * 2
        for w in words:
            test = line + w + " "
            if self.f_sm.size(test)[0] > max_w:
                self.screen.blit(self.f_sm.render(line.rstrip(), True, sc), (bx, ty))
                ty += 17; line = w + " "
            else:
                line = test
        if line:
            self.screen.blit(self.f_sm.render(line.rstrip(), True, sc), (bx, ty))
            ty += 17

        # Progress bar
        if self.path:
            n   = len(self.path)
            ty += 5 # small padding before bar
            bar = pygame.Rect(bx, ty, PANEL_W - PANEL_PAD*2, 9)
            pygame.draw.rect(self.screen, DIVIDER, bar, border_radius=4)
            fc = COL_GRN if n == 64 else (COL_YEL if n > 40 else COL_RED)
            fill = bar.copy(); fill.width = max(1, int(bar.width * n / 64))
            pygame.draw.rect(self.screen, fc, fill, border_radius=4)
            self.screen.blit(self.f_sm.render(f"{n} / 64 squares visited", True, TEXT_PRI),
                             (bx, ty + 15))
            self.screen.blit(self.f_sm.render(f"Step {self.anim_step+1} / {len(self.path)}",
                                              True, TEXT_DIM), (bx, ty + 32))

    def _draw_infobar(self):
        pygame.draw.rect(self.screen, INFO_BG, (0, 0, WIN_W, INFO_H))
        pygame.draw.line(self.screen, DIVIDER, (0, INFO_H), (WIN_W, INFO_H))

        self.screen.blit(self.f_lg.render("Knight's Tour", True, TEXT_PRI), (MARGIN, 12))
        self.screen.blit(self.f_sm.render(f"Algorithm: {self.ALGOS[self.algo_idx]}",
                                          True, TEXT_DIM), (MARGIN, 38))

        hint = self.f_sm.render(
            "Space = play/pause   |   Left / Right = step   |   Click board = set start",
            True, TEXT_DIM)
        self.screen.blit(hint, (WIN_W//2 - hint.get_width()//2, 42))

    # -- Events ---------------------------------------------------------------
    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    self._toggle_play()
                elif event.key == pygame.K_RIGHT and self.path:
                    self.anim_step = min(self.anim_step + 1, len(self.path) - 1)
                    self.playing = False
                elif event.key == pygame.K_LEFT and self.path:
                    self.anim_step = max(self.anim_step - 1, 0)
                    self.playing = False
                elif event.key == pygame.K_r:
                    self._reset()

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                cell = self.mouse_to_cell(mx, my)

                if cell and not self.solving:
                    self.start = cell; self.path = []; self.anim_step = 0
                    self.playing = False; self.solved = False
                    self.status = "Start square set. Press Solve."

                for i, btn in enumerate(self.algo_btns):
                    if btn.clicked((mx, my)):
                        for b in self.algo_btns: b.active = False
                        btn.active = True; self.algo_idx = i; self._reset()

                if self.btn_solve.clicked((mx, my)): self.start_solve()
                if self.btn_play.clicked((mx, my)):  self._toggle_play()
                if self.btn_reset.clicked((mx, my)): self._reset()

                for i, btn in enumerate(self.spd_btns):
                    if btn.clicked((mx, my)):
                        for b in self.spd_btns: b.active = False
                        btn.active = True; self.anim_spd = self.SPEEDS[i][1]

    def _toggle_play(self):
        if not self.path: return
        if self.anim_step >= len(self.path) - 1:
            self.anim_step = 0
        self.playing = not self.playing
        self.anim_acc = 0.0

    def _reset(self):
        self.path = []; self.anim_step = 0; self.anim_acc = 0.0
        self.playing = False; self.solved = False; self.solving = False
        self.ga_gen = 0; self.status = "Click a square, then press Solve."

    # -- Loop -----------------------------------------------------------------
    def run(self):
        while True:
            dt = self.clock.tick(FPS) / 1000.0
            self._handle_events()

            if self.playing and self.path:
                self.anim_acc += dt * self.anim_spd
                steps = int(self.anim_acc)
                if steps:
                    self.anim_acc -= steps
                    self.anim_step = min(self.anim_step + steps, len(self.path) - 1)
                    if self.anim_step >= len(self.path) - 1:
                        self.playing = False

            if self.path:
                self.anim_step = min(self.anim_step, len(self.path) - 1)

            self.screen.fill(BG)
            self._draw_board()
            self._draw_panel()
            self._draw_infobar()
            pygame.display.flip()


if __name__ == "__main__":
    KnightTourApp().run()
