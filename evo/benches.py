"""Les 8 bancs d'essai du moteur physique (§10, phase 1).

Chaque banc est indépendant de pygame : `reset()`, `substep(h)` et `metrics()` ne
font que de la physique (les tests les utilisent tels quels) ; `draw(painter)`
reçoit un `render_schema.Painter`.
"""
import math

import numpy as np

import config
from evo import creature as cr
from evo import physics
from evo import skeleton as sk

H = config.DT / config.SUBSTEPS  # sous-pas physique


def _gravity_arrows(seed=3, n=10):
    rng = np.random.default_rng(seed)
    w, h = config.WINDOW_SIZE
    return list(zip(rng.uniform(60, w - 60, n), rng.uniform(0, h, n)))


class Bench:
    number = 0
    title = ""
    subtitle = ""
    help = ""
    snapshot_times = (0.0, 0.5, 1.0, 2.0)
    export_keys = ()  # touches « pressées » avant l'export (variante montrée)

    def __init__(self):
        self.show_velocity = True
        self.reset()

    def reset(self):
        raise NotImplementedError

    def substep(self, h):
        raise NotImplementedError

    def on_key(self, key):
        """Touche propre au banc (caractère). Renvoie True si elle a été utilisée."""
        return False

    def metrics(self):
        return []

    def draw(self, painter):
        raise NotImplementedError


# ---------------------------------------------------------------------------
# 1. Movement()
# ---------------------------------------------------------------------------
class MovementBench(Bench):
    number = 1
    title = "Movement();"
    subtitle = "Sans force, la vitesse est constante : le point va en ligne droite."
    P0 = (-5.0, -0.6)
    V0 = (2.0, 0.5)

    def reset(self):
        self.world = physics.World([self.P0], mass=[1.0], vel=[self.V0])
        self.world.g = 0.0
        self.clock = 0.0
        self.trail = [tuple(self.P0)]
        self.max_err = 0.0

    def substep(self, h):
        physics.substep(self.world, h)
        self.clock += h
        exact = np.add(self.P0, np.multiply(self.V0, self.world.t))
        self.max_err = max(self.max_err, float(np.linalg.norm(self.world.pos[0] - exact)))
        if int(self.clock / 0.1) >= len(self.trail):
            self.trail.append(tuple(self.world.pos[0]))
        if self.world.pos[0, 0] > 6.8:
            self.reset()

    def metrics(self):
        p, v = self.world.pos[0], self.world.vel[0]
        return [f"position   ({p[0]:+.3f}, {p[1]:+.3f}) m",
                f"vitesse    ({v[0]:+.3f}, {v[1]:+.3f}) m/s   (constante)",
                f"écart à p0 + v·t : {self.max_err:.1e} m"]

    def draw(self, painter):
        painter.set_camera((640, 400), 100)
        for q in self.trail:
            painter.point(q, radius=4, hex_code=config.SCHEMA_TRAIL)
        p = self.world.pos[0]
        painter.point(p, radius=20)
        if self.show_velocity:
            painter.arrow(p, self.world.vel[0], 50)


