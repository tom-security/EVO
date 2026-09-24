"""La créature (§2) : squelette imposé, 16 muscles asymétriques, contrôleur à horloge + K poses.

Conventions
- 8 articulations, indice j = côté·4 + type (côté 0 = gauche, 1 = droit ;
  type 0 épaule, 1 coude, 2 hanche, 3 genou).
- φ = angle de l'articulation, compté depuis la posture de repos (φ = 0 au repos), mesuré en
  miroir à gauche et à droite, et orienté pour que le muscle « + » l'augmente :
  deltoïde (lève le bras vers la tête), biceps (flexion), fléchisseurs de hanche (lèvent
  la jambe vers la tête), ischios (flexion du genou).
- Les forces musculaires sont en unités internes (0 à S_MAX) ; le couple physique vaut
  force × torque_unit() (voir config.TORQUE_SCALE).
"""
import math
from dataclasses import dataclass, replace
from functools import lru_cache

import numpy as np

import config
from evo import physics
from evo import skeleton as sk

BONE_NAMES = ("spine", "clavicle", "humerus", "forearm", "pelvis", "femur", "tibia")
JOINT_TYPES = ("épaule", "coude", "hanche", "genou")
SIDES = ("gauche", "droit")
# (muscle « + », muscle « − ») par type d'articulation (§2.3)
MUSCLE_NAMES = (
    ("Deltoïde", "Grand dorsal"),
    ("Biceps", "Triceps"),
    ("Fléchisseurs de hanche", "Fessiers"),
    ("Ischios", "Quadriceps"),
)

# Triplets (A, pivot, B) de chaque articulation, côté gauche puis droit.
JOINTS = (
    (sk.NECK, sk.L_SHOULDER, sk.L_ELBOW), (sk.L_SHOULDER, sk.L_ELBOW, sk.L_HAND),
    (sk.PELVIS, sk.L_HIP, sk.L_KNEE), (sk.L_HIP, sk.L_KNEE, sk.L_FOOT),
    (sk.NECK, sk.R_SHOULDER, sk.R_ELBOW), (sk.R_SHOULDER, sk.R_ELBOW, sk.R_HAND),
    (sk.PELVIS, sk.R_HIP, sk.R_KNEE), (sk.R_HIP, sk.R_KNEE, sk.R_FOOT),
)
# Sens de l'angle signé A→B (physics.World.joint_angles) qui correspond au muscle « + »,
# côté gauche, dans la posture de repos du §2.2 ; le côté droit est le miroir.
# Épaule, coude, hanche : l'angle A→B diminue ; genou (plié dans l'autre sens) : il augmente.
_PLUS_SIGN_LEFT = (-1.0, -1.0, -1.0, +1.0)
JOINT_SIGNS = np.array([s * side for side in (+1.0, -1.0) for s in _PLUS_SIGN_LEFT])

# Pattes, dans l'ordre des booléens « tenir » d'une pose.
LIMBS = sk.LIMB_ENDS  # (L_HAND, R_HAND, L_FOOT, R_FOOT)
LIMB_NAMES = ("main G", "main D", "pied G", "pied D")


def wrap_angle(a):
    return (np.asarray(a) + np.pi) % (2 * np.pi) - np.pi


def reference_lengths():
    """Longueurs de référence des os (m), mises à l'échelle BODY_SCALE."""
    return np.array([config.BONE_REF_LENGTHS[n] for n in BONE_NAMES]) * config.BODY_SCALE


@lru_cache(maxsize=None)
def _torque_unit(scale, torque_scale, g):
    skel = sk.build_skeleton({n: v for n, v in zip(BONE_NAMES, reference_lengths())},
                             head_length=config.HEAD_LENGTH * scale)
    world = skel.make_world()
    return torque_scale * world.mass.sum() * g * config.BONE_REF_LENGTHS["spine"] * scale


def torque_unit():
    """Couple (N·m) d'une force musculaire de 1 : TORQUE_SCALE × poids × colonne de la créature de référence."""
    return _torque_unit(config.BODY_SCALE, config.TORQUE_SCALE, config.G)


def fitness(height, energy, muscle_mass):
    """Score de sélection (§3.2) : hauteur finale − pénalité d'énergie − pénalité de masse musculaire."""
    return height - config.FITNESS_ENERGY * energy - config.FITNESS_MUSCLE * muscle_mass


