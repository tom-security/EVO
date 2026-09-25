"""Commande `compare` (§7.5, §8) : champions de plusieurs générations en fantômes sur la même scène.

Détail non montré par la vidéo (image 37, t ≈ 16:48 : fantômes presque superposés près du départ, libellé
« Génération 200 ») ; choix : chaque champion est rejoué (moteur scalaire, hauteur vérifiée comme pour
`replay`), tous partent ensemble et sont montrés au même instant t, chacun à sa propre hauteur. Décor du
replay (cadrage normal, sans le premier plan qui les cacherait), fantômes semi-transparents du plus ancien au plus récent,
libellé souligné sur la génération la plus récente. La caméra suit le plus haut en gardant les autres à
l'écran tant que l'écart le permet.
"""
import json
import os
import time

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import numpy as np

import config
from evo import skeleton as sk


def camera_track(replays, framing):
    """Hauteur visée par la caméra à chaque frame (même rôle que ref_y pour le replay)."""
    ys = np.stack([r.ref_y for r in replays])
    hi, lo = ys.max(axis=0), ys.min(axis=0)
    # la caméra garde le point visé à la hauteur écran du départ : il reste `above` m au-dessus
    above = framing.y_px(config.GROUND_Y + config.START_HEIGHT) / framing.scale
    return np.maximum(0.5 * (hi + lo), hi - (above - config.COMPARE_TOP_MARGIN))


class CompareView:
    """Décor + fantômes + libellé ; mêmes méthodes que JungleView (run_interactive, export)."""

    def __init__(self, replays, use_cache=True, log=None):
        import pygame
        from evo import fonts, render_lizard, scene

        self.replays = sorted(replays, key=lambda r: r.gen)
        self.replay = self.replays[-1]                       # la plus récente, qui porte le libellé
        layers = scene.BACK_LAYERS + (scene.FRONT_LAYERS if config.COMPARE_FRONT_LAYER else ())
        self.scene = scene.Scene(None, layers=layers, use_cache=use_cache, log=log)
        self.framing = self.scene.framing
        self.camera = scene.Camera(self.framing)
        self.lizards = [render_lizard.LizardShape(r.skel) for r in self.replays]
        self.track = camera_track(self.replays, self.framing)
        lab = config.COMPARE_LABEL
        self.label = fonts.load(*lab["font"]).render(f"Génération {self.replay.gen}", True, pygame.Color("#FFFFFF"))
        self.label_ink = self.label.get_bounding_rect()
        self.alpha = int(round(255 * config.COMPARE_GHOST_ALPHA))

    @property
    def n_frames(self):
        return min(r.n_frames for r in self.replays)

    def follow(self, frame):
        self.camera.update(self.track[frame])

    def reset_camera(self):
        self.camera.update(self.track[0], snap=True)

    def draw(self, surface, frame, timings=None, speed=1.0, hud=None):
        import pygame

        t0 = time.perf_counter()
        self.scene.draw_back(surface, self.camera.shift)
        t1 = time.perf_counter()
        origin, scale = self.camera.origin(), self.framing.scale
        for r, lizard in zip(self.replays, self.lizards):
            drawn = lizard.render(r.pos[frame], origin, scale, clip=surface.get_size())
            if drawn is not None:
                canvas, xy = drawn
                canvas.set_alpha(self.alpha)
                surface.blit(canvas, xy)
        t2 = time.perf_counter()
        self.scene.draw_front(surface, self.camera.shift)
        t3 = time.perf_counter()
        # libellé souligné, trait de rappel depuis le NECK de la plus récente (image 37)
        lab = config.COMPARE_LABEL
        neck = self.replay.pos[frame][sk.NECK]
        ax, ay = origin[0] + neck[0] * scale, origin[1] - neck[1] * scale
        thick, gap, before, after = lab["underline"]
        ux, uy = ax + lab["offset"][0], ay + lab["offset"][1]
        ink = self.label_ink
        white = pygame.Color("#FFFFFF")
        surface.fill(white, pygame.Rect(round(ux), round(uy), before + ink.width + after, thick))
        surface.blit(self.label, (round(ux + before - ink.left), round(uy - gap - ink.bottom)))
        pygame.draw.line(surface, white, (ax, ay), (ux, uy + thick / 2), lab["line"])
        pygame.draw.aaline(surface, white, (ax, ay), (ux, uy + thick / 2))
        t4 = time.perf_counter()
        if timings is not None:
            timings.append(((t1 - t0) + (t3 - t2), t2 - t1, t4 - t3, self.scene.front_coverage(self.camera.shift)))


