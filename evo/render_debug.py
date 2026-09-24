"""Vue debug de la créature (§7.6, images 15–17) : fond bleu nuit, grille, « écorché ».

Os et articulations crème, muscles rose-rouge : épaisseur ∝ force max évoluée,
couleur ∝ contraction instantanée (§5.5). La queue est une chaîne de points.
"""
import math

import numpy as np
import pygame

import config
from evo import creature as cr
from evo import skeleton as sk
from evo.render_schema import Painter, color

MUSCLE_ALPHA = 217  # ≈ 85 % d'opacité (§5.2)


def _lerp_color(a, b, t):
    ca, cb = color(a), color(b)
    t = max(0.0, min(1.0, t))
    return pygame.Color(*(int(round(ca[k] + (cb[k] - ca[k]) * t)) for k in range(3)))


def _unit(v):
    n = math.hypot(v[0], v[1])
    return (v[0] / n, v[1] / n) if n > 1e-12 else (0.0, 0.0)


class DebugView:
    def __init__(self, surface, fonts):
        self.surface = surface
        self.fonts = fonts
        self.painter = Painter(surface, fonts)
        self.overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        self.cam_y = None

    # --- caméra -------------------------------------------------------------
    def follow(self, creature, smooth=True):
        """Suit la créature verticalement (lerp doux) ; le sol reste visible au départ."""
        half_h = self.surface.get_height() / 2 / config.DEBUG_SCALE
        target = max(float(creature.reference_point()[1]), config.GROUND_Y + half_h - 1.0)
        if self.cam_y is None or not smooth:
            self.cam_y = target
        else:
            self.cam_y += (target - self.cam_y) * 0.08
        w, h = self.surface.get_size()
        self.painter.set_camera((w / 2 - config.TRUNK_X * config.DEBUG_SCALE,
                                 h / 2 + self.cam_y * config.DEBUG_SCALE), config.DEBUG_SCALE)

    # --- décor debug --------------------------------------------------------
    def background(self, ref_y0):
        p = self.painter
        w, h = self.surface.get_size()
        self.surface.fill(color(config.DEBUG_BG))
        left = p.to_px((config.TRUNK_X - config.TRUNK_WIDTH / 2, 0))[0]
        right = p.to_px((config.TRUNK_X + config.TRUNK_WIDTH / 2, 0))[0]
        pygame.draw.rect(self.surface, color(config.DEBUG_TRUNK), (left, 0, right - left, h))
        # Grille : lignes fines tous les DEBUG_GRID_STEP m, plus marquées tous les 5 pas ; les
        # lignes horizontales partent de la hauteur de départ, pour lire la hauteur du HUD.
        step = config.DEBUG_GRID_STEP
        top = p.origin[1] / p.scale
        bottom = (p.origin[1] - h) / p.scale
        faint = _lerp_color(config.DEBUG_BG, config.DEBUG_GRID, 0.3)
        for k in range(int(math.floor((bottom - ref_y0) / step)), int(math.ceil((top - ref_y0) / step)) + 1):
            y_world = ref_y0 + k * step
            y = p.to_px((0, y_world))[1]
            major = k % 5 == 0
            pygame.draw.line(self.surface, color(config.DEBUG_GRID) if major else faint, (0, y), (w, y), 1)
            if major and y_world > config.GROUND_Y:
                p.text(f"{k * step:+.0f} m", (left - 8, y - 2), "small", config.DEBUG_TEXT_DIM, anchor="bottomright")
        x_min = -p.origin[0] / p.scale
        x_max = (w - p.origin[0]) / p.scale
        for k in range(int(math.floor(x_min / step)), int(math.ceil(x_max / step)) + 1):
            x = p.to_px((k * step, 0))[0]
            major = k % 5 == 0
            pygame.draw.line(self.surface, color(config.DEBUG_GRID) if major else faint, (x, 0), (x, h), 1)
        # Sol
        gy = p.to_px((0, config.GROUND_Y))[1]
        if gy < h:
            pygame.draw.rect(self.surface, color(config.DEBUG_GROUND), (0, gy, w, h - gy))
            pygame.draw.line(self.surface, color(config.DEBUG_BONE), (0, gy), (w, gy), 2)

    # --- créature -----------------------------------------------------------
    def creature(self, c):
        p = self.painter
        pos = c.world.pos
        self.overlay.fill((0, 0, 0, 0))
        over = Painter(self.overlay, self.fonts)
        over.set_camera(p.origin, p.scale)
        self._muscles(over, c)
        self.surface.blit(self.overlay, (0, 0))

        bone = config.DEBUG_BONE
        for (a, b), name in zip(c.world.links, c.skel.link_names):
            if name == "brace":
                continue
            p.bone(pos[a], pos[b], 2 if name == "tail" else 3, bone)
        for k in range(sk.TAIL_START, len(pos)):
            p.point(pos[k], radius=2, hex_code=bone)
        for k in range(sk.TAIL_START):
            radius = 6 if k in (sk.NECK, sk.PELVIS) else 4
            p.point(pos[k], radius=radius, hex_code=bone)
        for limb in cr.LIMBS:
            center = p.to_px(pos[limb])
            if c.world.held[limb]:
                pygame.draw.circle(self.surface, color(config.DEBUG_HELD), _ipt(center), 9, 2)
            pygame.draw.circle(self.surface, color("#B41C34"), _ipt(center), 3)

    def _muscles(self, over, c):
        pos = c.world.pos
        s_max = config.S_MAX
        length_px = config.BONE_REF_LENGTHS["humerus"] * config.BODY_SCALE * over.scale
        max_half_width = 0.22 * length_px  # fuseau le plus épais (force = S_MAX)
        for side in range(2):
            for jtype in range(4):
                j = side * 4 + jtype
                a, piv, b = cr.JOINTS[j]
                s_plus, s_minus = c.genome.strengths[side, jtype]
                u = c.activation[j]
                act_plus = u / s_plus if (u > 0 and s_plus > 0) else 0.0
                act_minus = -u / s_minus if (u < 0 and s_minus > 0) else 0.0
                col_plus = _muscle_color(act_plus)
                col_minus = _muscle_color(act_minus)
                if jtype == 0:    # épaule : deltoïde (ovale) / grand dorsal (triangle vers la colonne)
                    self._spindle(over, pos[piv], pos[b], 0.0, 0.45, max_half_width * s_plus / s_max, 0.0, col_plus)
                    self._girdle_triangle(over, pos[piv], pos[sk.NECK], pos[sk.PELVIS], s_minus / s_max, col_minus)
                elif jtype == 2:  # hanche : fléchisseurs (fuseau) / fessiers (triangle vers la colonne)
                    self._spindle(over, pos[piv], pos[b], 0.0, 0.45, max_half_width * s_plus / s_max, 0.0, col_plus)
                    self._girdle_triangle(over, pos[piv], pos[sk.PELVIS], pos[sk.NECK], s_minus / s_max, col_minus)
                else:             # coude (biceps/triceps) et genou (ischios/quadriceps) : fuseaux sur l'os proximal
                    prox_a, prox_b = pos[a], pos[piv]
                    inner = _inner_side(prox_a, prox_b, pos[b])
                    off = 0.35 * max_half_width
                    self._spindle(over, prox_a, prox_b, 0.15, 0.95, max_half_width * 0.7 * s_plus / s_max,
                                  inner * off, col_plus)
                    self._spindle(over, prox_a, prox_b, 0.15, 0.95, max_half_width * 0.7 * s_minus / s_max,
                                  -inner * off, col_minus)

    @staticmethod
    def _spindle(over, p0, p1, t0, t1, half_width, offset, rgba, n=12):
        """Fuseau entre les fractions t0 et t1 du segment p0→p1, décalé de `offset` px."""
        if half_width < 0.5:
            return
        a, b = over.to_px(p0), over.to_px(p1)
        d = _unit((b[0] - a[0], b[1] - a[1]))
        nrm = (-d[1], d[0])
        top, bottom = [], []
        for k in range(n + 1):
            t = t0 + (t1 - t0) * k / n
            wdt = half_width * math.sin(math.pi * k / n)
            cx = a[0] + (b[0] - a[0]) * t + nrm[0] * offset
            cy = a[1] + (b[1] - a[1]) * t + nrm[1] * offset
            top.append((cx + nrm[0] * wdt, cy + nrm[1] * wdt))
            bottom.append((cx - nrm[0] * wdt, cy - nrm[1] * wdt))
        pygame.draw.polygon(over.surface, rgba, [_ipt(q) for q in top + bottom[::-1]])

    @staticmethod
    def _girdle_triangle(over, joint, girdle_center, other_end, size, rgba):
        """Triangle de la ceinture vers la colonne : taille ∝ force (grand dorsal, fessiers)."""
        if size <= 0.01:
            return
        tip = girdle_center + (other_end - girdle_center) * (0.12 + 0.38 * size)
        pts = [over.to_px(joint), over.to_px(girdle_center), over.to_px(tip)]
        pygame.draw.polygon(over.surface, rgba, [_ipt(q) for q in pts])

    # --- HUD debug ----------------------------------------------------------
    def hud(self, c, title, history=None, extra=()):
        p = self.painter
        w, h = self.surface.get_size()
        p.text(title, (w / 2, 14), "label", config.DEBUG_TEXT, anchor="midtop")
        held = ", ".join(n for n, limb in zip(cr.LIMB_NAMES, cr.LIMBS) if c.world.held[limb]) or "aucune"
        lines = [f"Temps : {c.t:.1f} s",
                 f"Hauteur : {c.height():+.2f} m",
                 f"Horloge : {c.genome.period:.1f} s · pose {c.pose_index + 1}/{c.genome.n_poses}",
                 f"Énergie : {c.energy:.1f}",
                 f"Masse musculaire : {c.muscle_mass():.1f}",
                 f"Pattes tenues : {held}"]
        if c.fallen:
            lines.append("Au sol")
        lines += list(extra)
        panel = pygame.Surface((max(self.fonts["mono"].size(line)[0] for line in lines) + 20, 22 * len(lines) + 12),
                               pygame.SRCALPHA)
        panel.fill((4, 4, 20, 190))
        self.surface.blit(panel, (6, 8))
        for k, line in enumerate(lines):
            p.text(line, (16, 14 + 22 * k), "mono", config.DEBUG_TEXT)
        if history:
            self._height_graph(history)

    def _height_graph(self, history, duration=10.0):
        """Petit graphe hauteur(t) en bas à droite (courbe « distance » #9CEC6C, §5.2)."""
        w, h = self.surface.get_size()
        box = pygame.Rect(w - 330, h - 190, 310, 170)
        panel = pygame.Surface(box.size, pygame.SRCALPHA)
        panel.fill((20, 20, 36, 200))
        self.surface.blit(panel, box.topleft)
        hs = [v for _, v in history]
        lo = min(-1.0, math.floor(min(hs)))
        hi = max(1.0, math.ceil(max(hs)))
        t_max = max(duration, history[-1][0])

        def to_px(t, v):
            return (box.left + 36 + (box.width - 50) * t / t_max,
                    box.bottom - 22 - (box.height - 40) * (v - lo) / (hi - lo))

        grid = _lerp_color(config.DEBUG_BG, config.DEBUG_GRID, 0.6)
        zero = to_px(0, 0)[1]
        pygame.draw.line(self.surface, grid, (box.left + 36, zero), (box.right - 14, zero), 1)
        pts = [to_px(t, v) for t, v in history]
        if len(pts) > 1:
            pygame.draw.lines(self.surface, color("#9CEC6C"), False, [_ipt(q) for q in pts], 2)
        self.painter.text(f"{hi:+.0f} m", (box.left + 32, to_px(0, hi)[1]), "small", config.DEBUG_TEXT_DIM, anchor="midright")
        self.painter.text("0", (box.left + 32, zero), "small", config.DEBUG_TEXT_DIM, anchor="midright")
        self.painter.text(f"{lo:+.0f} m", (box.left + 32, to_px(0, lo)[1]), "small", config.DEBUG_TEXT_DIM, anchor="midright")
        self.painter.text(f"hauteur (0–{t_max:.0f} s)", (box.left + 40, box.top + 4), "small", config.DEBUG_TEXT_DIM)


def _muscle_color(activation):
    rgba = _lerp_color(config.DEBUG_MUSCLE_REST, config.DEBUG_MUSCLE_ACTIVE, activation)
    rgba.a = MUSCLE_ALPHA
    return rgba


def _inner_side(a, piv, b):
    """+1 / −1 : côté (en pixels écran) vers lequel l'os distal se replie."""
    d1 = np.asarray(piv) - np.asarray(a)
    d2 = np.asarray(b) - np.asarray(piv)
    cross = d1[0] * d2[1] - d1[1] * d2[0]
    return -1.0 if cross > 0 else 1.0  # l'axe y est inversé à l'écran


def _ipt(p):
    return (int(round(p[0])), int(round(p[1])))
