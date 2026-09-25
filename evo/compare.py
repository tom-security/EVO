"""Commande `compare` (§7.5, §8) : champions de plusieurs générations en fantômes sur la même scène.

Détail non montré par la vidéo (image 37, t ≈ 16:48 : fantômes presque superposés près du départ, plusieurs
libellés « Génération N » superposés) ; choix :
- chaque champion est rejoué (moteur scalaire, hauteur vérifiée comme pour `replay`) ; tous partent ensemble
  et sont montrés au même instant t, chacun à sa propre hauteur ;
- décor du replay sans le premier plan (ses canopées les cacheraient), à une échelle fixe calculée pour que le
  plus grand écart entre les torses tienne dans l'écran (COMPARE_FIT) ; la caméra vise le milieu entre le plus
  haut et le plus bas ;
- fantômes semi-transparents, de plus en plus opaques avec la génération, dessinés du plus ancien au plus
  récent ; un libellé souligné par fantôme, les libellés espacés pour ne jamais se chevaucher.
"""
import json
import math
import os
import time

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import numpy as np

import config
from evo import skeleton as sk


def fitted_scale(replays, height=None):
    """Échelle (px/m) du cadrage fixe : le plus grand écart entre les torses tient avec les marges."""
    h = (config.WINDOW_SIZE[1] if height is None else height)
    ys = np.stack([r.ref_y for r in replays])
    spread = float((ys.max(axis=0) - ys.min(axis=0)).max())
    top, bottom = config.COMPARE_MARGINS
    return min(config.SCENE_SCALE, math.floor(10.0 * h / (spread + top + bottom)) / 10.0)


def camera_track(replays, framing):
    """Hauteur visée par la caméra à chaque frame (même rôle que ref_y pour le replay) : le milieu entre le
    plus haut et le plus bas, borné pour garder chacun à l'écran avec les marges ; priorité au plus haut."""
    ys = np.stack([r.ref_y for r in replays])
    hi, lo = ys.max(axis=0), ys.min(axis=0)
    # la caméra garde le point visé à la hauteur écran du départ : `above` m au-dessus, `below` m en dessous
    y_ref = framing.y_px(config.GROUND_Y + config.START_HEIGHT)
    above, below = y_ref / framing.scale, (framing.size[1] - y_ref) / framing.scale
    top, bottom = config.COMPARE_MARGINS
    lowest_target = hi - (above - top)        # plus bas, le plus haut sortirait par le haut
    highest_target = lo + (below - bottom)    # plus haut, le plus bas sortirait par le bas
    mid = 0.5 * (hi + lo)
    fits = lowest_target <= highest_target
    return np.where(fits, np.clip(mid, lowest_target, np.maximum(lowest_target, highest_target)), lowest_target)


def ghost_alphas(n):
    """Opacité de chaque fantôme, du plus ancien au plus récent."""
    a0, a1 = config.COMPARE_GHOST_ALPHA
    return [a1] if n == 1 else [float(a) for a in np.linspace(a0, a1, n)]


def label_layout(anchor_ys, ink_height, screen_height, gens=None):
    """Ordonnée (px) du souligné de chaque libellé : décalage de COMPARE_LABEL depuis le NECK, puis, du plus
    haut au plus bas à l'écran, écart minimal (hauteur d'encre + écart + trait + spacing) ; la pile reste
    dans l'écran. Deux fantômes à moins d'un écart l'un de l'autre sont rangés par génération, la plus
    récente au-dessus (au départ, quand ils se superposent)."""
    lab = config.COMPARE_LABEL
    thick, gap, _, _ = lab["underline"]
    step = ink_height + gap + thick + lab["spacing"]
    wanted = np.asarray(anchor_ys, float) + lab["offset"][1]
    order = list(np.argsort(wanted, kind="stable"))
    if gens is not None:
        swapped = True
        while swapped:
            swapped = False
            for k in range(len(order) - 1):
                a, b = order[k], order[k + 1]
                if wanted[b] - wanted[a] < step and gens[b] > gens[a]:
                    order[k], order[k + 1] = b, a
                    swapped = True
    ys = np.empty(len(wanted))
    prev = -np.inf
    for i in order:
        ys[i] = prev = max(wanted[i], prev + step)
    top_limit, bottom_limit = ink_height + gap + 2, screen_height - thick - 2
    if len(ys):
        ys += max(0.0, top_limit - ys.min())               # pas au-dessus de l'écran
        ys -= max(0.0, ys.max() - bottom_limit)            # ni en dessous (la pile remonte en bloc)
    return ys


