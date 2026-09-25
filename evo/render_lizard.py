"""Le lézard vu de dessus (§5.4), recalculé à chaque frame depuis les positions des points.

Ordre de dessin : queue, pattes (capsules), mains et pieds (doigts en éventail), torse, tête et
yeux. Deux tons séparés par l'axe de la colonne : moitié gauche claire, moitié droite foncée ;
« gauche » est le côté des points L_* ([CHOIX] côté anatomique, stable quand le lézard tourne).
Le dessin est fait dans une petite surface autour du lézard, en supersampling ×LIZARD_SUPERSAMPLE,
puis réduit : bords lissés, sans jointure entre les pièces. Le mode silhouette (une couleur, sans
doigts ni yeux) sert aux miniatures de la vue population (§7.1).
"""
import math

import numpy as np
import pygame

import config
from evo import skeleton as sk

# (os, point a, point b, proximal ?) par côté : ceinture, os proximal, os distal
_LIMBS = {
    0: ((sk.NECK, sk.L_SHOULDER, True), (sk.L_SHOULDER, sk.L_ELBOW, True), (sk.L_ELBOW, sk.L_HAND, False),
        (sk.PELVIS, sk.L_HIP, True), (sk.L_HIP, sk.L_KNEE, True), (sk.L_KNEE, sk.L_FOOT, False)),
    1: ((sk.NECK, sk.R_SHOULDER, True), (sk.R_SHOULDER, sk.R_ELBOW, True), (sk.R_ELBOW, sk.R_HAND, False),
        (sk.PELVIS, sk.R_HIP, True), (sk.R_HIP, sk.R_KNEE, True), (sk.R_KNEE, sk.R_FOOT, False)),
}
_EXTREMITIES = ((sk.L_ELBOW, sk.L_HAND, 0), (sk.R_ELBOW, sk.R_HAND, 1), (sk.L_KNEE, sk.L_FOOT, 0), (sk.R_KNEE, sk.R_FOOT, 1))


def _unit(v):
    n = math.hypot(v[0], v[1])
    return v / n if n > 1e-12 else np.array([0.0, 1.0])


def _rot90(v):
    return np.array([-v[1], v[0]])


def _catmull_rom(points, samples=8):
    """Courbe lisse passant par les points (Catmull-Rom uniforme, extrémités doublées)."""
    p = np.asarray(points, dtype=float)
    if len(p) < 3:
        return p
    ext = np.vstack([p[0], p, p[-1]])
    t = np.linspace(0.0, 1.0, samples + 1)[1:, None]
    # tous les segments d'un coup : (segments, échantillons, 2)
    p0, p1, p2, p3 = (ext[k:len(ext) - 3 + k, None, :] for k in range(4))
    seg = 0.5 * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t ** 2
                 + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3)
    return np.vstack([p[:1], seg.reshape(-1, 2)])