# ---------------------------------------------------------------------------
# 2. Gravity()
# ---------------------------------------------------------------------------
class GravityBench(Bench):
    number = 2
    title = "Gravity();"
    subtitle = "g·dt ajouté à la vitesse verticale à chaque pas : trajectoire parabolique."
    snapshot_times = (0.3, 0.6, 0.9, 1.2)
    P0 = (-2.5, -1.5)
    V0 = (3.0, 6.0)
    ARROWS = _gravity_arrows()

    def reset(self):
        self.world = physics.World([self.P0], mass=[1.0], vel=[self.V0])
        self.clock = 0.0
        self.trail = [tuple(self.P0)]
        self.max_err = 0.0

    def analytic(self, t):
        g = self.world.g
        return np.array([self.P0[0] + self.V0[0] * t,
                         self.P0[1] + self.V0[1] * t - 0.5 * g * t * t])

    def substep(self, h):
        physics.substep(self.world, h)
        self.clock += h
        self.max_err = max(self.max_err, float(np.linalg.norm(self.world.pos[0] - self.analytic(self.world.t))))
        if int(self.clock / 0.05) >= len(self.trail):
            self.trail.append(tuple(self.world.pos[0]))
        if self.world.pos[0, 1] < -2.8:
            self.reset()

    def metrics(self):
        t = self.world.t
        return [f"vitesse verticale  {self.world.vel[0, 1]:+.3f} m/s",
                f"écart à la parabole exacte : {self.max_err * 1000:.2f} mm",
                f"attendu pour Euler semi-implicite (½·g·h·t) : {0.5 * self.world.g * H * t * 1000:.2f} mm"]

    def draw(self, painter):
        painter.gravity_field(self.ARROWS, self.clock)
        painter.set_camera((640, 330), 150)
        ts = np.linspace(0.0, 1.45, 60)
        pts = [painter.to_px(self.analytic(t)) for t in ts]
        for a, b in zip(pts[::2], pts[1::2]):
            painter.line_px(a, b, config.SCHEMA_TEXT_DIM, 2)
        for q in self.trail:
            painter.point(q, radius=4, hex_code=config.SCHEMA_TRAIL)
        p = self.world.pos[0]
        painter.point(p, radius=20)
        if self.show_velocity:
            painter.arrow(p, self.world.vel[0], 22)


# ---------------------------------------------------------------------------
# 3. Hold()
# ---------------------------------------------------------------------------
class HoldBench(Bench):
    number = 3
    title = "Hold();"
    subtitle = "Un point fixé garde une vitesse nulle, malgré la gravité."
    help = "H fixer / lâcher"
    ARROWS = _gravity_arrows(seed=5)

    def reset(self):
        self.world = physics.World([(0.0, 0.0)], mass=[1.0], held=[True])
        self.clock = 0.0
        self.hold_pos = self.world.pos[0].copy()
        self.max_drift = 0.0

    def substep(self, h):
        physics.substep(self.world, h)
        self.clock += h
        if self.world.held[0]:
            self.max_drift = max(self.max_drift, float(np.linalg.norm(self.world.pos[0] - self.hold_pos)))
        if self.world.pos[0, 1] < -2.6:
            self.reset()

    def on_key(self, key):
        if key == "h":
            self.world.held[0] = not self.world.held[0]
            if self.world.held[0]:  # on fixe là où le point se trouve
                self.hold_pos = self.world.pos[0].copy()
            return True
        return False

    def metrics(self):
        return [f"fixé : {'oui' if self.world.held[0] else 'non'}",
                f"vitesse  {np.linalg.norm(self.world.vel[0]):.3f} m/s",
                f"déplacement pendant la fixation : {self.max_drift:.1e} m"]

    def draw(self, painter):
        painter.gravity_field(self.ARROWS, self.clock)
        painter.set_camera((640, 330), 150)
        p = self.world.pos[0]
        painter.point(p, radius=20, held=bool(self.world.held[0]))
        if self.show_velocity and not self.world.held[0]:
            painter.arrow(p, self.world.vel[0], 22)


