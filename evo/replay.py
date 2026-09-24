"""Commande `replay` (§8) : rejoue une créature sauvegardée dans la jungle (§5).

La créature est relue depuis runs/<graine>/gen_XXXX.npz, avec la config du run, puis rejouée
10 s avec le moteur scalaire (evo/creature.py). On garde un état par frame (1/60 s) et on vérifie
que la hauteur rejouée est la hauteur stockée. Le rendu (décor pré-rendu + lézard) lit ensuite
ces états : fenêtre interactive à 60 fps, ou export PNG sans écran.
"""
import glob
import json
import os
import re
import time

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import numpy as np

import config
from evo import creature as cr
from evo import evolution as ev

H = config.DT / config.SUBSTEPS
REFERENCE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "reference")


class Replay:
    """Une créature d'une génération sauvegardée, rejouée et enregistrée frame par frame."""

    def __init__(self, run_dir, gen=None, rank=1, index=None, log=print):
        self.run_dir = run_dir
        with open(os.path.join(run_dir, "config.json")) as fh:
            ev.apply_config(json.load(fh), strict=False)
        cr._torque_unit.cache_clear()
        gens = ev.saved_generations(run_dir)
        if not gens:
            raise FileNotFoundError(f"aucune génération sauvegardée dans {run_dir}")
        self.gen = gens[-1] if gen is None else gen
        pop, res, _, _ = ev.load_generation(run_dir, self.gen)
        order = ev.ranking(res["score"])
        if index is None:
            if not 1 <= rank <= len(order):
                raise ValueError(f"rang {rank} hors de 1…{len(order)}")
            index = int(order[rank - 1])
        self.index = int(index)
        self.rank = int(np.where(order == self.index)[0][0]) + 1
        self.genome = pop.genome(self.index)
        self.stored = {k: float(res[k][self.index]) for k in ("height", "score", "energy", "muscle_mass")}
        self.seed = os.path.basename(os.path.normpath(run_dir))
        t0 = time.perf_counter()
        self._simulate()
        self.replay_seconds = time.perf_counter() - t0
        if log:
            status = "identique" if self.ok else f"ÉCART {self.error:.3g} m"
            log(f"replay graine {self.seed}, gén. {self.gen}, rang {self.rank} (n°{self.index}) : "
                f"hauteur rejouée {self.height_replay:+.9f} m, stockée {self.stored['height']:+.9f} m → {status} "
                f"({self.replay_seconds:.1f} s, moteur scalaire)")

    def _simulate(self):
        c = cr.Creature(self.genome)
        self.skel = c.skel
        n_frames = int(round(config.SIM_DURATION / config.DT))
        n_points = len(c.world.pos)
        self.pos = np.empty((n_frames + 1, n_points, 2))
        self.held = np.empty((n_frames + 1, n_points), bool)
        self.activation = np.empty((n_frames + 1, len(c.activation)))
        self.t = np.empty(n_frames + 1)
        self.height = np.empty(n_frames + 1)
        self.ref_y = np.empty(n_frames + 1)

        def record(f):
            self.pos[f] = c.world.pos
            self.held[f] = c.world.held
            self.activation[f] = c.activation
            self.t[f] = c.t
            self.height[f] = c.height()
            self.ref_y[f] = c.reference_point()[1]

        record(0)
        for f in range(1, n_frames + 1):
            for _ in range(config.SUBSTEPS):
                c.substep(H)
            record(f)
        self.height_replay = c.height()
        self.error = abs(self.height_replay - self.stored["height"])
        self.ok = self.error <= 1e-9

    @property
    def n_frames(self):
        return len(self.t)

    def frame_at(self, t):
        return int(np.clip(round(t / config.DT), 0, self.n_frames - 1))

    def label(self):
        return f"graine {self.seed}, gén. {self.gen}, rang {self.rank}"


class JungleView:
    """Décor + caméra + lézard pour un replay."""

    def __init__(self, replay, framing=None, use_cache=True, log=None):
        import pygame  # noqa: F401  (initialisé par l'appelant)
        from evo import render_lizard, scene

        self.replay = replay
        self.scene = scene.Scene(framing, use_cache=use_cache, log=log)
        self.framing = self.scene.framing
        self.camera = scene.Camera(self.framing)
        self.lizard = render_lizard.LizardShape(replay.skel)

    def reset_camera(self):
        self.camera.update(self.replay.ref_y[0], snap=True)

    def draw(self, surface, frame, timings=None):
        t0 = time.perf_counter()
        self.scene.draw_back(surface, self.camera.shift)
        t1 = time.perf_counter()
        self.lizard.draw(surface, self.replay.pos[frame], self.camera.origin(), self.framing.scale)
        t2 = time.perf_counter()
        self.scene.draw_front(surface, self.camera.shift)
        t3 = time.perf_counter()
        if timings is not None:
            timings.append(((t1 - t0) + (t3 - t2), t2 - t1))


