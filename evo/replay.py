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
# mesure des temps : une canopée du premier plan est « à l'écran » quand elle couvre au moins 5 % de
# l'image (les lianes seules, visibles dès le départ comme sur l'image 03, ne comptent pas)
CANOPY_COVERAGE = 0.05
BIG_CANOPY_COVERAGE = 0.20
REFERENCE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "reference")


class Replay:
    """Une créature d'une génération sauvegardée, rejouée et enregistrée frame par frame."""

    def __init__(self, run_dir, gen=None, rank=1, index=None, log=print):
        self.run_dir = run_dir
        self.by_index = index is not None   # rejoué par indice : le HUD affiche « Créature: i »
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
                f"hauteur rejouée {self.height_replay:+.9f} m, stockée {self.stored['height']:+.9f} m → {status} ; "
                f"énergie {self.energy[-1]:.4f} (stockée {self.stored['energy']:.4f}) ({self.replay_seconds:.1f} s, moteur scalaire)")

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
        self.energy = np.empty(n_frames + 1)   # énergie cumulée du HUD (ENERGY_SCALE inclus, comme dans le run)

        def record(f):
            self.pos[f] = c.world.pos
            self.held[f] = c.world.held
            self.activation[f] = c.activation
            self.t[f] = c.t
            self.height[f] = c.height()
            self.ref_y[f] = c.reference_point()[1]
            self.energy[f] = c.energy

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

    @property
    def creature_number(self):
        """Numéro affiché « Créature: i » (indice + 1, comme « Créature: 1 » de l'image 03)."""
        return self.index + 1

    def label(self):
        who = f"créature {self.creature_number}" if self.by_index else f"rang {self.rank}"
        return f"graine {self.seed}, gén. {self.gen}, {who}"


def frame_stats(arr):
    """Statistiques de temps (ms) : colonnes décor, lézard, HUD."""
    if not len(arr):
        return {"frames": 0}
    total = arr.sum(axis=1)
    out = {"frames": int(len(arr)), "total_ms_mean": float(total.mean()), "total_ms_p95": float(np.percentile(total, 95)),
           "total_ms_max": float(total.max()), "over_budget": float(np.mean(total > 1000.0 / 60))}
    for k, name in enumerate(("decor", "lizard", "hud")):
        out[f"{name}_ms_mean"], out[f"{name}_ms_max"] = float(arr[:, k].mean()), float(arr[:, k].max())
    return out


def crossing_frames(heights, markers):
    """Pour chaque repère : première frame où la hauteur HUD l'atteint (None s'il n'est jamais atteint)."""
    out = {}
    for hud in markers:
        idx = np.nonzero(np.asarray(heights) >= hud)[0]
        out[hud] = int(idx[0]) if len(idx) else None
    return out