# ---------------------------------------------------------------------------
# 4. Link()
# ---------------------------------------------------------------------------
class LinkBench(Bench):
    number = 4
    title = "Link();"
    subtitle = "Deux points liés lancés en tournant : la longueur reste constante."
    help = "M comparer avec un ressort"
    snapshot_times = (0.2, 0.5, 0.8, 1.1)
    export_keys = ("m",)
    L0 = 1.0
    SPIN = 2 * math.pi   # rad/s
    V_CM = (0.0, 6.0)
    START_Y = -2.2

    def __init__(self):
        self.compare = False
        super().__init__()

    def _pair(self, x0, mode):
        half = self.L0 / 2
        pos = [(x0 - half, self.START_Y), (x0 + half, self.START_Y)]
        vel = [(self.V_CM[0], self.V_CM[1] - self.SPIN * half),
               (self.V_CM[0], self.V_CM[1] + self.SPIN * half)]
        world = physics.World(pos, [(0, 1)], vel=vel)
        world.link_mode = mode
        return world

    def reset(self):
        if self.compare:
            self.pairs = [("Link() : lien rigide", self._pair(-2.3, "rigid")),
                          ("Ressort (méthode naïve)", self._pair(2.3, "spring"))]
        else:
            self.pairs = [("Link() : lien rigide", self._pair(0.0, "rigid"))]
        self.max_err = [0.0] * len(self.pairs)
        self.clock = 0.0

    def substep(self, h):
        for k, (_, world) in enumerate(self.pairs):
            physics.substep(world, h)
            self.max_err[k] = max(self.max_err[k], world.length_error())
        self.clock += h
        if all(np.mean(w.pos[:, 1]) < -3.0 for _, w in self.pairs):
            self.reset()

    def on_key(self, key):
        if key == "m":
            self.compare = not self.compare
            self.reset()
            return True
        return False

    def metrics(self):
        lines = []
        for (name, world), err in zip(self.pairs, self.max_err):
            lines.append(f"{name:<24} longueur {world.link_lengths()[0] / self.L0:.3f}·L0"
                         f"   erreur max {err * 100:.3f} %")
        return lines

    def draw(self, painter):
        painter.set_camera((640, 300), 140)
        for name, world in self.pairs:
            a, b = world.pos
            rigid = world.link_mode == "rigid"
            painter.bone(a, b, 12, config.SCHEMA_BONE if rigid else config.SCHEMA_SPRING)
            for p in world.pos:
                painter.point(p, radius=16)
            if self.show_velocity:
                for p, v in zip(world.pos, world.vel):
                    painter.arrow(p, v, 12, width=6)
            x_label = painter.to_px((world.pos[:, 0].mean(), 0))[0]
            if len(self.pairs) > 1:
                x_label = painter.to_px((-2.3 if rigid else 2.3, 0))[0]
            painter.text(name, (x_label, 120), "label", anchor="midtop")
            painter.text(f"longueur = {world.link_lengths()[0] / self.L0:.3f} × L0",
                         (x_label, 150), "mono", config.SCHEMA_TEXT_DIM, anchor="midtop")