# ---------------------------------------------------------------------------
# Fenêtre interactive
# ---------------------------------------------------------------------------
def run_interactive(replay, use_cache=True, fps_report=False):
    """Espace pause · R recommencer · S ralenti ×0.25 · ←/→ image par image (en pause) · Échap."""
    import pygame

    pygame.display.init()
    screen = pygame.display.set_mode(config.WINDOW_SIZE)
    pygame.display.set_caption(f"replay : {replay.label()}")
    view = JungleView(replay, use_cache=use_cache, log=print)
    view.reset_camera()
    clock = pygame.time.Clock()
    frame_f, paused, slow = 0.0, False, False
    stamps, durations, fps_windows = [], [], []
    last_caption = time.perf_counter()
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                running = False
            elif event.type == pygame.KEYDOWN and not fps_report:
                if event.key == pygame.K_SPACE:
                    paused = not paused
                elif event.key == pygame.K_r:
                    frame_f = 0.0
                    view.reset_camera()
                elif event.key == pygame.K_s:
                    slow = not slow
                elif paused and event.key == pygame.K_RIGHT:
                    frame_f = min(frame_f + 1, replay.n_frames - 1)
                elif paused and event.key == pygame.K_LEFT:
                    frame_f = max(frame_f - 1, 0)
        frame = int(frame_f)
        view.camera.update(replay.ref_y[frame])
        view.draw(screen, frame)
        pygame.display.flip()
        clock.tick(config.FPS)
        now = time.perf_counter()
        if stamps:
            durations.append(now - stamps[-1])
        stamps.append(now)
        while stamps and now - stamps[0] > 1.0:
            stamps.pop(0)
        if len(durations) > config.FPS:   # après une seconde de chauffe
            fps_windows.append(len(stamps) - 1)
        if now - last_caption > 0.5:
            last_caption = now
            fps_now = (len(stamps) - 1) / max(stamps[-1] - stamps[0], 1e-9) if len(stamps) > 1 else 0.0
            low = min(fps_windows) if fps_windows else fps_now
            pygame.display.set_caption(f"replay : {replay.label()} · t = {replay.t[frame]:.1f} s · "
                                       f"{fps_now:.0f} fps (min {low:.0f})")
        if not paused:
            frame_f += 0.25 if slow else 1.0
            if frame_f > replay.n_frames - 1:
                if fps_report:
                    running = False
                frame_f = float(replay.n_frames - 1)
    pygame.quit()
    if durations:
        d = np.array(durations[config.FPS:] or durations)
        print(f"fps moyen {1.0 / d.mean():.1f} ; fps minimum sur une fenêtre de 1 s : "
              f"{min(fps_windows) if fps_windows else float('nan'):.0f} ; frames > 16.7 ms : "
              f"{100.0 * np.mean(d > 1 / 60 + 1e-3):.1f} % ; frame la plus longue {1000 * d.max():.1f} ms")


# ---------------------------------------------------------------------------
# Export sans écran
# ---------------------------------------------------------------------------
def reference_image(minutes, seconds):
    """Image de docs/reference/ la plus proche de l'instant demandé (règle de nommage de CLAUDE.md)."""
    target = 60 * minutes + seconds
    best, best_dt = None, None
    for path in glob.glob(os.path.join(REFERENCE_DIR, "*_t*m*s.png")):
        m = re.search(r"_t(\d+)m(\d+)s\.png$", path)
        if m:
            dt = abs(60 * int(m.group(1)) + int(m.group(2)) - target)
            if best_dt is None or dt < best_dt:
                best, best_dt = path, dt
    return best


def _caption(pygame, surface, lines, pos, font):
    pad = 8
    imgs = [font.render(line, True, pygame.Color("#FCFCFC")) for line in lines]
    w = max(i.get_width() for i in imgs) + 2 * pad
    h = sum(i.get_height() for i in imgs) + 2 * pad
    box = pygame.Surface((w, h), pygame.SRCALPHA)
    box.fill((20, 20, 20, 190))
    surface.blit(box, pos)
    y = pos[1] + pad
    for img in imgs:
        surface.blit(img, (pos[0] + pad, y))
        y += img.get_height()