class JungleView:
    """Décor + caméra + lézard pour un replay."""

    def __init__(self, replay, framing=None, use_cache=True, log=None, hud=True, subtitle=None):
        import pygame  # noqa: F401  (initialisé par l'appelant)
        from evo import hud as hud_mod
        from evo import render_lizard, scene

        self.replay = replay
        self.scene = scene.Scene(framing, use_cache=use_cache, log=log)
        self.framing = self.scene.framing
        self.camera = scene.Camera(self.framing)
        self.lizard = render_lizard.LizardShape(replay.skel)
        # repères : frame du premier franchissement vers le haut de la hauteur HUD (jamais redéclenché)
        self.crossings = crossing_frames(replay.height, self.scene.markers)
        self.hud = hud_mod.Hud(self.framing, replay.gen, replay.genome.period, replay.genome.muscle_mass(),
                               rank=None if replay.by_index else replay.rank,
                               creature=replay.creature_number if replay.by_index else None,
                               subtitle=subtitle) if hud else None

    def marker_alphas(self, frame):
        from evo.scene import marker_alpha
        return {hud: marker_alpha((frame - f0) * config.DT) for hud, f0 in self.crossings.items()
                if f0 is not None and frame >= f0}

    def reset_camera(self):
        self.camera.update(self.replay.ref_y[0], snap=True)

    def draw(self, surface, frame, timings=None, speed=1.0, hud=True):
        t0 = time.perf_counter()
        self.scene.draw_back(surface, self.camera.shift)
        if not (hud and self.hud is not None):
            # repères seulement sans HUD : avec HUD, l'étiquette de hauteur les remplace (images 03, 05, 09 ;
            # repères visibles seulement dans les vues sans HUD, images 06 et 08)
            self.scene.draw_markers(surface, self.camera.shift, self.marker_alphas(frame))
        t1 = time.perf_counter()
        self.lizard.draw(surface, self.replay.pos[frame], self.camera.origin(), self.framing.scale)
        t2 = time.perf_counter()
        self.scene.draw_front(surface, self.camera.shift)
        t3 = time.perf_counter()
        if hud and self.hud is not None:   # par-dessus tout : l'étiquette reste visible sous une canopée
            r = self.replay
            ref_px = self.framing.y_px(r.ref_y[frame], self.camera.shift)
            self.hud.draw(surface, r.t[frame], r.height[frame], r.energy[frame], ref_px, speed=speed)
        t4 = time.perf_counter()
        if timings is not None:
            timings.append(((t1 - t0) + (t3 - t2), t2 - t1, t4 - t3, self.scene.front_coverage(self.camera.shift)))


# ---------------------------------------------------------------------------
# Fenêtre interactive
# ---------------------------------------------------------------------------
def run_interactive(replay, use_cache=True, fps_report=False, speed=1.0, subtitle=None, make_view=None, slow=False):
    """Espace pause · R recommencer · S ralenti ×0.25 · F accéléré (×FAST_SPEED) · ←/→ image par image
    (en pause) · Échap.

    `make_view` : fabrique d'une autre vue à jouer avec les mêmes touches (mode analyse, comparaison de
    générations), appelée une fois la fenêtre ouverte ; la vue fournit draw(), reset_camera(), scene, et
    follow(frame) si sa caméra ne suit pas simplement `replay`.
    """
    import pygame

    pygame.display.init()
    screen = pygame.display.set_mode(config.WINDOW_SIZE)
    pygame.display.set_caption(f"replay : {replay.label()}")
    if make_view is None:
        view = JungleView(replay, use_cache=use_cache, log=print, subtitle=subtitle)
    else:
        view = make_view()
    follow = getattr(view, "follow", None) or (lambda f: view.camera.update(replay.ref_y[f]))
    view.reset_camera()
    fast = speed if speed > 1 else config.FAST_SPEED
    clock = pygame.time.Clock()
    frame_f, paused = 0.0, False
    stamps, durations, fps_windows, canopy = [], [], [], []
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
                elif event.key == pygame.K_f:
                    speed = 1.0 if speed > 1 else float(fast)
                elif paused and event.key == pygame.K_RIGHT:
                    frame_f = min(frame_f + 1, replay.n_frames - 1)
                elif paused and event.key == pygame.K_LEFT:
                    frame_f = max(frame_f - 1, 0)
        frame = int(frame_f)
        follow(frame)
        view.draw(screen, frame, speed=speed)
        pygame.display.flip()
        clock.tick(config.FPS)
        now = time.perf_counter()
        if stamps:
            durations.append(now - stamps[-1])
            canopy.append(view.scene.front_coverage(view.camera.shift) >= CANOPY_COVERAGE)
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
            frame_f += (config.SLOW_SPEED if slow else 1.0) * speed
            if frame_f > replay.n_frames - 1:
                if fps_report:
                    running = False
                frame_f = float(replay.n_frames - 1)
    pygame.quit()
    if durations:
        skip = config.FPS if len(durations) > 2 * config.FPS else 0
        d, on = np.array(durations[skip:]), np.array(canopy[skip:], bool)
        print(f"fps moyen {1.0 / d.mean():.1f} ; fps minimum sur une fenêtre de 1 s : "
              f"{min(fps_windows) if fps_windows else float('nan'):.0f} ; frames > 16.7 ms : "
              f"{100.0 * np.mean(d > 1 / 60 + 1e-3):.1f} % ; frame la plus longue {1000 * d.max():.1f} ms")
        if on.any():
            dc = d[on]
            print(f"frames avec une canopée à l'écran (≥ {CANOPY_COVERAGE:.0%} de l'image, {len(dc)}) : fps moyen {1.0 / dc.mean():.1f} ; "
                  f"frames > 16.7 ms : {100.0 * np.mean(dc > 1 / 60 + 1e-3):.1f} % ; la plus longue {1000 * dc.max():.1f} ms")


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