# ---------------------------------------------------------------------------
# Génome (§2.5)
# ---------------------------------------------------------------------------
@dataclass
class Genome:
    lengths: np.ndarray    # (7,) m, ordre BONE_NAMES
    strengths: np.ndarray  # (2, 4, 2) [côté, articulation, (+, −)], dans [0, S_MAX]
    period: float          # s, période de l'horloge
    targets: np.ndarray    # (K, 8) rad, φ cible de chaque articulation pour chaque pose
    holds: np.ndarray      # (K, 4) bool, patte tenue dans chaque pose (ordre LIMBS)

    @property
    def n_poses(self):
        return len(self.targets)

    def muscle_mass(self):
        """Somme des forces max des 16 muscles (§2.3). La queue n'a pas de muscles : elle n'y entre pas."""
        return float(self.strengths.sum())

    def copy(self):
        return replace(self, lengths=self.lengths.copy(), strengths=self.strengths.copy(),
                       targets=self.targets.copy(), holds=self.holds.copy())


def random_genome(rng, n_poses=None):
    """Génome aléatoire de la génération 0, avec les plages d'init du §2.5."""
    k = config.N_POSES if n_poses is None else n_poses
    lengths = reference_lengths() * rng.uniform(*config.LENGTH_FACTOR_RANGE, size=len(BONE_NAMES))
    if config.SYMMETRIC_MORPHOLOGY:
        half = rng.uniform(0.0, config.S_MAX, size=(4, 2))
        strengths = np.stack([half, half])
    else:
        strengths = rng.uniform(0.0, config.S_MAX, size=(2, 4, 2))
    period = rng.uniform(*config.PERIOD_INIT)
    span = math.radians(config.TARGET_RANGE_DEG)
    targets = rng.uniform(-span, span, size=(k, 8))
    holds = rng.random(size=(k, 4)) < config.HOLD_PROBABILITY
    return Genome(lengths, strengths, float(period), targets, holds)


def diagonal_gait_genome(period=2.0, strength=1.0, swing_deg=40.0, double_support=True):
    """Poses écrites à la main (§10, phase 2) : allure diagonale, K = 4 poses.

    Pose A : main G + pied D tiennent. Le grand dorsal et le biceps G tirent, le fessier
             et le quadriceps D poussent ; main D et pied G, libres, remontent
             (deltoïde + triceps D, fléchisseur de hanche + ischios G).
    Pose A': mêmes cibles, les 4 pattes tiennent : la main et le pied qui viennent de
             monter se posent avant que les deux autres lâchent (double appui).
    Poses B, B' : l'inverse (main D + pied G).
    Sans le double appui (A, A, B, B), l'allure monte plus vite (+5.2 m en 10 s) mais le
    corps penche un peu plus à chaque cycle, et la créature tombe vers 12–14 s : le
    contrôleur ne connaît que les angles des articulations, pas l'orientation du corps.
    """
    a = math.radians(swing_deg)
    # Ordre des cibles : épaule, coude, hanche, genou (côté gauche puis droit).
    pull_arm_raise_leg = [-a, +0.8 * a, +a, +0.8 * a]    # bras qui tire, jambe qui remonte
    reach_arm_push_leg = [+a, -0.6 * a, -a, -0.6 * a]    # bras qui remonte, jambe qui pousse
    pose_a = np.array(pull_arm_raise_leg + reach_arm_push_leg)
    pose_b = np.array(reach_arm_push_leg + pull_arm_raise_leg)  # miroir : on échange les côtés
    hold_a = np.array([True, False, False, True])    # main G, pied D
    hold_b = np.array([False, True, True, False])    # main D, pied G
    hold_a2 = np.ones(4, dtype=bool) if double_support else hold_a
    hold_b2 = np.ones(4, dtype=bool) if double_support else hold_b
    strengths = np.full((2, 4, 2), float(strength))
    return Genome(reference_lengths(), strengths, float(period),
                  np.array([pose_a, pose_a, pose_b, pose_b]),
                  np.array([hold_a, hold_a2, hold_b, hold_b2]))


def limp_genome():
    """Créature inerte : aucun muscle, aucune prise (elle tombe)."""
    genome = diagonal_gait_genome()
    genome.strengths[:] = 0.0
    genome.holds[:] = False
    return genome


