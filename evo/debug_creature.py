"""Commande `debug-creature` : la créature dans la vue debug (§7.6), en fenêtre ou en export PNG."""
import os

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import numpy as np

import config
from evo import creature as cr

H = config.DT / config.SUBSTEPS
SPEEDS = (1.0, 0.25, 0.1)
DURATION = 10.0

MODES = {
    "diagonale": ("Poses écrites à la main : diagonale + double appui",
                  lambda seed: cr.diagonal_gait_genome()),
    "diagonale-simple": ("Poses écrites à la main : diagonale seule (sans double appui)",
                         lambda seed: cr.diagonal_gait_genome(double_support=False)),
    "inerte": ("Créature inerte (aucun muscle, aucune prise)",
               lambda seed: cr.limp_genome()),
    "aleatoire": ("Créature aléatoire de la génération 0 (graine {seed})",
                  lambda seed: cr.random_genome(np.random.default_rng(seed))),
}


class Session:
    def __init__(self, mode, seed=0):
        self.mode, self.seed = mode, seed
        self.reset()

    def reset(self):
        self.creature = cr.Creature(MODES[self.mode][1](self.seed))
        self.history = [(0.0, 0.0)]
        self.max_error = 0.0

    @property
    def title(self):
        return MODES[self.mode][0].format(seed=self.seed)

    def substep(self):
        self.creature.substep(H)
        self.max_error = max(self.max_error, self.creature.world.length_error())
        if int(round(self.creature.t / config.DT)) > len(self.history) - 1:
            self.history.append((self.creature.t, self.creature.height()))

    def metrics(self):
        c = self.creature
        return [f"mode {self.mode} : hauteur {c.height():+.2f} m à t = {c.t:.1f} s   au sol : {'oui' if c.fallen else 'non'}",
                f"énergie {c.energy:.1f}   masse musculaire {c.muscle_mass():.1f}   score {c.score():+.2f}"
                f"   erreur de longueur max {self.max_error * 100:.2f} %"]


def run_interactive(mode="diagonale", seed=0):
    import pygame
    from evo.render_debug import DebugView
    from evo.render_schema import load_fonts

    pygame.display.init()
    screen = pygame.display.set_mode(config.WINDOW_SIZE)
    pygame.display.set_caption("debug-creature")
    view = DebugView(screen, load_fonts())
    session = Session(mode, seed)
    names = list(MODES)
    speed_idx, paused, accumulator = 0, False, 0.0
    clock = pygame.time.Clock()
    help_line = "1–4 mode · N nouvelle graine · Espace pause · R recommencer · S ralenti"
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                running = False
            elif event.type == pygame.KEYDOWN:
                if pygame.K_1 <= event.key <= pygame.K_4:
                    session = Session(names[event.key - pygame.K_1], session.seed)
                    view.cam_y = None
                elif event.key == pygame.K_n:
                    session = Session("aleatoire", session.seed + 1)
                    view.cam_y = None
                elif event.key == pygame.K_r:
                    session.reset()
                    view.cam_y = None
                elif event.key == pygame.K_SPACE:
                    paused = not paused
                elif event.key == pygame.K_s:
                    speed_idx = (speed_idx + 1) % len(SPEEDS)
        if not paused:
            accumulator += SPEEDS[speed_idx] * config.SUBSTEPS
            n = int(accumulator)
            accumulator -= n
            for _ in range(n):
                session.substep()
        draw_frame(view, session, extra=(help_line,) if SPEEDS[speed_idx] == 1.0
                   else (help_line, f"ralenti ×{SPEEDS[speed_idx]:g}"))
        pygame.display.flip()
        clock.tick(config.FPS)
    pygame.quit()


def draw_frame(view, session, extra=()):
    view.follow(session.creature)
    view.background(session.creature.ref_y0)
    view.creature(session.creature)
    view.hud(session.creature, session.title, session.history, extra=extra)


def export(out_dir, modes=None, seed=0, times=(0.0, 3.0, 6.0, 10.0)):
    """Pour chaque mode : une image par instant, une planche 2×2, et les métriques à 10 s."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    from evo.render_debug import DebugView
    from evo.render_schema import load_fonts

    pygame.display.init()
    os.makedirs(out_dir, exist_ok=True)
    width, height = config.WINDOW_SIZE
    surface = pygame.Surface(config.WINDOW_SIZE)
    view = DebugView(surface, load_fonts())
    results = {}
    for mode in modes or MODES:
        session = Session(mode, seed)
        view.cam_y = None
        frames, done = [], 0
        for t in times:
            target = int(round(t / H))
            for _ in range(target - done):
                session.substep()
                if _ % config.SUBSTEPS == 0:
                    view.follow(session.creature)  # garde le lerp de caméra réaliste
            done = target
            draw_frame(view, session)
            pygame.image.save(surface, os.path.join(out_dir, f"creature_{mode}_t{t:05.2f}.png"))
            frames.append(surface.copy())
        sheet = pygame.Surface(config.WINDOW_SIZE)
        for k, frame in enumerate(frames[:4]):
            small = pygame.transform.smoothscale(frame, (width // 2, height // 2))
            sheet.blit(small, ((k % 2) * width // 2, (k // 2) * height // 2))
        pygame.image.save(sheet, os.path.join(out_dir, f"planche_creature_{mode}.png"))
        results[mode] = session
        print(f"[{mode}] {session.title}")
        for line in session.metrics():
            print("    " + line)
    pygame.quit()
    print(f"Images écrites dans {out_dir}")
    return results
