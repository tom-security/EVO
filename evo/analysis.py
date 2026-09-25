"""Commande `analyze` (§7.4, §8) : zoom sur une créature rejouée, surcouche muscles + os (§5.5).

- Caméra zoomée (ANALYSIS_SCALE, image 11) qui suit le torse en lerp comme le replay ; décor du replay
  construit à ce zoom (sans le premier plan), visible sur les bords du tronc.
- Surcouche recalculée à chaque frame depuis les points, dans la même toile que le lézard : os crème
  (traits, articulations en disques, NECK et PELVIS plus gros), puis les 16 muscles (8 par côté) en formes
  courbes ancrées aux insertions. Taille ∝ force max évoluée (génome) ; couleur de #FC5464 à #FC0434 selon
  la contraction instantanée = activation enregistrée par le replay ÷ force max du muscle.
- Un libellé par muscle, « 76% » = force max en % de S_MAX, relié au muscle par un trait blanc ; les
  libellés apparaissent un par un. Ralenti ×0.25 : touche S du replay, ou --slow.
"""
import json
import os
import time

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import numpy as np

import config
from evo import creature as cr
from evo import skeleton as sk

# points de chaque côté : épaule, coude, main, hanche, genou, pied
_SIDE_POINTS = ((sk.L_SHOULDER, sk.L_ELBOW, sk.L_HAND, sk.L_HIP, sk.L_KNEE, sk.L_FOOT),
                (sk.R_SHOULDER, sk.R_ELBOW, sk.R_HAND, sk.R_HIP, sk.R_KNEE, sk.R_FOOT))
_BONES = np.array([(sk.NECK, sk.PELVIS)] + [pair for sh, el, ha, hip, kn, ft in _SIDE_POINTS
                                              for pair in ((sk.NECK, sh), (sh, el), (el, ha), (sk.PELVIS, hip),
                                                           (hip, kn), (kn, ft))])
SHOULDER, ELBOW, HIP, KNEE = range(4)   # types d'articulation (evo/creature.py)
PLUS, MINUS = 0, 1


def _unit(v):
    n = float(np.hypot(v[0], v[1]))
    return v / n if n > 1e-12 else np.array([0.0, 1.0])


def _rot90(v):
    return np.array([-v[1], v[0]])


def _mix(a, b, u):
    ca, cb = np.array(_rgb(a), float), np.array(_rgb(b), float)
    return tuple(int(round(x)) for x in ca + (cb - ca) * min(max(u, 0.0), 1.0))


def _rgb(color):
    if isinstance(color, tuple):
        return color[:3]
    c = color.lstrip("#")
    return tuple(int(c[k:k + 2], 16) for k in (0, 2, 4))


