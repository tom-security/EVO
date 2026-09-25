"""Commande `population` (§7.1, §8) : les créatures d'une génération en miniatures, triées par rang.

Les poses finales viennent de l'évaluateur batché (evo/batch.py) : toute la génération en quelques
secondes, au lieu de 1000 replays scalaires, avec la config du run. La hauteur batchée est comparée à
la hauteur stockée. Chaque créature est une silhouette verte (LizardShape en mode silhouette) dans sa
pose finale redressée tête en haut (images 24 et 25, y compris les créatures au sol), rendue une seule
fois dans une petite surface ; une image de la vue ne coûte que le fond pré-rendu et un blit par
miniature. Grille de l'image 24 (50 × 20) :
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
    ev.use_run_config(run_dir)


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
def upright_pose(pos):
    """Pose tournée autour du centre du torse pour mettre l'axe PELVIS → NECK à la verticale, tête en
    haut (rotation seule : longueurs et côtés gauche / droit conservés), puis posée loin au-dessus du
    sol pour que le dessin ne couche pas la queue sur un sol qui n'existe plus."""
    P = np.asarray(pos, dtype=float)
    ref = 0.5 * (P[sk.NECK] + P[sk.PELVIS])
    fwd = P[sk.NECK] - P[sk.PELVIS]
    phi = 0.5 * np.pi - np.arctan2(fwd[1], fwd[0])
    c, s = np.cos(phi), np.sin(phi)
    d = P - ref
    rotated = np.column_stack([c * d[:, 0] - s * d[:, 1], s * d[:, 0] + c * d[:, 1]])
    return rotated + np.array([config.TRUNK_X, config.GROUND_Y + config.POP_MINI_LIFT])


def render_miniature(skel, pos, scale=None):
    """Silhouette d'une créature dans sa pose finale, centrée sur son point de référence (torse),
    redressée tête en haut si POP_MINI_UPRIGHT.

    Renvoie (surface, (dx, dy)) : coin haut gauche de la surface par rapport au centre de la case.
    """
    from evo.render_lizard import LizardShape

    scale = config.POP_MINI_SCALE if scale is None else scale
    if config.POP_MINI_UPRIGHT:
        pos = upright_pose(pos)
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
# Cycle complet (§7.1) : apparition, tri, histogramme, élimination des perdantes, enfants
# ---------------------------------------------------------------------------
class Offspring:
    """La génération N+1 vue depuis la génération N (lignée des .npz) : les survivantes sont les S meilleures de
    N, dans l'ordre (elles gardent leur case triée) ; l'enfant de la survivante de rang j apparaît dans la case
    libérée S + j, juste sous son parent. Les enfants ne sont pas encore évalués : posture de repos."""

    def __init__(self, generation):
        run_dir, gen = generation.run_dir, generation.gen + 1
        if gen not in ev.saved_generations(run_dir):
            raise FileNotFoundError(f"pas de génération {gen} dans {run_dir} : le cycle de la génération "
                                    f"{generation.gen} montre ses enfants (choisis --gen N avec N+1 sauvegardée)")
        pop, _, lineage, _ = ev.load_generation(run_dir, gen)
        order = ev.ranking(generation.results["score"])
        child = lineage["is_child"]
        s = int(np.sum(~child))
        parents = lineage["parent"]
        if not (np.array_equal(parents[:s], order[:s]) and child[s:].all()
                and np.array_equal(parents[s:], order[:len(parents) - s])):
            raise ValueError(f"lignée inattendue entre les générations {generation.gen} et {gen}")
        self.gen, self.n_survivors = gen, s
        self.index = np.arange(s, len(parents))                 # indices des enfants dans la génération N+1
        self.parent_rank = np.arange(len(parents) - s)          # rang (génération N) du parent de chaque enfant
        self.slots = s + self.parent_rank                       # case libérée sous le parent
        self.skeletons, self.poses = [], []
        for i in self.index:
            c = cr.Creature(pop.genome(i))                      # posture de repos, au départ
            self.skeletons.append(c.skel)
            self.poses.append(c.world.pos.copy())


def cycle_phases():
    """{phase: (début, fin)} en s : apparition, tri, histogramme, élimination, enfants, fin (tenue)."""
    spans = (("apparition", config.POP_APPEAR_S + config.POP_FADE_S), ("tri", config.POP_SORT_S),
             ("histogramme", config.POP_CYCLE_HIST_S), ("elimination", config.POP_ELIM_S),
             ("enfants", config.POP_CHILD_S), ("fin", config.VIDEO_HOLD_S))
    out, t = {}, 0.0
    for name, duration in spans:
        out[name] = (t, t + duration)
        t += duration + (config.POP_PAUSE_S if name != "fin" else 0.0)
    return out