# ---------------------------------------------------------------------------
# 5. Itérations du solveur
# ---------------------------------------------------------------------------
class IterationBench(Bench):
    number = 5
    title = "Link(); × k"
    subtitle = "Dès 3 points, on répète la passe sur tous les liens : l'erreur converge."
    help = "+/− nombre de points"
    PASSES = (0, 1, 2, 5, 20)
    CHAIN_PASSES = (1, 2, 5, 20, None)  # None = moteur complet (N_ITER + stabilisation)
    CHAIN_LOOP = 5.0
    snapshot_times = (0.0, 0.8, 2.0, 4.0)

    def __init__(self):
        self.n_points = 5
        super().__init__()

    # Haut : configuration figée de l'image 22 (tous vers le haut, le point de gauche de travers).
    def frozen_world(self):
        n = self.n_points
        pos = np.stack([np.linspace(-1.0, 1.0, n), np.zeros(n)], axis=1)
        vel = np.tile([0.0, 1.0], (n, 1))
        vel[0] = (-0.45, 1.1)
        return physics.World(pos, [(i, i + 1) for i in range(n - 1)], vel=vel)

    def solve_frozen(self, passes):
        world = self.frozen_world()
        world.n_iter = passes
        world.beta = 0.0
        physics.link(world, H)
        return world

    # Bas : chaînes pendues à un point fixe, lâchées à l'horizontale.
    def make_chain(self, passes):
        n = self.n_points
        world = physics.World(np.stack([np.linspace(0.0, 1.0, n), np.zeros(n)], axis=1),
                              [(i, i + 1) for i in range(n - 1)])
        world.held[0] = True
        if passes is not None:  # vitesses seules : ni Baumgarte ni projection
            world.n_iter, world.beta, world.n_pos_iter = passes, 0.0, 0
        return world

    def reset(self):
        self.frozen = [self.solve_frozen(k) for k in self.PASSES]
        self.chains = [self.make_chain(k) for k in self.CHAIN_PASSES]
        self.chain_max_err = [0.0] * len(self.chains)
        self.clock = 0.0

    def substep(self, h):
        for k, world in enumerate(self.chains):
            physics.substep(world, h)
            self.chain_max_err[k] = max(self.chain_max_err[k], world.length_error())
        self.clock += h
        if self.clock >= self.CHAIN_LOOP:
            self.chains = [self.make_chain(k) for k in self.CHAIN_PASSES]
            self.chain_max_err = [0.0] * len(self.chains)
            self.clock = 0.0

    def on_key(self, key):
        if key in ("+", "="):
            self.n_points = min(12, self.n_points + 1)
        elif key == "-":
            self.n_points = max(3, self.n_points - 1)
        else:
            return False
        self.reset()
        return True

    @staticmethod
    def _chain_label(passes):
        return "moteur complet" if passes is None else f"{passes} passe{'s' if passes > 1 else ''}"

    def metrics(self):
        chains = " | ".join(f"{e * 100:.1f} %" for e in self.chain_max_err)
        return [f"{self.n_points} points · erreur de longueur max des chaînes : {chains}"]

    def draw(self, painter):
        n_panels = len(self.PASSES)
        width = config.WINDOW_SIZE[0] / n_panels
        painter.text("Correction des vitesses (image 22) : erreur restante après k passes",
                     (640, 112), "label", anchor="midtop")
        for i, (passes, world) in enumerate(zip(self.PASSES, self.frozen)):
            cx = width * (i + 0.5)
            painter.set_camera((cx, 290), 85)
            for a, b in world.links:
                painter.bone(world.pos[a], world.pos[b], 7)
            for p, v in zip(world.pos, world.vel):
                painter.point(p, radius=10)
                painter.arrow(p, v, 80, width=5)
            label = f"{passes} passe{'s' if passes > 1 else ''}"
            painter.text(label, (cx, 330), "label", anchor="midtop")
            painter.text(f"erreur {world.velocity_residual():.1e} m/s", (cx, 358), "mono",
                         config.SCHEMA_TEXT_DIM, anchor="midtop")

        painter.text("Chaîne pendue : vitesses seules (sans stabilisation) vs moteur complet",
                     (640, 405), "label", anchor="midtop")
        for i, (passes, world) in enumerate(zip(self.CHAIN_PASSES, self.chains)):
            x0 = width * i + 70
            painter.set_camera((x0, 500), 85)
            for a, b in world.links:
                painter.bone(world.pos[a], world.pos[b], 6)
            for p, held in zip(world.pos, world.held):
                painter.point(p, radius=12 if held else 8, held=bool(held))
            ratio = np.sum(world.link_lengths()) / np.sum(world.rest)
            cx = width * (i + 0.5)
            painter.text(self._chain_label(passes), (cx, 440), "small", anchor="midtop")
            painter.text(f"longueur ×{ratio:.3f}", (cx, 462), "mono", config.SCHEMA_TEXT_DIM, anchor="midtop")