COMPARISONS = {   # nom → (instant de la vidéo, HUD affiché ?, description de notre image)
    "t8m02": ((8, 2), False, "champion à t = 0, cadrage serré de l'image 01"),
    "t10m14": ((10, 14), True, "génération 0, créature 1 à t = 0.5 s, carton « Le commencement »"),
    "t10m20": ((10, 20), True, "génération 0, créature 1 à t = 6.5 s"),
    "t13m55": ((13, 55), False, "champion au passage de +10 m"),
    "t14m35": ((14, 35), True, "champion à t = 6.4 s"),
}
FIRST_CARD_SUBTITLE = "Le commencement"   # [VU] image 39


def export(replay, out_dir, times=(0, 2, 4, 6, 8, 10), compare=tuple(COMPARISONS), use_cache=True, log=print,
           subtitle=None):
    """PNG aux instants demandés (avec HUD), planche 3×2, comparaisons côte à côte, temps par frame."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    from evo import scene

    pygame.display.init()
    pygame.font.init()
    os.makedirs(out_dir, exist_ok=True)
    w, h = config.WINDOW_SIZE
    screen = pygame.display.set_mode((w, h))
    view = JungleView(replay, use_cache=use_cache, log=log, subtitle=subtitle)
    view.reset_camera()
    tag = f"s{replay.seed}_g{replay.gen}_" + (f"c{replay.creature_number}" if replay.by_index else f"r{replay.rank}")
    wanted = {replay.frame_at(t): t for t in times}
    above10 = np.nonzero(replay.height >= 10.0)[0]
    frame_10m = int(above10[0]) if len(above10) else None
    frame_6s4 = replay.frame_at(6.4)
    shots, timings, paths, special = {}, [], [], {}
    for f in range(replay.n_frames):
        view.camera.update(replay.ref_y[f], snap=(f == 0))
        if f == frame_10m:   # image 06 : sans HUD
            view.draw(screen, f, hud=False)
            special["t13m55"] = (screen.copy(), f, replay)
        view.draw(screen, f, timings)
        if f in wanted:
            path = os.path.join(out_dir, f"replay_{tag}_t{int(round(wanted[f])):02d}.png")
            pygame.image.save(screen, path)
            paths.append(path)
            shots[wanted[f]] = screen.copy()
        if f == frame_6s4:
            special["t14m35"] = (screen.copy(), f, replay)
    small = pygame.font.SysFont(config.FONT_SANS, 18)

    # planche 3 × 2
    tw, th = w // 2, h // 2
    sheet = pygame.Surface((3 * tw, 2 * th))
    for k, t in enumerate(times[:6]):
        f = replay.frame_at(t)
        sheet.blit(pygame.transform.smoothscale(shots[t], (tw, th)), ((k % 3) * tw, (k // 3) * th))
        _caption(pygame, sheet, [f"t = {t:g} s   h = {replay.height[f]:+.1f} m"], ((k % 3) * tw + 8, (k // 3) * th + th - 44), small)
    path = os.path.join(out_dir, f"planche_{tag}.png")
    pygame.image.save(sheet, path)
    paths.append(path)

    # comparaisons côte à côte avec les images de référence
    if "t8m02" in compare:
        zoom = scene.Framing(scale=config.COMPARE_T8M02_FRAMING[0], ground_px=config.COMPARE_T8M02_FRAMING[1])
        zview = JungleView(replay, framing=zoom, use_cache=use_cache, log=log, hud=False)
        zview.reset_camera()
        zview.draw(screen, 0, hud=False)
        special["t8m02"] = (screen.copy(), 0, replay)
    if "t10m20" in compare or "t10m14" in compare:   # « Génération 0, Créature 1 » : première créature
        first = Replay(replay.run_dir, gen=0, index=0, log=log)
        fview = JungleView(first, use_cache=use_cache, subtitle=FIRST_CARD_SUBTITLE)
        for name, t_shot in (("t10m14", 0.5), ("t10m20", 6.5)):
            target = first.frame_at(t_shot)
            fview.reset_camera()
            for f in range(target + 1):
                fview.camera.update(first.ref_y[f], snap=(f == 0))
            fview.draw(screen, target)
            special[name] = (screen.copy(), target, first)
    for name in compare:
        if name not in special:
            log(f"comparaison {name} : pas d'image (la créature n'atteint pas l'instant voulu)")
            continue
        ours, f, rep = special[name]
        ref_path = reference_image(*COMPARISONS[name][0])
        board = pygame.Surface((2 * w, h))
        board.blit(pygame.transform.smoothscale(pygame.image.load(ref_path), (w, h)), (0, 0))
        board.blit(ours, (w, 0))
        _caption(pygame, board, [f"Référence : {os.path.basename(ref_path)}"], (8, h - 44), small)
        _caption(pygame, board, [f"Nous : {rep.label()}, t = {rep.t[f]:.2f} s, h = {rep.height[f]:+.2f} m"
                                 + (" (cadrage de l'image 01 : 28.4 px/m)" if name == "t8m02" else "")],
                 (w + 8, h - 44), small)
        path = os.path.join(out_dir, f"comparaison_{name}.png")
        pygame.image.save(board, path)
        paths.append(path)

    t = np.array(timings)
    arr, coverage = t[:, :3] * 1000.0, t[:, 3]
    stats = {"frames": len(arr), "decor_built": view.scene.built, "replay_ok": bool(replay.ok),
             "height_replay": replay.height_replay, "height_stored": replay.stored["height"],
             "hud_text_renders": view.hud.renders if view.hud else 0}
    classes = (("toutes", np.ones(len(arr), bool)), ("canopee", coverage >= CANOPY_COVERAGE),
               ("grande_canopee", coverage >= BIG_CANOPY_COVERAGE))
    for key, mask in classes:
        stats[key] = frame_stats(arr[mask])
        stats[key]["coverage_max"] = float(coverage[mask].max()) if mask.any() else 0.0
    with open(os.path.join(out_dir, f"temps_{tag}.json"), "w") as fh:
        json.dump(stats, fh, indent=1)
    for key, label in (("toutes", "toutes les frames"),
                       ("canopee", f"frames avec une canopée à l'écran (premier plan ≥ {CANOPY_COVERAGE:.0%} de l'image)"),
                       ("grande_canopee", f"frames où le premier plan couvre ≥ {BIG_CANOPY_COVERAGE:.0%} de l'image")):
        st = stats[key]
        if st["frames"]:
            log(f"temps par frame, {label} ({st['frames']} frames ; conteneur, sans affichage) : décor {st['decor_ms_mean']:.2f} ms "
                f"(max {st['decor_ms_max']:.2f}), lézard {st['lizard_ms_mean']:.2f} ms (max {st['lizard_ms_max']:.2f}), "
                f"HUD {st['hud_ms_mean']:.2f} ms (max {st['hud_ms_max']:.2f}), total {st['total_ms_mean']:.2f} ms "
                f"(p95 {st['total_ms_p95']:.2f}, max {st['total_ms_max']:.2f}), > 16.7 ms : {st['over_budget'] * 100:.1f} %")
    log(f"HUD : {stats['hud_text_renders']} textes rendus pour {len(arr)} frames (cache par valeur affichée)")
    pygame.quit()
    return paths, stats