# ---------------------------------------------------------------------------
# Surcouche anatomique (§5.5)
# ---------------------------------------------------------------------------
class Anatomy:
    """Os et muscles d'une créature, à partir des proportions du dessin (LizardShape) et du génome."""

    def __init__(self, shape, genome):
        self.shape = shape
        self.strength = np.asarray(genome.strengths, float)          # (côté, articulation, sens)
        self.frac = self.strength / config.S_MAX
        w = shape.w_limb
        bone, joint, big = config.ANALYSIS_BONE_SIZES
        self.bone_w, self.joint_r, self.big_r = bone * w, joint * w, big * w
        self.fiber_white, fiber_w = config.ANALYSIS_FIBER
        self.fiber_w = fiber_w * w
        self.s_plus = self.strength[:, :, PLUS].reshape(-1)
        self.s_minus = self.strength[:, :, MINUS].reshape(-1)

    def contraction(self, activation):
        """(2, 4, 2) : part de sa force max qu'utilise chaque muscle à cet instant (0–1)."""
        a = np.asarray(activation, float)
        plus = np.where(self.s_plus > 0, np.clip(a, 0.0, None) / np.maximum(self.s_plus, 1e-12), 0.0)
        minus = np.where(self.s_minus > 0, np.clip(-a, 0.0, None) / np.maximum(self.s_minus, 1e-12), 0.0)
        return np.minimum(np.stack([plus, minus], axis=1).reshape(2, 4, 2), 1.0)

    # --- géométrie des muscles (m, monde) -----------------------------------------
    def muscles(self, P):
        """{(côté, articulation, sens): (contour, fibres, ancre)} ; contour None pour une force nulle."""
        P = np.asarray(P, float)
        neck, pelvis = P[sk.NECK], P[sk.PELVIS]
        spine = pelvis - neck
        tri = config.ANALYSIS_TRIANGLE
        out = {}
        for s, (sh, el, _, hip, kn, _) in enumerate(_SIDE_POINTS):
            f = self.frac[s]

            def depth(frac):
                return tri["depth"] * (tri["min"] + (1.0 - tri["min"]) * frac)

            out[(s, SHOULDER, MINUS)] = self._triangle(neck, P[sh], neck + spine * depth(f[SHOULDER, MINUS]),
                                                       tri["bulge"][0], f[SHOULDER, MINUS])
            out[(s, HIP, PLUS)] = self._triangle(pelvis, P[hip], pelvis - spine * depth(f[HIP, PLUS]),
                                                 tri["bulge"][1], f[HIP, PLUS])
            out[(s, SHOULDER, PLUS)] = self._oval(P[sh], P[el], f[SHOULDER, PLUS])
            out[(s, HIP, MINUS)] = self._oval(P[hip], P[kn], f[HIP, MINUS])
            # coude et genou : le muscle « + » est du côté vers lequel il fait tourner l'os distal (couple
            # τ > 0 : rotation dans le sens trigonométrique, evo/physics.contraction_forces)
            for joint, a, b in ((ELBOW, sh, el), (KNEE, hip, kn)):
                n = cr.JOINT_SIGNS[s * 4 + joint] * _rot90(_unit(P[b] - P[a]))
                out[(s, joint, PLUS)] = self._spindle(P[a], P[b], n, f[joint, PLUS])
                out[(s, joint, MINUS)] = self._spindle(P[a], P[b], -n, f[joint, MINUS])
        return out

    def _triangle(self, base, outer, apex, bulge, frac):
        """Base sur l'os (NECK → épaule ou PELVIS → hanche), pointe sur la colonne, bord extérieur courbé."""
        edge = apex - outer
        away = _rot90(_unit(edge))
        if np.dot(away, outer - base) < 0:
            away = -away
        control = 0.5 * (outer + apex) + away * bulge * float(np.hypot(*edge))
        u = np.linspace(0.0, 1.0, 9)[:, None]
        curve = (1 - u) ** 2 * outer + 2 * (1 - u) * u * control + u ** 2 * apex
        contour = np.vstack([base, curve])
        fibers = [np.array([apex, base + (outer - base) * k]) for k in (0.3, 0.6, 0.85)]
        return (contour if frac > 0 else None), fibers, (base + outer + apex) / 3.0

    def _oval(self, a, b, frac):
        u0, u1, width = config.ANALYSIS_OVAL
        d = b - a
        axis, n = _unit(d), _rot90(_unit(d))
        length = float(np.hypot(*d))
        center = a + d * (u0 + u1) / 2
        ra, rb = length * (u1 - u0) / 2, width * self.shape.w_limb * frac
        ang = np.linspace(0.0, 2 * np.pi, 24, endpoint=False)[:, None]
        contour = center + axis * ra * np.cos(ang) + n * rb * np.sin(ang)
        x = np.linspace(-0.85, 0.85, 7)[:, None]
        fibers = [center + axis * ra * x + n * k * rb * np.sqrt(1 - x ** 2) for k in (-0.45, 0.45)]
        return (contour if frac > 0 else None), fibers, center

    def _spindle(self, a, b, n, frac):
        """Fuseau le long de l'os a → b, du côté n ; ses pointes sont sur l'os (insertions)."""
        u0, u1, width = config.ANALYSIS_SPINDLE
        v = np.linspace(0.0, 1.0, 13)[:, None]
        bone = a + (b - a) * (u0 + (u1 - u0) * v)
        w = width * self.shape.w_limb * frac * np.sin(np.pi * v) ** 0.8
        mid = bone + n * 0.55 * w
        contour = np.vstack([mid + n * w, (mid - n * w)[::-1]])
        fibers = [mid + n * k * w for k in (-0.45, 0.45)]
        return (contour if frac > 0 else None), fibers, mid[len(mid) // 2]

    # --- formes à dessiner ----------------------------------------------------------
    def shapes(self, P, activation, muscles=None):
        """(couleur, forme) en m, pour LizardShape.render(extra=…) : os, articulations, puis muscles."""
        P = np.asarray(P, float)
        cream = config.ANALYSIS_BONE
        # os : un quadrilatère par os (les disques des articulations en arrondissent les bouts)
        a, b = P[_BONES[:, 0]], P[_BONES[:, 1]]
        d = b - a
        n = np.column_stack([-d[:, 1], d[:, 0]])
        n *= (self.bone_w / 2) / np.maximum(np.hypot(n[:, 0], n[:, 1]), 1e-12)[:, None]
        quads = np.stack([a + n, b + n, b - n, a - n], axis=1)
        out = [(cream, q) for q in quads]
        for points in _SIDE_POINTS:
            for p in points:
                out.append((cream, ("cercle", P[p], self.joint_r)))
        out.append((cream, ("cercle", P[sk.NECK], self.big_r)))
        out.append((cream, ("cercle", P[sk.PELVIS], self.big_r)))
        muscles = self.muscles(P) if muscles is None else muscles
        c = self.contraction(activation)
        order = [(SHOULDER, MINUS), (HIP, PLUS), (ELBOW, PLUS), (ELBOW, MINUS), (KNEE, PLUS), (KNEE, MINUS),
                 (SHOULDER, PLUS), (HIP, MINUS)]
        for joint, sense in order:
            for s in (0, 1):
                contour, fibers, _ = muscles[(s, joint, sense)]
                if contour is None:
                    continue
                color = _mix(config.ANALYSIS_MUSCLE_REST, config.ANALYSIS_MUSCLE_ACTIVE, c[s, joint, sense])
                out.append((color, contour))
                light = _mix(color, (255, 255, 255), self.fiber_white)
                out.extend((light, ("ligne", line, self.fiber_w)) for line in fibers)
        return out


# ---------------------------------------------------------------------------
# Libellés « 76% »
# ---------------------------------------------------------------------------
def label_alpha(t, k):
    """Opacité (0–1) du k-ième libellé à l'instant t du replay : ils apparaissent un par un."""
    start, step, fade = config.ANALYSIS_LABEL_TIMES
    return min(max((t - (start + k * step)) / fade, 0.0), 1.0)


def percent(frac):
    return f"{int(round(100 * frac))}%"


class Labels:
    """Textes pré-rendus ; colonnes fixes autour du point où la caméra garde le torse."""

    def __init__(self, anatomy, right_side, center_px):
        import pygame
        from evo import fonts

        self.font = fonts.load(*config.ANALYSIS_LABEL_FONT)
        self.center = center_px
        self.items = []   # (clé du muscle, surface, rectangle d'encre)
        for joint, sense, screen_side, dy in config.ANALYSIS_LABELS:
            side = right_side if screen_side > 0 else 1 - right_side
            surf = self.font.render(percent(anatomy.frac[side, joint, sense]), True, pygame.Color("#FFFFFF"))
            self.items.append(((side, joint, sense), screen_side, dy, surf, surf.get_bounding_rect()))

    def draw(self, surface, t, anchors_px):
        import pygame

        cx, cy = self.center
        gap_x, gap_y = config.ANALYSIS_LABEL_GAP
        white = pygame.Color("#FFFFFF")
        for k, (key, screen_side, dy, surf, ink) in enumerate(self.items):
            alpha = label_alpha(t, k)
            if alpha <= 0.0:
                continue
            mid_y = cy + dy
            if screen_side > 0:
                left = cx + config.ANALYSIS_LABEL_DX
                end = np.array([left - gap_x, mid_y + gap_y])
            else:
                left = cx - config.ANALYSIS_LABEL_DX - ink.width
                end = np.array([left + ink.width + gap_x, mid_y + gap_y])
            start = np.asarray(anchors_px[key], float)
            tip = start + (end - start) * alpha               # le trait se déroule du muscle vers le texte
            d = tip - start
            n = np.array([-d[1], d[0]]) / max(float(np.hypot(*d)), 1e-9) * config.ANALYSIS_LABEL_LINE / 2
            quad = [start + n, tip + n, tip - n, start - n]
            pygame.draw.polygon(surface, white, quad)
            pygame.draw.aalines(surface, white, True, quad)
            surf.set_alpha(int(round(255 * alpha)))
            surface.blit(surf, (round(left - ink.left), round(mid_y - ink.height / 2 - ink.top)))
            surf.set_alpha(None)


# ---------------------------------------------------------------------------
# Vue
# ---------------------------------------------------------------------------
def analysis_framing():
    from evo import scene

    s = config.ANALYSIS_SCALE
    # le centre du torse au départ (hauteur START_HEIGHT) à y = ANALYSIS_TORSO_PX ; la caméra l'y garde
    return scene.Framing(scale=s, ground_px=config.ANALYSIS_TORSO_PX + config.START_HEIGHT * s)


class AnalysisView:
    """Décor zoomé + lézard + surcouche + libellés, pour un replay ; mêmes méthodes que JungleView."""

    def __init__(self, replay, use_cache=True, log=None):
        from evo import render_lizard, scene

        self.replay = replay
        layers = scene.BACK_LAYERS + (scene.FRONT_LAYERS if config.ANALYSIS_FRONT_LAYER else ())
        self.scene = scene.Scene(analysis_framing(), layers=layers, use_cache=use_cache, log=log)
        self.framing = self.scene.framing
        self.camera = scene.Camera(self.framing)
        self.lizard = render_lizard.LizardShape(replay.skel)
        self.anatomy = Anatomy(self.lizard, replay.genome)
        p0 = replay.pos[0]
        right = 1 if p0[sk.R_SHOULDER][0] >= p0[sk.L_SHOULDER][0] else 0   # côté des points R_* à l'écran
        self.labels = Labels(self.anatomy, right, (self.framing.x_px(config.TRUNK_X), config.ANALYSIS_TORSO_PX))

    def follow(self, frame):
        self.camera.update(self.replay.ref_y[frame])

    def reset_camera(self):
        self.camera.update(self.replay.ref_y[0], snap=True)

    def draw(self, surface, frame, timings=None, speed=1.0, hud=None):
        t0 = time.perf_counter()
        self.scene.draw_back(surface, self.camera.shift)
        t1 = time.perf_counter()
        r = self.replay
        P = r.pos[frame]
        muscles = self.anatomy.muscles(P)
        extra = self.anatomy.shapes(P, r.activation[frame], muscles)
        origin, scale = self.camera.origin(), self.framing.scale
        drawn = self.lizard.render(P, origin, scale, clip=surface.get_size(), extra=extra)
        if drawn is not None:
            surface.blit(*drawn)
        t2 = time.perf_counter()
        self.scene.draw_front(surface, self.camera.shift)
        t3 = time.perf_counter()
        anchors = {k: (origin[0] + v[2][0] * scale, origin[1] - v[2][1] * scale) for k, v in muscles.items()}
        self.labels.draw(surface, r.t[frame], anchors)
        t4 = time.perf_counter()
        if timings is not None:
            timings.append(((t1 - t0) + (t3 - t2), t2 - t1, t4 - t3, self.scene.front_coverage(self.camera.shift)))


# ---------------------------------------------------------------------------
# Instants clés et export
# ---------------------------------------------------------------------------
def key_frames(replay, anatomy):
    """Frames où les muscles visés travaillent le plus, une fois leur libellé affiché :
    épaule (deltoïde + grand dorsal), hanche (fléchisseurs + fessiers), genou (ischios + quadriceps)."""
    start, step, fade = config.ANALYSIS_LABEL_TIMES
    shown = {(j, s): start + k * step + fade for k, (j, s, _, _) in enumerate(config.ANALYSIS_LABELS)}
    c = np.array([anatomy.contraction(a) for a in replay.activation])     # (F, côté, articulation, sens)
    out = {}
    for name, joint, t_lo, t_hi in (("epaule", SHOULDER, shown[(SHOULDER, MINUS)], shown[(HIP, PLUS)] - fade),
                                    ("hanche", HIP, shown[(HIP, MINUS)], shown[(KNEE, PLUS)] - fade),
                                    ("genou", KNEE, shown[(KNEE, MINUS)], replay.t[-1])):
        score = c[:, :, joint, PLUS].max(axis=1) + c[:, :, joint, MINUS].max(axis=1)
        window = (replay.t >= t_lo) & (replay.t <= t_hi)
        f = int(np.flatnonzero(window)[np.argmax(score[window])])
        out[name] = (f, float(score[f]))
    return out


REFERENCE_PERCENT = {(SHOULDER, PLUS): 22, (SHOULDER, MINUS): 76, (ELBOW, PLUS): 57, (HIP, PLUS): 31}   # §9


def export(replay, out_dir, use_cache=True, log=print):
    """PNG aux instants clés et à t = 10 s, planche, comparaisons avec les images 11 et 12, temps (JSON)."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    from evo.replay import _caption, frame_stats, reference_image

    pygame.display.init()
    pygame.font.init()
    os.makedirs(out_dir, exist_ok=True)
    w, h = config.WINDOW_SIZE
    screen = pygame.display.set_mode((w, h))
    view = AnalysisView(replay, use_cache=use_cache, log=log)
    view.reset_camera()
    tag = f"s{replay.seed}_g{replay.gen}_r{replay.rank}"
    keys = key_frames(replay, view.anatomy)
    wanted = {f: name for name, (f, _) in keys.items()}
    wanted[replay.n_frames - 1] = "t10"
    shots, timings, paths = {}, [], []
    for f in range(replay.n_frames):
        view.follow(f)
        view.draw(screen, f, timings)
        if f in wanted:
            name = wanted[f]
            path = os.path.join(out_dir, f"analyse_{tag}_{name}_t{replay.t[f]:05.2f}.png")
            pygame.image.save(screen, path)
            paths.append(path)
            shots[name] = (screen.copy(), f)
    small = pygame.font.SysFont(config.FONT_SANS, 18)
    captions = {"epaule": "deltoïde / grand dorsal", "hanche": "fléchisseurs / fessiers", "genou": "ischios / quadriceps",
                "t10": "fin, tous les libellés"}
    sheet = pygame.Surface((w, h))
    for k, name in enumerate(("epaule", "hanche", "genou", "t10")):
        img, f = shots[name]
        sheet.blit(pygame.transform.smoothscale(img, (w // 2, h // 2)), ((k % 2) * w // 2, (k // 2) * h // 2))
        _caption(pygame, sheet, [f"{captions[name]}, t = {replay.t[f]:.2f} s"], ((k % 2) * w // 2 + 8, (k // 2) * h // 2 + h // 2 - 40), small)
    path = os.path.join(out_dir, f"planche_analyse_{tag}.png")
    pygame.image.save(sheet, path)
    paths.append(path)
    for (m, s), name in (((16, 15), "epaule"), ((16, 35), "hanche")):
        ref = reference_image(m, s)
        img, f = shots[name]
        board = pygame.Surface((2 * w, h))
        board.blit(pygame.transform.smoothscale(pygame.image.load(ref), (w, h)), (0, 0))
        board.blit(img, (w, 0))
        _caption(pygame, board, [f"Référence : {os.path.basename(ref)}"], (8, h - 44), small)
        _caption(pygame, board, [f"Nous : {replay.label()}, t = {replay.t[f]:.2f} s ({captions[name]})"], (w + 8, h - 44), small)
        path = os.path.join(out_dir, f"comparaison_t{m}m{s:02d}.png")
        pygame.image.save(board, path)
        paths.append(path)

    arr = np.array(timings)[:, :3] * 1000.0
    st = frame_stats(arr)
    percents = {f"{cr.MUSCLE_NAMES[j][s]}": {"nous": round(100 * float(view.anatomy.frac[0, j, s]), 1),
                                            "video_s9": REFERENCE_PERCENT.get((j, s))}
                for j in range(4) for s in (PLUS, MINUS)}
    stats = {"frames": st, "key_frames": {k: {"frame": f, "t": float(replay.t[f]), "score": sc} for k, (f, sc) in keys.items()},
             "percent": percents, "decor_built": view.scene.built, "replay_ok": bool(replay.ok)}
    with open(os.path.join(out_dir, f"temps_analyse_{tag}.json"), "w") as fh:
        json.dump(stats, fh, indent=1, ensure_ascii=False)
    log(f"temps par frame (mode analyse, {st['frames']} frames ; conteneur, sans affichage) : décor {st['decor_ms_mean']:.2f} ms "
        f"(max {st['decor_ms_max']:.2f}), lézard + surcouche {st['lizard_ms_mean']:.2f} ms (max {st['lizard_ms_max']:.2f}), "
        f"libellés {st['hud_ms_mean']:.2f} ms (max {st['hud_ms_max']:.2f}), total {st['total_ms_mean']:.2f} ms "
        f"(p95 {st['total_ms_p95']:.2f}, max {st['total_ms_max']:.2f}), > 16.7 ms : {st['over_budget'] * 100:.1f} %")
    log("forces max en % de S_MAX (nous / §9) : " + ", ".join(
        f"{n} {v['nous']:.0f} %" + (f" / {v['video_s9']} %" if v["video_s9"] is not None else "") for n, v in percents.items()))
    pygame.quit()
    return paths, stats