# ---------------------------------------------------------------------------
# 6. Contract()
# ---------------------------------------------------------------------------
class ContractBench(Bench):
    number = 6
    title = "Contract();"
    subtitle = "Couple sur une articulation : pivot poussé d'un côté, extrémités de l'autre, ΣF = 0."
    snapshot_times = (0.3, 0.9, 1.8, 2.4)
    TAU0 = 0.3  # N·m, couple max
    HALF_ANGLE = math.radians(30)
    # Un couple fixe qui alterne dérive d'un cycle à l'autre (l'inertie change avec
    # l'angle, rien ne rappelle le système). On alterne donc une consigne d'angle, suivie
    # par un couple plafonné (τ = clamp(Kp·e − Kd·ω), ce que fera le contrôleur de la phase 2).
    TARGETS_DEG = (35.0, 60.0)
    TARGET_PERIOD = 1.5
    KP, KD = 3.0, 1.2

    def reset(self):
        pivot = np.array([0.0, 0.6])
        down_left = np.array([-math.sin(self.HALF_ANGLE), -math.cos(self.HALF_ANGLE)])
        down_right = np.array([math.sin(self.HALF_ANGLE), -math.cos(self.HALF_ANGLE)])
        pos = [pivot + down_left, pivot, pivot + down_right]  # A, P, B
        self.world = physics.World(pos, [(0, 1), (1, 2)], joints=[(0, 1, 2)])
        self.world.g = 0.0
        self.clock = 0.0
        self.max_sum_force = 0.0
        self.max_sum_moment = 0.0
        self.max_momentum = 0.0
        self.angle0 = float(self.world.joint_angles()[0])

    def target(self, t):
        return math.radians(self.TARGETS_DEG[int(t / self.TARGET_PERIOD) % 2])

    def substep(self, h):
        w = self.world
        error = self.target(w.t) - w.joint_angles()[0]
        w.torque[0] = np.clip(self.KP * error - self.KD * w.joint_velocities()[0], -self.TAU0, self.TAU0)
        forces = physics.contraction_forces(w.pos, w.joints, w.torque)
        moment = np.sum(w.pos[:, 0] * forces[:, 1] - w.pos[:, 1] * forces[:, 0])
        self.max_sum_force = max(self.max_sum_force, float(np.linalg.norm(forces.sum(axis=0))))
        self.max_sum_moment = max(self.max_sum_moment, abs(float(moment)))
        physics.substep(w, h)
        self.max_momentum = max(self.max_momentum, float(np.linalg.norm(w.momentum())))
        self.clock += h

    def metrics(self):
        w = self.world
        mode = "fermeture" if w.torque[0] < 0 else "ouverture"
        return [f"consigne {math.degrees(self.target(w.t)):.0f}°   angle {math.degrees(w.joint_angles()[0]):.1f}°"
                f"   couple {w.torque[0]:+.2f} N·m ({mode})",
                f"max |ΣF| = {self.max_sum_force:.1e} N   max |ΣM| = {self.max_sum_moment:.1e} N·m",
                f"quantité de mouvement max |p| = {self.max_momentum:.1e}   erreur de longueur {w.length_error() * 100:.3f} %"]

    def draw(self, painter):
        painter.set_camera((640, 400), 250)
        w = self.world
        for a, b in w.links:
            painter.bone(w.pos[a], w.pos[b], 14)
        for p in w.pos:
            painter.point(p, radius=20)
        forces = w.contract_forces
        for p, f in zip(w.pos, forces):
            painter.arrow(p, f, 400, width=9)


# ---------------------------------------------------------------------------
# 7. Masses
# ---------------------------------------------------------------------------
class MassBench(Bench):
    number = 7
    title = "Masses"
    subtitle = "Masse d'un point = somme des demi-longueurs des os qui y sont attachés."
    snapshot_times = (0.0,)
    POINTS = [(0.0, 0.0), (3.0, 0.0), (0.0, -1.0), (3.0, -2.0)]  # image 20
    BONES = [(0, 1), (0, 2), (1, 3)]
    EXPECTED = (2.0, 2.5, 0.5, 1.0)

    def reset(self):
        self.world = physics.World(self.POINTS, self.BONES)
        self.clock = 0.0

    def substep(self, h):
        self.clock += h

    def metrics(self):
        got = " / ".join(f"{m:.1f}" for m in self.world.mass)
        want = " / ".join(f"{m:.1f}" for m in self.EXPECTED)
        return [f"masses calculées : {got}", f"image 20         : {want}"]

    def draw(self, painter):
        painter.set_camera((360, 216), 187)
        w = self.world
        centroid = w.pos.mean(axis=0)
        colors = config.MASS_SCHEMA_COLORS
        for (a, b), rest in zip(w.links, w.rest):
            pa, pb = w.pos[a], w.pos[b]
            mid = (pa + pb) / 2
            painter.line_px(painter.to_px(pa), painter.to_px(mid), colors[a][1], 16)
            painter.line_px(painter.to_px(mid), painter.to_px(pb), colors[b][1], 16)
            # étiquettes des demi-longueurs, du côté opposé au reste du schéma
            normal = np.array([-(pb - pa)[1], (pb - pa)[0]]) / rest
            if np.dot(normal, mid - centroid) < 0:
                normal = -normal
            for q in (pa + (pb - pa) * 0.25, pa + (pb - pa) * 0.75):
                c = painter.to_px(q)
                painter.text(f"{rest / 2:.1f}", (c[0] + normal[0] * 70, c[1] - normal[1] * 70),
                             "half", anchor="center")
        for k, (p, m) in enumerate(zip(w.pos, w.mass)):
            radius = int(37 * math.sqrt(m))
            painter.point(p, radius=radius, hex_code=colors[k][0])
            painter.text(f"{m:.1f}", painter.to_px(p), "mass" if m >= 1.0 else "mass_small", anchor="center")