class LizardShape:
    """Proportions du dessin, calées sur les longueurs d'os du génome (squelette rigide)."""

    def __init__(self, skel):
        rest = {}
        for name, length in zip(skel.link_names, skel.rest):
            rest.setdefault(name, float(length))
        self.spine = rest["spine"]
        ref_spine = config.BONE_REF_LENGTHS["spine"] * config.BODY_SCALE
        self.w_limb = config.LIZARD_LIMB_WIDTH * ref_spine        # diamètre humérus / fémur (m)
        self.w_distal = config.LIZARD_DISTAL_RATIO * self.w_limb  # avant-bras / tibia
        sh, hip, waist = config.LIZARD_TORSO
        self.w_sh = sh * rest["clavicle"]
        self.w_hip = hip * rest["pelvis"]
        self.w_waist = waist * max(self.w_sh, self.w_hip)
        self.w_tail = config.LIZARD_TAIL_BASE * self.w_hip
        head_half, aspect = config.LIZARD_HEAD
        self.head_half = head_half * self.w_sh
        self.head_len = aspect * 2 * self.head_half
        angles, f_len, f_width, pad, palm = config.LIZARD_FINGERS
        self.finger_angles = [math.radians(a) for a in angles]
        self.finger_len = f_len * self.w_distal
        self.finger_width = f_width * self.w_distal
        self.pad_radius = 0.5 * pad * self.w_distal
        self.palm_radius = 0.5 * palm * self.w_distal
        self.n_points = len(skel.pos)
        tail_len = sum(length for name, length in zip(skel.link_names, skel.rest) if name == "tail")
        self.tail_extra = max(0.0, config.TAIL_VISUAL_FACTOR * self.spine - tail_len)   # prolongement dessiné (m)
        self.margin = max(self.w_hip, self.w_sh, self.finger_len + self.pad_radius, self.head_len) + self.w_limb
        # profils lissés du torse (le long de la colonne depuis PELVIS) et de la tête (depuis NECK),
        # et ellipse des yeux : ne dépendent que des proportions, calculés une fois
        L = self.spine
        self.torso_profile = _catmull_rom([(-0.14 * L, self.w_tail), (0.0, 0.82 * self.w_hip), (0.22 * L, self.w_hip),
                                           (0.55 * L, self.w_waist), (0.86 * L, self.w_sh), (L, 0.86 * self.w_sh),
                                           (1.06 * L, 0.8 * self.head_half)], samples=6)
        H, hw = self.head_len, self.head_half
        self.head_profile = _catmull_rom([(-0.08 * H, 0.8 * hw), (0.2 * H, hw), (0.55 * H, 0.97 * hw),
                                          (0.82 * H, 0.66 * hw), (0.95 * H, 0.3 * hw), (H, 0.0)], samples=6)
        e_pos, e_along, e_across, e_inset = config.LIZARD_EYE
        self.eye_u = e_pos * H
        self.eye_v = float(np.interp(self.eye_u, self.head_profile[:, 0], self.head_profile[:, 1])) * e_inset
        ang = np.linspace(0, 2 * math.pi, 18, endpoint=False)
        self.eye_along = np.array([[e_along * H * math.cos(a)] for a in ang])
        self.eye_across = np.array([[e_across * hw * math.sin(a)] for a in ang])

    # ------------------------------------------------------------------
    def polygons(self, pos, silhouette=None):
        """Liste ordonnée (couleur, polygone en m) ou (couleur, ('cercle', centre, rayon)).

        silhouette = (couleur, couleur des points, rayon des points en m) : miniature de la vue population
        (§7.1), d'une seule couleur, sans doigts ni yeux, avec un point clair par main et par pied.
        """
        P = np.asarray(pos, dtype=float)
        neck, pelvis = P[sk.NECK], P[sk.PELVIS]
        fwd = _unit(neck - pelvis)
        left = _rot90(fwd)
        if np.dot(P[sk.L_SHOULDER] - neck, left) < 0:   # côté des points L_*
            left = -left
        sigma = 1.0 if np.allclose(left, _rot90(fwd)) else -1.0
        if silhouette:
            body, dot, dot_radius = silhouette
            light = dark = body
            limb_colors = (body, body)
        else:
            light, dark = config.LIZARD_LIGHT, config.LIZARD_DARK
            limb_colors = config.LIZARD_LIMB_COLORS
        out = []

        # 1. queue : ligne médiane lissée, prolongée au-delà du dernier point (dessin seulement),
        #    effilée jusqu'à une pointe fine
        chain = _catmull_rom(self._visual_tail(np.vstack([pelvis, P[sk.TAIL_START:]])), samples=4)
        seg = np.diff(chain, axis=0)
        seg_len = np.hypot(seg[:, 0], seg[:, 1])
        u = np.concatenate([[0.0], np.cumsum(seg_len)]) / max(seg_len.sum(), 1e-9)
        tang = np.vstack([seg, seg[-1:]])
        tang[1:-1] = seg[:-1] + seg[1:]
        normals = np.array([sigma * _rot90(_unit(-t)) for t in tang])   # « gauche » du lézard, qui regarde vers la tête
        width = self.w_tail * np.clip(1 - u, 0.0, 1.0) ** config.LIZARD_TAIL_TAPER + 0.02
        edge_l = chain + normals * width[:, None]
        edge_r = chain - normals * width[:, None]
        for edge in (edge_l, edge_r, chain):   # la queue dessinée ne passe pas sous le sol
            np.maximum(edge[:, 1], config.GROUND_Y, out=edge[:, 1])
        out.append((light, np.vstack([edge_l, chain[::-1]])))
        out.append((dark, np.vstack([edge_r, chain[::-1]])))

        # 2. pattes : capsules (ceinture et os proximal épais, os distal à 70 %)
        for side, color in ((0, limb_colors[0]), (1, limb_colors[1])):
            for a, b, proximal in _LIMBS[side]:
                out.extend(self._capsule(P[a], P[b], self.w_limb if proximal else self.w_distal, color))

        # 3. mains et pieds : paume, 5 rayons clairs en éventail, disque au bout de chaque doigt
        #    (silhouette : un seul point clair, dessiné en dernier pour rester visible sur le torse)
        dots = []
        for elbow, hand, side in _EXTREMITIES:
            if silhouette:
                dots.append((dot, ("cercle", P[hand], max(self.palm_radius, dot_radius))))
                continue
            axis = _unit(P[hand] - P[elbow])
            out.append((limb_colors[side], ("cercle", P[hand], self.palm_radius)))
            tips = []
            for ang in self.finger_angles:
                c, s = math.cos(ang), math.sin(ang)
                d = np.array([axis[0] * c - axis[1] * s, axis[0] * s + axis[1] * c])
                tip = P[hand] + d * self.finger_len
                n = _rot90(d) * self.finger_width / 2
                out.append((config.LIZARD_FINGER, np.array([P[hand] + n, tip + n, tip - n, P[hand] - n])))
                tips.append(tip)
            for tip in tips:
                out.append((config.LIZARD_PAD, ("cercle", tip, self.pad_radius)))

        # 4. torse ovoïde de NECK à PELVIS, partagé sur l'axe de la colonne
        prof = self.torso_profile
        axis_pts = np.array([pelvis + fwd * uu for uu in (prof[-1, 0], prof[0, 0])])
        for sign, color in ((1.0, light), (-1.0, dark)):
            half = pelvis + fwd * prof[:, :1] + (sign * left) * prof[:, 1:]
            out.append((color, np.vstack([half, axis_pts])))

        # 5. tête : ogive dans la direction NECK → HEAD, deux tons, deux yeux noirs
        hax = _unit(P[sk.HEAD] - neck)
        hleft = sigma * _rot90(hax)
        hprof = self.head_profile
        haxis = np.array([neck + hax * hprof[-1, 0], neck + hax * hprof[0, 0]])
        for sign, color in ((1.0, light), (-1.0, dark)):
            half = neck + hax * hprof[:, :1] + (sign * hleft) * hprof[:, 1:]
            out.append((color, np.vstack([half, haxis])))
        if silhouette:
            return out + dots
        for sign in (1.0, -1.0):
            center = neck + hax * self.eye_u + sign * hleft * self.eye_v
            out.append((config.LIZARD_EYE_COLOR, center + hax * self.eye_along + hleft * self.eye_across))
        return out

    def _visual_tail(self, tail):
        """Prolonge la chaîne de la queue de `tail_extra` m : même longueur de segment, courbure
        moyenne des derniers segments amortie de TAIL_VISUAL_DAMPING à chaque segment, jamais sous le sol."""
        if self.tail_extra <= 0 or len(tail) < 3:
            return tail
        seg = np.diff(tail, axis=0)
        ang = np.arctan2(seg[:, 1], seg[:, 0])
        turns = (np.diff(ang) + np.pi) % (2 * np.pi) - np.pi
        turn = float(np.mean(turns[-3:])) if len(turns) else 0.0
        step = float(np.hypot(*seg[-1])) or 1e-3
        heading = float(ang[-1])
        total = float(np.hypot(seg[:, 0], seg[:, 1]).sum()) + self.tail_extra
        pts, left, p = [], self.tail_extra, tail[-1].copy()
        while left > 1e-6:
            turn *= config.TAIL_VISUAL_DAMPING
            heading += turn
            d = min(step, left)
            p = p + d * np.array([math.cos(heading), math.sin(heading)])
            left -= d
            # la queue dessinée ne traverse pas le sol (bord compris) : elle s'y couche
            floor = config.GROUND_Y + self.w_tail * (left / total) ** config.LIZARD_TAIL_TAPER + 0.02
            p[1] = max(p[1], floor)
            pts.append(p.copy())
        return np.vstack([tail, pts])

    @staticmethod
    def _capsule(a, b, width, color):
        d = _unit(b - a)
        n = _rot90(d) * width / 2
        return [(color, np.array([a + n, b + n, b - n, a - n])),
                (color, ("cercle", a, width / 2)), (color, ("cercle", b, width / 2))]

    # ------------------------------------------------------------------
    def draw(self, surface, pos, origin, scale):
        """Dessine le lézard sur `surface`. Écran : x_px = ox + x·scale, y_px = oy − y·scale (origin = (ox, oy))."""
        drawn = self.render(pos, origin, scale, clip=surface.get_size())
        if drawn is not None:
            surface.blit(*drawn)

    def render(self, pos, origin, scale, clip=None, silhouette=None):
        """(toile SRCALPHA, coin haut gauche en px) du lézard, ou None s'il sort de `clip` = (w, h).

        Sans `clip`, la toile peut commencer à des coordonnées négatives (miniatures : origine au point
        de référence). `silhouette` : voir `polygons`.
        """
        P = np.asarray(pos, dtype=float)
        ox, oy = origin
        pts_x, pts_y = ox + P[:, 0] * scale, oy - P[:, 1] * scale
        m = self.margin * scale + 4
        x0, y0 = int(math.floor(pts_x.min() - m)), int(math.floor(pts_y.min() - m))
        x1, y1 = int(math.ceil(pts_x.max() + m)), int(math.ceil(pts_y.max() + m))
        if clip is not None:
            x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, clip[0]), min(y1, clip[1])
        if x1 <= x0 or y1 <= y0:
            return None
        ss = config.LIZARD_SUPERSAMPLE
        canvas = pygame.Surface(((x1 - x0) * ss, (y1 - y0) * ss), pygame.SRCALPHA)
        base = pygame.Color(silhouette[0] if silhouette else config.LIZARD_DARK)
        canvas.fill((base.r, base.g, base.b, 0))
        k = scale * ss
        cx, cy = (ox - x0) * ss, (oy - y0) * ss   # origine du monde dans la toile supersamplée
        colors = {}
        for color, shape in self.polygons(P, silhouette):
            rgb = colors.get(color) or colors.setdefault(color, pygame.Color(color))
            if isinstance(shape, tuple):
                _, center, radius = shape
                if np.all(np.isfinite(center)):
                    pygame.draw.circle(canvas, rgb, (cx + center[0] * k, cy - center[1] * k), max(1.0, radius * k))
            elif np.all(np.isfinite(shape)):   # un sommet non fini figerait pygame.draw.polygon
                pts = np.empty_like(shape)
                pts[:, 0] = cx + shape[:, 0] * k
                pts[:, 1] = cy - shape[:, 1] * k
                pygame.draw.polygon(canvas, rgb, pts.tolist())
        if ss > 1:
            canvas = pygame.transform.smoothscale(canvas, (x1 - x0, y1 - y0))
        return canvas, (x0, y0)