# ---------------------------------------------------------------------------
# Créature simulée
# ---------------------------------------------------------------------------
class Creature:
    """Un génome incarné : monde physique + horloge + contrôleur PD (§2.4)."""

    def __init__(self, genome, start_height=None, x=None):
        self.genome = genome
        start = config.START_HEIGHT if start_height is None else start_height
        x = config.TRUNK_X if x is None else x
        lengths = {n: float(v) for n, v in zip(BONE_NAMES, genome.lengths)}
        self.skel = sk.build_skeleton(lengths, head_length=config.HEAD_LENGTH * config.BODY_SCALE)
        origin = np.array([x, config.GROUND_Y + start]) - self._reference(self.skel.pos)
        self.world = self.skel.make_world(origin=origin)
        self.world.ground_y = config.GROUND_Y
        self.world.joints = np.array(JOINTS, dtype=np.int64)
        self.world.torque = np.zeros(len(JOINTS))
        self.phi_rest = JOINT_SIGNS * self.world.joint_angles()
        self.body_points = np.arange(sk.TAIL_START)  # tout sauf la queue
        self.ref_y0 = self.reference_point()[1]
        self.t = 0.0
        self.pose_index = -1
        self.energy = 0.0
        self.fallen = False
        self.activation = np.zeros(len(JOINTS))  # force musculaire signée de chaque articulation

    @staticmethod
    def _reference(pos):
        """Point de référence de la hauteur (§1.7) : centre du torse (milieu NECK–PELVIS)."""
        return 0.5 * (pos[sk.NECK] + pos[sk.PELVIS])

    def reference_point(self):
        return self._reference(self.world.pos)

    def height(self):
        """Hauteur grimpée depuis le départ (m), celle qu'affiche le HUD."""
        return float(self.reference_point()[1] - self.ref_y0)

    def muscle_mass(self):
        return self.genome.muscle_mass()

    def score(self):
        return fitness(self.height(), self.energy, self.muscle_mass())

    def joint_phi(self):
        """φ de chaque articulation (rad, 0 = repos, + = sens du muscle « + »)."""
        return wrap_angle(JOINT_SIGNS * self.world.joint_angles() - self.phi_rest)

    def joint_phi_rate(self):
        return JOINT_SIGNS * self.world.joint_velocities()

    def current_pose(self, t=None):
        t = self.t if t is None else t
        k = self.genome.n_poses
        phase = (t % self.genome.period) / self.genome.period
        return min(int(phase * k), k - 1)

    @staticmethod
    def on_trunk(p):
        """Le mur : une patte ne peut tenir que sur la bande verticale du tronc."""
        return abs(p[0] - config.TRUNK_X) <= config.TRUNK_WIDTH / 2

    def apply_holds(self, pose):
        """Début d'intervalle : chaque patte tient (à sa position courante) ou lâche (§2.4)."""
        for limb, want in zip(LIMBS, self.genome.holds[pose]):
            self.world.held[limb] = bool(want) and not self.fallen and self.on_trunk(self.world.pos[limb])

    def control(self, pose):
        """Contrôleur PD (§2.4) : u = clamp(Kp·(φ_cible − φ) − Kd·φ', −S_minus, +S_plus)."""
        error = wrap_angle(self.genome.targets[pose] - self.joint_phi())
        u = config.KP * error - config.KD * self.joint_phi_rate()
        s_plus = self.genome.strengths[:, :, 0].reshape(-1)
        s_minus = self.genome.strengths[:, :, 1].reshape(-1)
        self.activation = np.clip(u, -s_minus, s_plus)
        self.world.torque = JOINT_SIGNS * self.activation * torque_unit()

    def substep(self, h):
        pose = self.current_pose()
        if pose != self.pose_index:
            self.apply_holds(pose)
            self.pose_index = pose
        self.control(pose)
        rate = self.joint_phi_rate() if config.ENERGY_MODE == "power" else None
        physics.substep(self.world, h)
        if config.ENERGY_MODE == "power":
            self.energy += float(np.sum(np.abs(self.activation * rate))) * h
        else:
            self.energy += float(np.sum(np.abs(self.activation))) * h
        if not self.fallen and np.any(self.world.pos[self.body_points, 1]
                                      <= config.GROUND_Y + config.FALL_CONTACT_EPS):
            self.fallen = True
            if config.FALL_DISABLES_HOLD:
                self.world.held[:] = False
        self.t += h

    def simulate(self, duration, h=None, callback=None):
        h = config.DT / config.SUBSTEPS if h is None else h
        for _ in range(int(round(duration / h))):
            self.substep(h)
            if callback is not None:
                callback(self)
        return self