# ---------------------------------------------------------------------------
# 8. Pendule humain
# ---------------------------------------------------------------------------
class PendulumBench(Bench):
    number = 8
    title = "Pendule humain"
    subtitle = "Squelette complet (tête et queue comprises) pendu par une patte pendant 10 s."
    help = "H changer de patte · B liens de rigidité"
    DURATION = 10.0
    snapshot_times = (0.0, 0.5, 2.0, 10.0)

    def __init__(self):
        self.anchor = sk.L_HAND
        self.show_braces = True
        super().__init__()
        self.show_velocity = False

    def reset(self):
        self.skel = sk.build_skeleton()
        self.world = self.skel.make_world(origin=-self.skel.pos[self.anchor])
        self.world.held[self.anchor] = True
        names = self.skel.link_names
        self.tail_mask = np.array([n == "tail" for n in names])
        self.brace_mask = np.array([n == "brace" for n in names])
        self.body_mask = ~self.tail_mask
        self.e0 = self.world.kinetic_energy() + self.world.potential_energy()
        self.max_body = self.max_tail = 0.0
        self.max_energy_gain = 0.0
        self.finite = True
        self.clock = 0.0

    def energy(self):
        return self.world.kinetic_energy() + self.world.potential_energy() - self.e0

    def substep(self, h):
        physics.substep(self.world, h)
        self.clock += h
        if self.clock <= self.DURATION + 1e-9:
            err = np.abs(self.world.link_lengths() - self.world.rest) / self.world.rest
            self.max_body = max(self.max_body, float(err[self.body_mask].max()))
            self.max_tail = max(self.max_tail, float(err[self.tail_mask].max()))
            self.max_energy_gain = max(self.max_energy_gain, self.energy())
            self.finite = self.finite and bool(np.isfinite(self.world.pos).all())

    def on_key(self, key):
        if key == "h":
            ends = sk.LIMB_ENDS
            self.anchor = ends[(ends.index(self.anchor) + 1) % len(ends)]
            self.reset()
            return True
        if key == "b":
            self.show_braces = not self.show_braces
            return True
        return False

    def metrics(self):
        done = self.clock >= self.DURATION - 1e-9
        status = ("✓ 10 s écoulées" if done else f"{self.clock:.1f} / 10 s")
        ok = self.max_body < 0.01 and self.max_tail < 0.01 and self.finite
        verdict = ("critère < 1 % respecté" if ok else "critère < 1 % NON respecté") if done else ""
        return [f"pendu par {self.skel.names[self.anchor]}   {status}   {verdict}",
                f"erreur de longueur max : os du corps {self.max_body * 100:.3f} %   queue {self.max_tail * 100:.3f} %",
                f"énergie E − E0 = {self.energy():+.3f} J (gain max {self.max_energy_gain:+.4f} J)"
                f"   {'aucun NaN' if self.finite else 'NaN !'}"]

    def draw(self, painter):
        hanging_by_hand = self.anchor in (sk.L_HAND, sk.R_HAND)
        painter.set_camera((640, 130 if hanging_by_hand else 330), 300)
        w = self.world
        for (a, b), name in zip(w.links, self.skel.link_names):
            if name == "brace":
                if self.show_braces:
                    painter.dashed_px(painter.to_px(w.pos[a]), painter.to_px(w.pos[b]), config.SCHEMA_BRACE, 2)
            else:
                painter.bone(w.pos[a], w.pos[b], 5 if name == "tail" else 9)
        for k, p in enumerate(w.pos):
            if w.held[k]:
                continue
            radius = 10 if k in (sk.NECK, sk.PELVIS) else (4 if k >= sk.TAIL_START else 7)
            painter.point(p, radius=radius)
        painter.point(w.pos[self.anchor], radius=12, held=True)
        if self.show_velocity:
            for p, v in zip(w.pos[:sk.HEAD], w.vel[:sk.HEAD]):
                painter.arrow(p, v, 15, width=4)