def load_champions(run_dir, gens, log=print):
    from evo.replay import Replay

    return [Replay(run_dir, gen=g, rank=1, log=log) for g in gens]


def export(replays, out_dir, times=(0.5, 2.0, 4.0, 6.4, 10.0), use_cache=True, log=print):
    """PNG aux instants demandés, planche, comparaison avec l'image 37, temps par frame (JSON)."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    from evo.replay import _caption, frame_stats, reference_image

    pygame.display.init()
    pygame.font.init()
    os.makedirs(out_dir, exist_ok=True)
    w, h = config.WINDOW_SIZE
    screen = pygame.display.set_mode((w, h))
    view = CompareView(replays, use_cache=use_cache, log=log)
    view.reset_camera()
    seed = view.replay.seed
    tag = f"s{seed}_g" + "-".join(str(r.gen) for r in view.replays)
    wanted = {view.replay.frame_at(t): t for t in times}
    small = pygame.font.SysFont(config.FONT_SANS, 18)
    shots, timings, paths = {}, [], []
    for f in range(view.n_frames):
        view.follow(f)
        view.draw(screen, f, timings)
        if f in wanted:
            t = wanted[f]
            heights = ", ".join(f"gén. {r.gen} {r.height[f]:+.1f} m" for r in view.replays)
            shots[t] = (screen.copy(), heights)
            path = os.path.join(out_dir, f"comparaison_{tag}_t{t:04.1f}.png")
            pygame.image.save(screen, path)
            paths.append(path)
    tw, th = w // 2, h // 2
    sheet = pygame.Surface((3 * tw, 2 * th))
    for k, t in enumerate(times[:6]):
        img, heights = shots[t]
        sheet.blit(pygame.transform.smoothscale(img, (tw, th)), ((k % 3) * tw, (k // 3) * th))
        _caption(pygame, sheet, [f"t = {t:g} s", heights], ((k % 3) * tw + 8, (k // 3) * th + th - 62), small)
    path = os.path.join(out_dir, f"planche_{tag}.png")
    pygame.image.save(sheet, path)
    paths.append(path)
    ref = reference_image(16, 48)
    img, heights = shots[times[0]]
    board = pygame.Surface((2 * w, h))
    board.blit(pygame.transform.smoothscale(pygame.image.load(ref), (w, h)), (0, 0))
    board.blit(img, (w, 0))
    _caption(pygame, board, [f"Référence : {os.path.basename(ref)}"], (8, h - 44), small)
    _caption(pygame, board, [f"Nous : graine {seed}, t = {times[0]:g} s ; {heights}"], (w + 8, h - 44), small)
    path = os.path.join(out_dir, "comparaison_t16m48.png")
    pygame.image.save(board, path)
    paths.append(path)

    st = frame_stats(np.array(timings)[:, :3] * 1000.0)
    stats = {"frames": st, "gens": [r.gen for r in view.replays], "ghost_alpha": config.COMPARE_GHOST_ALPHA,
             "replays_ok": all(r.ok for r in view.replays),
             "heights": {str(r.gen): {f"{t:g}": float(r.height[view.replay.frame_at(t)]) for t in times} for r in view.replays}}
    with open(os.path.join(out_dir, f"temps_{tag}.json"), "w") as fh:
        json.dump(stats, fh, indent=1)
    log(f"temps par frame (comparaison, {len(view.replays)} fantômes, {st['frames']} frames ; conteneur, sans affichage) : "
        f"décor {st['decor_ms_mean']:.2f} ms (max {st['decor_ms_max']:.2f}), fantômes {st['lizard_ms_mean']:.2f} ms "
        f"(max {st['lizard_ms_max']:.2f}), libellé {st['hud_ms_mean']:.2f} ms, total {st['total_ms_mean']:.2f} ms "
        f"(p95 {st['total_ms_p95']:.2f}, max {st['total_ms_max']:.2f}), > 16.7 ms : {st['over_budget'] * 100:.1f} %")
    pygame.quit()
    return paths, stats