def sweep_time(start, duration, col, n_cols):
    """Instant où un balayage de gauche à droite commencé à `start` atteint la colonne `col`."""
    return start + duration * col / n_cols


class CycleView:
    """Cycle complet de la génération N ; `draw(surface, t)` pour t de 0 à `duration`."""

    def __init__(self, generation, offspring, size=None):
        import pygame

        self.base = PopulationView(generation, size)
        convert = pygame.display.get_surface() is not None
        t0 = time.perf_counter()
        self.children = []
        for skel, pos in zip(offspring.skeletons, offspring.poses):
            surf, offset = render_miniature(skel, pos)
            self.children.append((surf.convert_alpha() if convert else surf, offset))
        self.render_seconds = self.base.render_seconds + time.perf_counter() - t0
        hist, _ = _histogram_surface(generation)
        self.hist = hist.convert() if convert else hist
        self.offspring = offspring
        self.phases = cycle_phases()
        self.duration = self.phases["fin"][1]
        cols, rows = config.POPULATION_GRID
        n = len(generation)
        self.n_cols = cols
        self.n_appear_cols = int(np.ceil(n / rows))
        self.appear_col = np.arange(n) // rows                   # colonne de la place de calcul
        self.sorted_col = generation.slots % cols
        self.loser = generation.slots >= offspring.n_survivors
        self.child_col = offspring.slots % cols
        self.child_xy = np.rint(slot_centers(offspring.slots)).astype(int)

    def alphas(self, t):
        """Opacité de chaque créature de la génération N et de chaque enfant à l'instant t."""
        ph = self.phases
        a0, _ = ph["apparition"]
        reveal = a0 + config.POP_APPEAR_S * self.appear_col / self.n_appear_cols
        alpha = np.clip((t - reveal) / config.POP_FADE_S, 0.0, 1.0)
        gone = t >= sweep_time(ph["elimination"][0], config.POP_ELIM_S, self.sorted_col, self.n_cols)
        alpha = np.where(self.loser & gone, 0.0, alpha)
        born = t >= sweep_time(ph["enfants"][0], config.POP_CHILD_S, self.child_col, self.n_cols)
        return alpha, born.astype(float)

    def positions(self, t):
        s0, _ = self.phases["tri"]
        u = min(max((t - s0) / config.POP_SORT_S, 0.0), 1.0)
        u = u * u * (3.0 - 2.0 * u)
        return self.base.start + (self.base.end - self.base.start) * u

    def draw(self, surface, t):
        h0, h1 = self.phases["histogramme"]
        if h0 <= t < h1:
            surface.blit(self.hist, (0, 0))
            return
        surface.blit(self.base.background, (0, 0))
        xy = np.rint(self.positions(t)).astype(int)
        alpha, born = self.alphas(t)
        minis = self.base.minis
        solid, fading = [], []
        for i in self.base.draw_order:
            if alpha[i] >= 1.0:
                solid.append((minis[i][0], (xy[i, 0] + minis[i][1][0], xy[i, 1] + minis[i][1][1])))
            elif alpha[i] > 0.0:
                fading.append(i)
        surface.blits(solid, doreturn=False)
        for i in fading:                                        # fondu d'apparition : opacité de surface
            surf, (dx, dy) = minis[i]
            surf.set_alpha(int(round(255 * alpha[i])))
            surface.blit(surf, (xy[i, 0] + dx, xy[i, 1] + dy))
            surf.set_alpha(255)          # et non None, qui couperait aussi la transparence par pixel
        surface.blits([(surf, (x + dx, y + dy)) for (surf, (dx, dy)), (x, y), b
                       in zip(self.children, self.child_xy, born) if b], doreturn=False)


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


def run_interactive(generation, offspring=None):
    """Fenêtre 1280×720 à 60 fps. R : recommencer, Espace : pause, H : histogramme, Échap : quitter.
    Avec `offspring` (Offspring) : cycle complet au lieu du tri seul."""
    import pygame

    pygame.display.init()
    screen = pygame.display.set_mode(config.WINDOW_SIZE)
    pygame.display.set_caption(f"Population, génération {generation.gen} (graine {generation.seed})")
    view = PopulationView(generation) if offspring is None else CycleView(generation, offspring)
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