# ---------------------------------------------------------------------------
# 9. Sol
# ---------------------------------------------------------------------------
class GroundBench(Bench):
    number = 9
    title = "Sol"
    subtitle = "Collision sans rebond + frottement de Coulomb ; créature inerte lâchée à 8 m."
    snapshot_times = (0.0, 1.3, 3.0, 6.0)
    V0 = 5.0                 # m/s, vitesse de glissement initiale
    FRICTIONS = (0.5, 1.0, 2.0)

    def reset(self):
        self.creature = cr.Creature(cr.limp_genome())
        self.sliders = []
        for mu in self.FRICTIONS:
            world = physics.World([(0.0, config.GROUND_Y)], mass=[1.0], vel=[(self.V0, 0.0)])
            world.ground_y = config.GROUND_Y
            world.ground_friction = mu
            self.sliders.append(world)
        names = self.creature.skel.link_names
        self.tail_mask = np.array([n == "tail" for n in names])
        self.min_y = float(self.creature.world.pos[:, 1].min())
        self.max_body = self.max_tail = 0.0
        self.clock = 0.0

    def stop_distance(self, mu):
        return self.V0 ** 2 / (2 * mu * config.G)

    def substep(self, h):
        self.creature.substep(h)
        for world in self.sliders:
            physics.substep(world, h)
        w = self.creature.world
        self.min_y = min(self.min_y, float(w.pos[:, 1].min()))
        err = np.abs(w.link_lengths() - w.rest) / w.rest
        self.max_body = max(self.max_body, float(err[~self.tail_mask].max()))
        self.max_tail = max(self.max_tail, float(err[self.tail_mask].max()))
        self.clock += h

    def metrics(self):
        c = self.creature
        slides = "  ".join(f"μ={w.ground_friction:g} : {w.pos[0, 0]:.3f} m (théorie {self.stop_distance(w.ground_friction):.3f})"
                           for w in self.sliders)
        return [f"créature : hauteur {c.height():+.2f} m   au sol : {'oui' if c.fallen else 'non'}"
                f"   point le plus bas {self.min_y:+.1e} m   énergie cinétique {c.world.kinetic_energy():.2f} J",
                f"erreur de longueur max : os du corps {self.max_body * 100:.2f} %   queue {self.max_tail * 100:.2f} % (pic à l'impact)",
                f"glissade à {self.V0:g} m/s, arrêt à : {slides}"]

    def draw(self, painter):
        width, height = config.WINDOW_SIZE
        ground_px = 560
        # Gauche : la créature (échelle de la créature).
        painter.set_camera((330, ground_px), 30)
        painter.line_px((20, ground_px), (640, ground_px), config.SCHEMA_BONE, 3)
        w = self.creature.world
        start_y = painter.to_px((0, config.START_HEIGHT))[1]
        painter.dashed_px((40, start_y), (620, start_y), config.SCHEMA_TEXT_DIM, 1)
        painter.text(f"départ : {config.START_HEIGHT:g} m", (44, start_y - 22), "small", config.SCHEMA_TEXT_DIM)
        for (a, b), name in zip(w.links, self.creature.skel.link_names):
            if name != "brace":
                painter.bone(w.pos[a], w.pos[b], 3 if name == "tail" else 5)
        for k, p in enumerate(w.pos):
            painter.point(p, radius=2 if k >= sk.TAIL_START else 4)
        # Droite : points qui glissent, avec la distance d'arrêt théorique v0²/(2μg).
        painter.set_camera((720, ground_px), 190)
        painter.line_px((660, ground_px), (1260, ground_px), config.SCHEMA_BONE, 3)
        for k, world in enumerate(self.sliders):
            y = ground_px - 60 - 110 * k
            painter.set_camera((720, y), 190)
            painter.line_px((700, y), (1250, y), config.SCHEMA_BRACE, 2)
            stop = painter.to_px((self.stop_distance(world.ground_friction), 0))
            painter.line_px((stop[0], y - 22), (stop[0], y + 8), config.SCHEMA_GRAVITY, 3)
            painter.point(world.pos[0], radius=12)
            if self.show_velocity:
                painter.arrow(world.pos[0], world.vel[0], 18, width=6)
            painter.text(f"μ = {world.ground_friction:g}", (700, y - 44), "small", config.SCHEMA_TEXT_DIM)


BENCHES = [MovementBench, GravityBench, HoldBench, LinkBench,
           IterationBench, ContractBench, MassBench, PendulumBench, GroundBench]