def export(replay, out_dir, times=(0, 2, 4, 6, 8, 10), compare=("t8m02", "t13m55"), use_cache=True, log=print):
    """PNG aux instants demandés, planche 3×2, comparaisons côte à côte, temps par frame."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    from evo import scene

    pygame.display.init()
    pygame.font.init()
    os.makedirs(out_dir, exist_ok=True)
    w, h = config.WINDOW_SIZE
    screen = pygame.display.set_mode((w, h))
    view = JungleView(replay, use_cache=use_cache, log=log)
    view.reset_camera()
    tag = f"s{replay.seed}_g{replay.gen}_r{replay.rank}"
    wanted = {replay.frame_at(t): t for t in times}
    above10 = np.nonzero(replay.height >= 10.0)[0]
    frame_10m = int(above10[0]) if len(above10) else None
    shots, timings, paths, special = {}, [], [], {}
    for f in range(replay.n_frames):
        view.camera.update(replay.ref_y[f], snap=(f == 0))
        view.draw(screen, f, timings)
        if f in wanted:
            path = os.path.join(out_dir, f"replay_{tag}_t{int(round(wanted[f])):02d}.png")
            pygame.image.save(screen, path)
            paths.append(path)
            shots[wanted[f]] = screen.copy()
        if f == frame_10m:
            special["t13m55"] = (screen.copy(), f)
    small = pygame.font.SysFont(config.FONT_SANS, 18)

    # planche 3 × 2
    tw, th = w // 2, h // 2
    sheet = pygame.Surface((3 * tw, 2 * th))
    for k, t in enumerate(times[:6]):
        f = replay.frame_at(t)
        sheet.blit(pygame.transform.smoothscale(shots[t], (tw, th)), ((k % 3) * tw, (k // 3) * th))
        _caption(pygame, sheet, [f"t = {t:g} s   h = {replay.height[f]:+.1f} m"], ((k % 3) * tw + 8, (k // 3) * th + 8), small)
    path = os.path.join(out_dir, f"planche_{tag}.png")
    pygame.image.save(sheet, path)
    paths.append(path)

    # comparaisons côte à côte avec les images de référence
    if "t8m02" in compare:
        zoom = scene.Framing(scale=config.COMPARE_T8M02_FRAMING[0], ground_px=config.COMPARE_T8M02_FRAMING[1])
        zview = JungleView(replay, framing=zoom, use_cache=use_cache, log=log)
        zview.reset_camera()
        zview.draw(screen, 0)
        special["t8m02"] = (screen.copy(), 0)
    refs = {"t8m02": (8, 2), "t13m55": (13, 55)}
    for name in compare:
        if name not in special:
            log(f"comparaison {name} : pas d'image (la créature n'atteint pas l'instant voulu)")
            continue
        ours, f = special[name]
        ref_path = reference_image(*refs[name])
        board = pygame.Surface((2 * w, h))
        board.blit(pygame.transform.smoothscale(pygame.image.load(ref_path), (w, h)), (0, 0))
        board.blit(ours, (w, 0))
        _caption(pygame, board, [f"Référence : {os.path.basename(ref_path)}"], (8, h - 44), small)
        _caption(pygame, board, [f"Nous : {replay.label()}, t = {replay.t[f]:.2f} s, h = {replay.height[f]:+.2f} m"
                                 + (" (cadrage de l'image 01 : 28.4 px/m)" if name == "t8m02" else "")],
                 (w + 8, h - 44), small)
        path = os.path.join(out_dir, f"comparaison_{name}.png")
        pygame.image.save(board, path)
        paths.append(path)

    arr = np.array(timings) * 1000.0
    stats = {"frames": len(arr), "decor_ms_mean": float(arr[:, 0].mean()), "decor_ms_max": float(arr[:, 0].max()),
             "lizard_ms_mean": float(arr[:, 1].mean()), "lizard_ms_max": float(arr[:, 1].max()),
             "total_ms_mean": float(arr.sum(axis=1).mean()), "total_ms_p95": float(np.percentile(arr.sum(axis=1), 95)),
             "total_ms_max": float(arr.sum(axis=1).max()), "decor_built": view.scene.built,
             "replay_ok": bool(replay.ok), "height_replay": replay.height_replay, "height_stored": replay.stored["height"]}
    with open(os.path.join(out_dir, f"temps_{tag}.json"), "w") as fh:
        json.dump(stats, fh, indent=1)
    log(f"temps par frame (conteneur, sans affichage, {stats['frames']} frames) : décor {stats['decor_ms_mean']:.2f} ms "
        f"(max {stats['decor_ms_max']:.2f}), lézard {stats['lizard_ms_mean']:.2f} ms (max {stats['lizard_ms_max']:.2f}), "
        f"total {stats['total_ms_mean']:.2f} ms (p95 {stats['total_ms_p95']:.2f}, max {stats['total_ms_max']:.2f}) "
        f"pour 16.7 ms à 60 fps")
    pygame.quit()
    return paths, stats