def _board(pygame, left, right, captions, font, zooms=()):
    """Référence | nous, côte à côte ; chaque zoom (x, y, w, h, facteur, légende) ajoute une rangée agrandie."""
    from evo.replay import _caption

    w, h = left.get_size()
    board = pygame.Surface((2 * w, h + sum(z[3] * z[4] for z in zooms)))
    board.fill((0, 0, 0))
    for k, img in enumerate((left, right)):
        board.blit(img, (k * w, 0))
        _caption(pygame, board, [captions[k]], (k * w + 8, h - 44), font)
        y0 = h
        for x, y, zw, zh, f, label in zooms:
            crop = img.subsurface((x, y, zw, zh)).copy()
            board.blit(pygame.transform.scale(crop, (zw * f, zh * f)), (k * w, y0))
            _caption(pygame, board, [label], (k * w + 8, y0 + zh * f - 44), font)
            y0 += zh * f
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
                   small, zooms=((50, 45, 320, 130, 4, "×4 : 4 premières lignes (les meilleures)"),
                                 (50, 538, 320, 130, 4, "×4 : 4 dernières lignes (les pires, au sol)")))
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


def export_cycle(generation, offspring, out_dir, log=print):
    """Cycle complet : images clés, comparaison avec l'image 25 (élimination), temps (JSON)."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    from evo.replay import reference_image

    pygame.display.init()
    pygame.font.init()
    os.makedirs(out_dir, exist_ok=True)
    screen = pygame.display.set_mode(config.WINDOW_SIZE)
    view = CycleView(generation, offspring)
    ph = view.phases
    frame_ms = []
    for t in np.arange(0.0, view.duration, config.DT):
        t0 = time.perf_counter()
        view.draw(screen, t)
        frame_ms.append((time.perf_counter() - t0) * 1000.0)
    frame_ms = np.array(frame_ms)
    cols = view.n_cols
    # élimination à 6 colonnes (image 25 : colonnes 0 à 5 du bas déjà vides)
    t_elim6 = sweep_time(ph["elimination"][0], config.POP_ELIM_S, 6, cols) - 1e-6
    keys = (("1_apparition_mi", ph["apparition"][0] + config.POP_APPEAR_S / 2),
            ("2_apparition_finie", ph["apparition"][1]),
            ("3_triee", ph["tri"][1]),
            ("4_histogramme", ph["histogramme"][0] + 0.1),
            ("5_elimination_6_colonnes", t_elim6),
            ("6_elimination_finie", ph["elimination"][1]),
            ("7_enfants_mi", sweep_time(ph["enfants"][0], config.POP_CHILD_S, cols // 2, cols) - 1e-6),
            ("8_fin", ph["fin"][0]))
    tag = f"s{generation.seed}_g{generation.gen}"
    paths, shots = [], {}
    for name, t in keys:
        view.draw(screen, t)
        shots[name] = screen.copy()
        path = os.path.join(out_dir, f"cycle_{tag}_{name}.png")
        pygame.image.save(screen, path)
        paths.append(path)
    small = pygame.font.SysFont(config.FONT_SANS, 18)
    ref = reference_image(11, 20)
    board = _board(pygame, pygame.image.load(ref).convert(), shots["5_elimination_6_colonnes"],
                   [f"Référence : {os.path.basename(ref)}",
                    f"Nous : graine {generation.seed}, génération {generation.gen}, 6 colonnes éliminées"],
                   small, zooms=((50, 330, 320, 130, 4, "×4 : lignes 9 à 12, colonnes 0 à 13 (survivantes en haut, perdantes éliminées dans les colonnes 0 à 5)"),))
    path = os.path.join(out_dir, "comparaison_t11m20.png")
    pygame.image.save(board, path)
    paths.append(path)
    stats = {"gen": generation.gen, "next_gen": offspring.gen, "survivors": offspring.n_survivors,
             "children": len(offspring.index), "phases_s": {k: [round(a, 3), round(b, 3)] for k, (a, b) in ph.items()},
             "duration_s": view.duration, "miniatures_s": view.render_seconds,
             "frame_ms_mean": float(frame_ms.mean()), "frame_ms_p95": float(np.percentile(frame_ms, 95)),
             "frame_ms_max": float(frame_ms.max())}
    with open(os.path.join(out_dir, f"temps_cycle_{tag}.json"), "w") as fh:
        json.dump(stats, fh, indent=1)
    log(f"cycle gén. {generation.gen} → {offspring.gen} : {offspring.n_survivors} survivantes gardent leur case, "
        f"{len(offspring.index)} enfants sous leur parent ; {view.duration:.1f} s ; miniatures {view.render_seconds:.2f} s ; "
        f"une image {stats['frame_ms_mean']:.2f} ms (p95 {stats['frame_ms_p95']:.2f}, max {stats['frame_ms_max']:.2f})")
    pygame.quit()
    return paths, stats
