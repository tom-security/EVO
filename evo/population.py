"""Commande `population` (§7.1, §8) : les créatures d'une génération en miniatures, triées par rang.

Les poses finales viennent de l'évaluateur batché (evo/batch.py) : toute la génération en quelques
secondes, au lieu de 1000 replays scalaires, avec la config du run. La hauteur batchée est comparée à
la hauteur stockée. Chaque créature est une silhouette verte (LizardShape en mode silhouette) rendue
une seule fois dans une petite surface ; une image de la vue ne coûte que le fond pré-rendu et un
blit par miniature. Grille de l'image 24 (50 × 20) :
- place de calcul = indice dans le npz, rangé en colonnes (les colonnes apparaissent de gauche à
  droite pendant l'évaluation, §7.1) ;
- place triée = rang, en lecture par lignes (1 = en haut à gauche) ;
- le tri anime chaque miniature de l'une à l'autre (ease-in-out).
L'apparition colonne par colonne et la disparition des 500 perdantes sont pour la phase 5c.
"""
import json
import os
import time

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import numpy as np

import config
from evo import batch
from evo import creature as cr
from evo import evolution as ev
from evo import skeleton as sk


# ---------------------------------------------------------------------------
# Grille et tri
# ---------------------------------------------------------------------------
def slot_centers(slots):
    """Centre (px) des cases, numérotées en lecture par lignes : 0 = en haut à gauche."""
    cols, _ = config.POPULATION_GRID
    s = np.asarray(slots)
    (ox, oy), (px, py) = config.POP_ORIGIN, config.POP_PITCH
    return np.column_stack([ox + (s % cols) * px, oy + (s // cols) * py])


def compute_slots(n):
    """Case de calcul de chaque créature (indice du npz) : la grille se remplit colonne par colonne."""
    cols, rows = config.POPULATION_GRID
    if n > cols * rows:
        raise ValueError(f"{n} créatures pour une grille de {cols} × {rows}")
    i = np.arange(n)
    return (i % rows) * cols + i // rows


def sorted_slots(scores):
    """Case triée de chaque créature : son rang (0 = meilleur score), en lecture par lignes."""
    order = ev.ranking(scores)
    slots = np.empty(len(order), dtype=np.int64)
    slots[order] = np.arange(len(order))
    return slots


def sort_progress(t):
    """Avancement du tri (0 → 1) à l'instant t de la vue : attente, puis ease-in-out."""
    u = min(max((t - config.POP_SORT_DELAY_S) / config.POP_SORT_S, 0.0), 1.0)
    return u * u * (3.0 - 2.0 * u)


def sort_end():
    return config.POP_SORT_DELAY_S + config.POP_SORT_S


# ---------------------------------------------------------------------------
# Données : poses finales par l'évaluateur batché
# ---------------------------------------------------------------------------
def load_run_config(run_dir):
    """Config du run (comme pour un replay), pour réévaluer à l'identique."""
    with open(os.path.join(run_dir, "config.json")) as fh:
        ev.apply_config(json.load(fh), strict=False)
    cr._torque_unit.cache_clear()


class Generation:
    """Une génération sauvegardée, réévaluée d'un bloc : pose finale et hauteur de chaque créature."""

    def __init__(self, run_dir, gen=None, log=print):
        self.run_dir = run_dir
        self.seed = os.path.basename(os.path.normpath(run_dir))
        load_run_config(run_dir)
        gens = ev.saved_generations(run_dir)
        if not gens:
            raise FileNotFoundError(f"aucune génération sauvegardée dans {run_dir}")
        self.gen = gens[-1] if gen is None else gen
        t0 = time.perf_counter()
        self.pop, self.results, _, _ = ev.load_generation(run_dir, self.gen)
        genomes = self.pop.to_genomes()
        t1 = time.perf_counter()
        batch.evaluate(genomes[:2], duration=0.1)   # chauffe : compilation ou lecture du cache numba
        t2 = time.perf_counter()
        out = batch.evaluate(genomes, duration=config.SIM_DURATION)
        t3 = time.perf_counter()
        self.pos = out["pos"]
        self.height = out["height"]
        self.error = float(np.max(np.abs(self.height - self.results["height"])))
        self.ok = self.error <= 1e-9
        self.slots = sorted_slots(self.results["score"])
        self.skeletons = [sk.build_skeleton({n: float(v) for n, v in zip(cr.BONE_NAMES, lengths)},
                                            head_length=config.HEAD_LENGTH * config.BODY_SCALE)
                          for lengths in self.pop.lengths]
        self.timings = {"load_s": t1 - t0, "numba_warmup_s": t2 - t1, "evaluate_s": t3 - t2,
                        "skeletons_s": time.perf_counter() - t3, "threads": batch.get_num_threads()}
        if log:
            status = "identiques" if self.ok else f"ÉCART max {self.error:.3g} m"
            log(f"population graine {self.seed}, gén. {self.gen} : {len(self)} créatures réévaluées en "
                f"{self.timings['evaluate_s']:.1f} s (évaluateur batché, {self.timings['threads']} cœurs ; "
                f"chauffe numba {self.timings['numba_warmup_s']:.1f} s) ; hauteurs batchées et stockées {status}")

    def __len__(self):
        return len(self.height)

    def histogram(self):
        return ev.histogram(self.height)


# ---------------------------------------------------------------------------
# Vue
# ---------------------------------------------------------------------------
def render_miniature(skel, pos, scale=None):
    """Silhouette d'une créature dans sa pose (monde), centrée sur son point de référence (torse).

    Renvoie (surface, (dx, dy)) : coin haut gauche de la surface par rapport au centre de la case.
    """
    from evo.render_lizard import LizardShape

    scale = config.POP_MINI_SCALE if scale is None else scale
    ref = 0.5 * (pos[sk.NECK] + pos[sk.PELVIS])
    dot_color, dot_px = config.POP_MINI_DOT
    return LizardShape(skel).render(pos, (-ref[0] * scale, ref[1] * scale), scale,
                                    silhouette=(config.POP_MINI_COLOR, dot_color, dot_px / scale))


class PopulationView:
    """Grille des miniatures et tri animé ; `draw(surface, t)` compose une image à l'instant t."""

    def __init__(self, generation, size=None):
        import pygame
        from evo import charts

        self.generation = generation
        size = size or config.WINDOW_SIZE
        convert = pygame.display.get_surface() is not None
        t0 = time.perf_counter()
        self.background = charts.vignette(size)
        self.minis = []
        for skel, pos in zip(generation.skeletons, generation.pos):
            surf, offset = render_miniature(skel, pos)
            self.minis.append((surf.convert_alpha() if convert else surf, offset))
        self.render_seconds = time.perf_counter() - t0
        n = len(generation)
        self.start = slot_centers(compute_slots(n))
        self.end = slot_centers(generation.slots)
        self.draw_order = np.argsort(-generation.slots, kind="stable")   # les meilleures dessinées en dernier

    def positions(self, t):
        return self.start + (self.end - self.start) * sort_progress(t)

    def draw(self, surface, t):
        surface.blit(self.background, (0, 0))
        xy = np.rint(self.positions(t)).astype(int)
        minis = self.minis
        surface.blits([(minis[i][0], (xy[i, 0] + minis[i][1][0], xy[i, 1] + minis[i][1][1]))
                       for i in self.draw_order], doreturn=False)


# ---------------------------------------------------------------------------
# Mesures de comparaison (image 24 contre notre vue)
# ---------------------------------------------------------------------------
def measure_grid(surface):
    """Médianes mesurées sur une vue population : taille des miniatures, couleurs, fond."""
    import pygame

    a = pygame.surfarray.array3d(surface).transpose(1, 0, 2).astype(int)
    h, w = a.shape[:2]
    cols, rows = config.POPULATION_GRID
    body = (a[:, :, 1] - a[:, :, 0] > 30) & (a[:, :, 1] - a[:, :, 2] > 30)
    loose = (a[:, :, 1] - a[:, :, 0] > 8) & (a[:, :, 1] - a[:, :, 2] > 8)
    dots = (a[:, :, 2] > 100) & (a[:, :, 1] > 170)
    centers = slot_centers(np.arange(cols * rows))
    (px, py) = config.POP_PITCH
    heights, widths, tops, bottoms = [], [], [], []
    for cx, cy in centers:
        x0, x1 = max(int(cx - px / 2 + 1), 0), min(int(cx + px / 2), w)
        y0, y1 = max(int(cy - py / 2 + 1), 0), min(int(cy + py / 2), h)
        ys, xs = np.nonzero(loose[y0:y1, x0:x1])
        if len(ys):
            heights.append(ys.max() - ys.min() + 1)
            widths.append(xs.max() - xs.min() + 1)
            tops.append(ys.min() + y0 - cy)
            bottoms.append(ys.max() + y0 - cy)
    yy, xx = np.mgrid[0:h, 0:w]
    d = np.hypot((xx + 0.5 - w / 2) / (w / 2), (yy + 0.5 - h / 2) / (h / 2))
    gray = (np.ptp(a, axis=2) <= 3) & (a.mean(axis=2) < 45)
    bg = {f"{lo:.1f}": float(np.median(a.mean(axis=2)[gray & (d >= lo) & (d < lo + 0.1)]))
          for lo in (0.0, 0.5, 1.0, 1.3)}

    def hex_median(mask):
        return "#%02X%02X%02X" % tuple(int(v) for v in np.median(a[mask], axis=0)) if mask.any() else None

    return {"cells": len(heights), "height_px": float(np.median(heights)), "width_px": float(np.median(widths)),
            "top_px": float(np.median(tops)), "bottom_px": float(np.median(bottoms)),
            "body_color": hex_median(body), "dot_color": hex_median(dots), "background": bg}


# ---------------------------------------------------------------------------
# Interactif et export
# ---------------------------------------------------------------------------
def _histogram_surface(generation):
    from evo import charts

    counts = generation.histogram()
    return charts.histogram_chart(dict(zip(ev.HIST_COLUMNS, counts)), style="video"), counts


def run_interactive(generation):
    """Fenêtre 1280×720 à 60 fps. R : recommencer le tri, Espace : pause, H : histogramme, Échap : quitter."""
    import pygame

    pygame.display.init()
    screen = pygame.display.set_mode(config.WINDOW_SIZE)
    pygame.display.set_caption(f"Population, génération {generation.gen} (graine {generation.seed})")
    view = PopulationView(generation)
    hist, _ = _histogram_surface(generation)
    hist = hist.convert()
    clock = pygame.time.Clock()
    t, paused, show_hist, running = 0.0, False, False, True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                t, paused, show_hist = 0.0, False, False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                paused = not paused
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_h:
                show_hist = not show_hist
        if show_hist:
            screen.blit(hist, (0, 0))
        else:
            view.draw(screen, t)
        pygame.display.flip()
        dt = clock.tick(config.FPS) / 1000.0
        if not paused:
            t += dt
    pygame.quit()


def _board(pygame, left, right, captions, font, zoom=None):
    """Référence | nous, côte à côte ; `zoom` = (x, y, w, h, facteur) ajoute une rangée agrandie."""
    from evo.replay import _caption

    w, h = left.get_size()
    zh = 0 if zoom is None else zoom[3] * zoom[4]
    board = pygame.Surface((2 * w, h + zh))
    board.fill((0, 0, 0))
    for k, img in enumerate((left, right)):
        board.blit(img, (k * w, 0))
        if zoom is not None:
            x, y, zw, zhh, f = zoom
            crop = img.subsurface((x, y, zw, zhh)).copy()
            board.blit(pygame.transform.scale(crop, (zw * f, zhh * f)), (k * w, h))
        _caption(pygame, board, [captions[k]], (k * w + 8, h - 44), font)
    return board


def export(generation, out_dir, log=print):
    """PNG de la vue (calcul, mi-tri, triée), histogramme, comparaisons, temps et mesures (JSON)."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    from evo import charts
    from evo.replay import reference_image

    pygame.display.init()
    pygame.font.init()
    os.makedirs(out_dir, exist_ok=True)
    screen = pygame.display.set_mode(config.WINDOW_SIZE)
    tag = f"s{generation.seed}_g{generation.gen}"
    paths = []
    view = PopulationView(generation)

    # animation complète à 60 images/s : temps de composition d'une image
    times = np.arange(0.0, sort_end() + 0.5, config.DT)
    frame_ms = []
    for t in times:
        t0 = time.perf_counter()
        view.draw(screen, t)
        frame_ms.append((time.perf_counter() - t0) * 1000.0)
    frame_ms = np.array(frame_ms)
    shots = {}
    for name, t in (("calcul", 0.0), ("tri_mi", config.POP_SORT_DELAY_S + config.POP_SORT_S / 2),
                    ("triee", sort_end())):
        view.draw(screen, t)
        shots[name] = screen.copy()
        path = os.path.join(out_dir, f"population_{tag}_{name}.png")
        pygame.image.save(screen, path)
        paths.append(path)

    t0 = time.perf_counter()
    hist, counts = _histogram_surface(generation)
    hist_s = time.perf_counter() - t0
    path = os.path.join(out_dir, f"histogramme_{tag}.png")
    pygame.image.save(hist, path)
    paths.append(path)
    clipped = charts.clipped_bars(counts)
    if clipped:
        log(f"histogramme : barres tronquées à {config.HIST_VIDEO['y_max']} : {clipped}")

    small = pygame.font.SysFont(config.FONT_SANS, 18)
    ref_pop = pygame.image.load(reference_image(10, 49)).convert()
    ref_hist = pygame.image.load(reference_image(15, 45)).convert()
    board = _board(pygame, ref_pop, shots["triee"],
                   [f"Référence : {os.path.basename(reference_image(10, 49))} (génération 0)",
                    f"Nous : graine {generation.seed}, génération {generation.gen}, triée"],
                   small, zoom=(50, 45, 240, 130, 4))
    path = os.path.join(out_dir, "comparaison_population.png")
    pygame.image.save(board, path)
    paths.append(path)
    board = _board(pygame, ref_hist, hist,
                   [f"Référence : {os.path.basename(reference_image(15, 45))}",
                    f"Nous : graine {generation.seed}, génération {generation.gen}"], small)
    path = os.path.join(out_dir, "comparaison_histogramme.png")
    pygame.image.save(board, path)
    paths.append(path)

    lo = config.HIST_RANGE[0]
    h = generation.height
    stats = {
        "n": len(generation), "gen": generation.gen, "seed": generation.seed,
        "heights_ok": bool(generation.ok), "height_max_error_m": generation.error,
        "timings": dict(generation.timings, miniatures_s=view.render_seconds, histogram_s=hist_s,
                        frame_ms_mean=float(frame_ms.mean()), frame_ms_p95=float(np.percentile(frame_ms, 95)),
                        frame_ms_max=float(frame_ms.max()), frames=len(frame_ms)),
        "histogram": {"sum": int(counts.sum()), "counts": {f"{lo + k:+d}": int(c) for k, c in enumerate(counts)},
                      "clipped": clipped, "bin_min10": int(counts[0]),
                      "share_30_35": float(np.mean((h >= 30) & (h < 35))),
                      "fallen": int(generation.results["fallen"].sum()), "height_max": float(h.max()),
                      "height_median": float(np.median(h))},
        "mesures": {"reference_24": measure_grid(ref_pop), "nous": measure_grid(shots["triee"])},
    }
    with open(os.path.join(out_dir, "temps_population.json"), "w") as fh:
        json.dump(stats, fh, indent=1)
    tm = stats["timings"]
    total = tm["load_s"] + tm["numba_warmup_s"] + tm["evaluate_s"] + tm["skeletons_s"] + tm["miniatures_s"]
    log(f"temps : lecture {tm['load_s']:.2f} s, chauffe numba {tm['numba_warmup_s']:.2f} s, évaluation "
        f"{tm['evaluate_s']:.2f} s, squelettes {tm['skeletons_s']:.2f} s, miniatures {tm['miniatures_s']:.2f} s "
        f"→ {total:.1f} s ; histogramme {hist_s * 1000:.0f} ms ; une image de la vue {tm['frame_ms_mean']:.2f} ms "
        f"(p95 {tm['frame_ms_p95']:.2f}, max {tm['frame_ms_max']:.2f})")
    hs = stats["histogram"]
    ref = charts.REFERENCE_HIST.get(generation.gen)
    log(f"histogramme : somme {hs['sum']}, barre −10 m {hs['bin_min10']}, {hs['share_30_35'] * 100:.0f} % entre 30 et "
        f"35 m, au sol {hs['fallen']}, max {hs['height_max']:.1f} m" + (f" ({ref})" if ref else ""))
    pygame.quit()
    return paths, stats