def sheet_cells(n, cols=3):
    """(colonne, ligne) de chaque instant dans la planche, et (colonnes, lignes) : aucune case vide si n % cols == 0."""
    rows = int(math.ceil(n / cols))
    return [(k % cols, k // cols) for k in range(n)], (min(cols, n), rows)


class CompareView:
    """Décor + fantômes + libellés ; mêmes méthodes que JungleView (run_interactive, export)."""

    def __init__(self, replays, use_cache=True, log=None):
        import pygame
        from evo import fonts, render_lizard, scene

        self.replays = sorted(replays, key=lambda r: r.gen)
        self.replay = self.replays[-1]                       # la plus récente
        scale = fitted_scale(self.replays) if config.COMPARE_FIT else config.SCENE_SCALE
        layers = scene.BACK_LAYERS + (scene.FRONT_LAYERS if config.COMPARE_FRONT_LAYER else ())
        self.scene = scene.Scene(scene.Framing(scale=scale), layers=layers, use_cache=use_cache, log=log)
        self.framing = self.scene.framing
        self.camera = scene.Camera(self.framing)
        self.lizards = [render_lizard.LizardShape(r.skel) for r in self.replays]
        self.alphas = [int(round(255 * a)) for a in ghost_alphas(len(self.replays))]
        self.track = camera_track(self.replays, self.framing)
        font = fonts.load(*config.COMPARE_LABEL["font"])
        white = pygame.Color("#FFFFFF")
        self.labels = [font.render(f"Génération {r.gen}", True, white) for r in self.replays]
        # ombres pré-rendues du texte et du souligné (1 px en bas à droite)
        shade, shade_alpha = pygame.Color(config.COMPARE_LABEL_SHADOW[0]), int(round(255 * config.COMPARE_LABEL_SHADOW[1]))
        thick, _, before, after = config.COMPARE_LABEL["underline"]
        self.shadows = []
        for r, ink in zip(self.replays, [s.get_bounding_rect() for s in self.labels]):
            text = font.render(f"Génération {r.gen}", True, shade)
            text.set_alpha(shade_alpha)
            bar = pygame.Surface((before + ink.width + after, thick))
            bar.fill(shade)
            bar.set_alpha(shade_alpha)
            self.shadows.append((text, bar))
        self.label_inks = [s.get_bounding_rect() for s in self.labels]
        self.ink_height = max(ink.height for ink in self.label_inks)

    @property
    def n_frames(self):
        return min(r.n_frames for r in self.replays)

    def follow(self, frame):
        self.camera.update(self.track[frame])

    def reset_camera(self):
        self.camera.update(self.track[0], snap=True)

    def torso_px(self, frame):
        """Ordonnée à l'écran du torse de chaque fantôme."""
        return [self.framing.y_px(r.ref_y[frame], self.camera.shift) for r in self.replays]

    def label_rects(self, frame):
        """Ancre (NECK, px), début du souligné (px) et rectangle occupé (texte + souligné) de chaque libellé."""
        import pygame

        lab = config.COMPARE_LABEL
        thick, gap, before, after = lab["underline"]
        origin, scale = self.camera.origin(), self.framing.scale
        anchors = [(origin[0] + r.pos[frame][sk.NECK][0] * scale, origin[1] - r.pos[frame][sk.NECK][1] * scale)
                   for r in self.replays]
        ys = label_layout([a[1] for a in anchors], self.ink_height, self.framing.size[1],
                          gens=[r.gen for r in self.replays])
        out = []
        for (ax, ay), uy, ink in zip(anchors, ys, self.label_inks):
            ux = ax + lab["offset"][0]
            rect = pygame.Rect(round(ux), round(uy - gap - self.ink_height), before + ink.width + after,
                               self.ink_height + gap + thick)
            out.append(((ax, ay), (ux, uy), rect))
        return out

    def draw(self, surface, frame, timings=None, speed=1.0, hud=None):
        import pygame

        t0 = time.perf_counter()
        self.scene.draw_back(surface, self.camera.shift)
        t1 = time.perf_counter()
        origin, scale = self.camera.origin(), self.framing.scale
        for r, lizard, alpha in zip(self.replays, self.lizards, self.alphas):   # du plus ancien au plus récent
            drawn = lizard.render(r.pos[frame], origin, scale, clip=surface.get_size())
            if drawn is not None:
                canvas, xy = drawn
                canvas.set_alpha(alpha)
                surface.blit(canvas, xy)
        t2 = time.perf_counter()
        self.scene.draw_front(surface, self.camera.shift)
        t3 = time.perf_counter()
        # un libellé souligné par fantôme, trait de rappel depuis son NECK (image 37) ; traits d'abord, textes par-dessus
        lab = config.COMPARE_LABEL
        thick, gap, before, after = lab["underline"]
        white = pygame.Color("#FFFFFF")
        placed = self.label_rects(frame)
        # ombre de 1 px sous le texte et le souligné (lisibles sur un nuage blanc), puis le libellé
        for (_, (ux, uy), _), (text, bar), ink in zip(placed, self.shadows, self.label_inks):
            surface.blit(bar, (round(ux) + 1, round(uy) + 1))
            surface.blit(text, (round(ux + before - ink.left) + 1, round(uy - gap - ink.bottom) + 1))
        for (ax, ay), (ux, uy), _ in placed:
            pygame.draw.line(surface, white, (ax, ay), (ux, uy + thick / 2), lab["line"])
            pygame.draw.aaline(surface, white, (ax, ay), (ux, uy + thick / 2))
        for (_, (ux, uy), _), label, ink in zip(placed, self.labels, self.label_inks):
            surface.fill(white, pygame.Rect(round(ux), round(uy), before + ink.width + after, thick))
            surface.blit(label, (round(ux + before - ink.left), round(uy - gap - ink.bottom)))
        t4 = time.perf_counter()
        if timings is not None:
            timings.append(((t1 - t0) + (t3 - t2), t2 - t1, t4 - t3, self.scene.front_coverage(self.camera.shift)))


def load_champions(run_dir, gens, log=print):
    from evo.replay import Replay

    return [Replay(run_dir, gen=g, rank=1, log=log) for g in gens]


def _heights_lines(view, frame):
    items = [f"gén. {r.gen} {r.height[frame]:+.1f} m" for r in view.replays]
    half = (len(items) + 1) // 2
    return [" · ".join(items[:half]), " · ".join(items[half:])] if len(items) > 2 else [" · ".join(items)]


def export(replays, out_dir, times=None, use_cache=True, log=print):
    """PNG aux instants demandés, planche, comparaison avec l'image 37, temps et positions à l'écran (JSON)."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    from evo.replay import _caption, frame_stats, reference_image

    times = tuple(config.COMPARE_EXPORT_TIMES if times is None else times)
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
    shots, timings, paths, screen_y = {}, [], [], {}
    for f in range(view.n_frames):
        view.follow(f)
        view.draw(screen, f, timings)
        if f in wanted:
            t = wanted[f]
            shots[t] = (screen.copy(), _heights_lines(view, f))
            screen_y[f"{t:g}"] = {str(r.gen): round(y, 1) for r, y in zip(view.replays, view.torso_px(f))}
            path = os.path.join(out_dir, f"comparaison_{tag}_t{t:04.1f}.png")
            pygame.image.save(screen, path)
            paths.append(path)
    # planche : une case par instant, légende dans un bandeau sous l'image (elle ne cache aucun fantôme)
    cells, (cols, rows) = sheet_cells(len(times))
    tw, th, band = w // 2, h // 2, 70
    sheet = pygame.Surface((cols * tw, rows * (th + band)))
    sheet.fill((20, 20, 20))
    for (c, r_), t in zip(cells, times):
        img, lines = shots[t]
        x, y = c * tw, r_ * (th + band)
        sheet.blit(pygame.transform.smoothscale(img, (tw, th)), (x, y))
        for k, line in enumerate([f"t = {t:g} s"] + lines):
            sheet.blit(small.render(line, True, pygame.Color("#FCFCFC")), (x + 10, y + th + 4 + 21 * k))
    path = os.path.join(out_dir, f"planche_{tag}.png")
    pygame.image.save(sheet, path)
    paths.append(path)
    ref = reference_image(16, 48)
    img, lines = shots[times[0]]
    board = pygame.Surface((2 * w, h))
    board.blit(pygame.transform.smoothscale(pygame.image.load(ref), (w, h)), (0, 0))
    board.blit(img, (w, 0))
    _caption(pygame, board, [f"Référence : {os.path.basename(ref)}"], (8, h - 44), small)
    _caption(pygame, board, [f"Nous : graine {seed}, t = {times[0]:g} s, {view.framing.scale:g} px/m ; " + " · ".join(lines)],
             (w + 8, h - 44), small)
    path = os.path.join(out_dir, "comparaison_t16m48.png")
    pygame.image.save(board, path)
    paths.append(path)

    st = frame_stats(np.array(timings)[:, :3] * 1000.0)
    stats = {"frames": st, "gens": [r.gen for r in view.replays], "ghost_alpha": ghost_alphas(len(view.replays)),
             "scale_px_per_m": view.framing.scale, "replays_ok": all(r.ok for r in view.replays),
             "torso_screen_y_px": screen_y,
             "heights": {str(r.gen): {f"{t:g}": float(r.height[view.replay.frame_at(t)]) for t in times} for r in view.replays}}
    with open(os.path.join(out_dir, f"temps_{tag}.json"), "w") as fh:
        json.dump(stats, fh, indent=1)
    log(f"cadrage : {view.framing.scale:g} px/m (vue normale {config.SCENE_SCALE:g}), plus grand écart entre les torses "
        f"{float(np.ptp(np.stack([r.ref_y for r in view.replays]), axis=0).max()):.1f} m")
    for t, ys in screen_y.items():
        inside = all(0 <= y <= h for y in ys.values())
        log(f"t = {t} s : torses à y = " + ", ".join(f"gén. {g} {y:.0f} px" for g, y in ys.items())
            + (" → tous à l'écran" if inside else " → au moins un hors de l'écran"))
    log(f"temps par frame (comparaison, {len(view.replays)} fantômes, {st['frames']} frames ; conteneur, sans affichage) : "
        f"décor {st['decor_ms_mean']:.2f} ms (max {st['decor_ms_max']:.2f}), fantômes {st['lizard_ms_mean']:.2f} ms "
        f"(max {st['lizard_ms_max']:.2f}), libellés {st['hud_ms_mean']:.2f} ms, total {st['total_ms_mean']:.2f} ms "
        f"(p95 {st['total_ms_p95']:.2f}, max {st['total_ms_max']:.2f}), > 16.7 ms : {st['over_budget'] * 100:.1f} %")
    pygame.quit()
    return paths, stats
