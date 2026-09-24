"""Moteur physique maison (§1 de la spec).

Les fonctions portent les noms de la slide « Moteur physique » (image 19) :
Movement(), Gravity(), Hold(), Link(), Contract().

Phase 1 : un `World` = un seul système, en numpy. Le solveur de liens est une boucle
Python car Gauss-Seidel est séquentiel par nature ; il passera en numba batché
(B, P, 2) en phase 3 sans changer ces noms ni la séparation topologie / longueurs.
"""
import math

import numpy as np

import config


def compute_masses(n_points, links, rest, is_bone):
    """Masse d'un point = somme des demi-longueurs des os qui y sont attachés (§1.6).

    Les liens de rigidité invisibles (is_bone=False) ne comptent pas.
    """
    links = np.asarray(links, dtype=np.int64).reshape(-1, 2)
    rest = np.asarray(rest, dtype=np.float64)
    is_bone = np.asarray(is_bone, dtype=bool)
    mass = np.zeros(n_points)
    half = 0.5 * rest[is_bone]
    np.add.at(mass, links[is_bone, 0], half)
    np.add.at(mass, links[is_bone, 1], half)
    return mass


class World:
    """État d'un système de points liés.

    pos, vel : (P, 2)   mass, held : (P,)
    links : (L, 2) indices   rest : (L,) longueurs au repos   is_bone : (L,)
    joints : (J, 3) triplets (A, pivot, B)   torque : (J,) couple appliqué à chaque sous-pas
    """

    def __init__(self, pos, links=(), rest=None, is_bone=None, mass=None,
                 held=None, vel=None, joints=()):
        self.pos = np.array(pos, dtype=np.float64).reshape(-1, 2)
        n = len(self.pos)
        self.vel = np.zeros((n, 2)) if vel is None else np.array(vel, dtype=np.float64).reshape(n, 2)
        self.links = np.array(links, dtype=np.int64).reshape(-1, 2)
        self.rest = self.link_lengths() if rest is None else np.array(rest, dtype=np.float64)
        self.is_bone = (np.ones(len(self.links), dtype=bool) if is_bone is None
                        else np.array(is_bone, dtype=bool))
        if mass is None:
            mass = compute_masses(n, self.links, self.rest, self.is_bone)
        self.mass = np.array(mass, dtype=np.float64).reshape(n)
        if np.any(self.mass <= 0):
            raise ValueError("chaque point doit avoir une masse > 0 (relié à au moins un os)")
        self.held = np.zeros(n, dtype=bool) if held is None else np.array(held, dtype=bool)
        self.joints = np.array(joints, dtype=np.int64).reshape(-1, 3)
        self.torque = np.zeros(len(self.joints))
        self.contract_forces = np.zeros((n, 2))  # dernières forces de Contract(), pour affichage/vérif
        self.t = 0.0

        # Paramètres du solveur, propres à chaque monde (les bancs en font varier certains).
        self.g = config.G
        self.n_iter = config.N_ITER
        self.beta = config.BETA
        self.n_pos_iter = config.N_POS_ITER
        self.damping = config.DAMPING
        self.link_mode = "rigid"  # "rigid" (méthode de la vidéo) ou "spring" (méthode naïve, banc 4)

    @property
    def inv_mass(self):
        w = 1.0 / self.mass
        w[self.held] = 0.0
        return w

    def link_lengths(self):
        d = self.pos[self.links[:, 1]] - self.pos[self.links[:, 0]]
        return np.hypot(d[:, 0], d[:, 1])

    def length_error(self):
        """Erreur relative de longueur maximale sur tous les liens."""
        if len(self.links) == 0:
            return 0.0
        return float(np.max(np.abs(self.link_lengths() - self.rest) / self.rest))

    def velocity_residual(self):
        """Plus grande vitesse relative le long d'un lien (0 = liens parfaitement respectés)."""
        if len(self.links) == 0:
            return 0.0
        i, j = self.links[:, 0], self.links[:, 1]
        d = self.pos[j] - self.pos[i]
        n = d / np.hypot(d[:, 0], d[:, 1])[:, None]
        return float(np.max(np.abs(np.sum((self.vel[j] - self.vel[i]) * n, axis=1))))

    def joint_angles(self):
        """Angle signé (rad) de rA = A−P vers rB = B−P, dans ]−π, π]."""
        a, p, b = self.joints.T
        ra = self.pos[a] - self.pos[p]
        rb = self.pos[b] - self.pos[p]
        cross = ra[:, 0] * rb[:, 1] - ra[:, 1] * rb[:, 0]
        dot = np.sum(ra * rb, axis=1)
        return np.arctan2(cross, dot)

    def joint_velocities(self):
        """Vitesse angulaire (rad/s) de l'angle signé de chaque articulation."""
        a, p, b = self.joints.T
        ra, rb = self.pos[a] - self.pos[p], self.pos[b] - self.pos[p]
        va, vb = self.vel[a] - self.vel[p], self.vel[b] - self.vel[p]
        wa = (ra[:, 0] * va[:, 1] - ra[:, 1] * va[:, 0]) / np.sum(ra * ra, axis=1)
        wb = (rb[:, 0] * vb[:, 1] - rb[:, 1] * vb[:, 0]) / np.sum(rb * rb, axis=1)
        return wb - wa

    def kinetic_energy(self):
        return float(0.5 * np.sum(self.mass * np.sum(self.vel ** 2, axis=1)))

    def potential_energy(self):
        return float(np.sum(self.mass * self.g * self.pos[:, 1]))

    def momentum(self):
        return np.sum(self.mass[:, None] * self.vel, axis=0)


# ---------------------------------------------------------------------------
# Les 5 fonctions de la vidéo
# ---------------------------------------------------------------------------

def movement(world, h):
    """Movement() : on ajoute la vitesse à la position (Euler semi-implicite, §1.1)."""
    world.pos += world.vel * h


def gravity(world, h):
    """Gravity() : g·h ajouté vers le bas à la vitesse des points non fixés (§1.2)."""
    world.vel[~world.held, 1] -= world.g * h


def hold(world):
    """Hold() : un point fixé garde une vitesse nulle (§1.3)."""
    world.vel[world.held] = 0.0


def contraction_forces(pos, joints, torque):
    """Forces d'une contraction d'articulation (§1.5).

    Pour un couple τ sur (A, P, B) : force τ/|A−P| perpendiculaire sur A, force
    τ/|B−P| en sens de rotation opposé sur B, et −(F_A + F_B) sur le pivot.
    Somme des forces nulle et somme des moments nulle (3ᵉ loi de Newton).
    τ > 0 ouvre l'angle signé A→B, τ < 0 le ferme.
    """
    forces = np.zeros_like(pos)
    if len(joints) == 0:
        return forces
    a, p, b = joints.T
    ra = pos[a] - pos[p]
    rb = pos[b] - pos[p]
    perp_a = np.stack([-ra[:, 1], ra[:, 0]], axis=1)
    perp_b = np.stack([-rb[:, 1], rb[:, 0]], axis=1)
    fa = -torque[:, None] * perp_a / np.sum(ra * ra, axis=1)[:, None]
    fb = torque[:, None] * perp_b / np.sum(rb * rb, axis=1)[:, None]
    np.add.at(forces, a, fa)
    np.add.at(forces, b, fb)
    np.add.at(forces, p, -(fa + fb))
    return forces


def contract(world, h):
    """Contract() : applique les couples `world.torque` aux articulations."""
    world.contract_forces = contraction_forces(world.pos, world.joints, world.torque)
    free = ~world.held
    world.vel[free] += world.contract_forces[free] / world.mass[free, None] * h


def link(world, h):
    """Link() : liens rigides par correction des vitesses (§1.4).

    Pour chaque lien, on annule la vitesse relative le long de l'axe par deux
    impulsions opposées. On répète la passe sur tous les liens `n_iter` fois
    (Gauss-Seidel) : chaque passe réduit l'erreur. Le biais de Baumgarte
    (beta·C/h) ramène doucement les longueurs qui ont dérivé.
    """
    if len(world.links) == 0 or world.n_iter <= 0:
        return
    w = world.inv_mass.tolist()
    px, py = world.pos[:, 0].tolist(), world.pos[:, 1].tolist()
    vx, vy = world.vel[:, 0].tolist(), world.vel[:, 1].tolist()

    # Les positions ne bougent pas pendant les passes : axes et biais calculés une fois.
    constraints = []
    for (i, j), rest in zip(world.links.tolist(), world.rest.tolist()):
        wi, wj = w[i], w[j]
        wsum = wi + wj
        dx, dy = px[j] - px[i], py[j] - py[i]
        dist = math.hypot(dx, dy)
        if wsum == 0.0 or dist < 1e-12:
            continue
        bias = world.beta * (dist - rest) / h
        constraints.append((i, j, dx / dist, dy / dist, wi, wj, wsum, bias))

    for _ in range(world.n_iter):
        for i, j, nx, ny, wi, wj, wsum, bias in constraints:
            vrel = (vx[j] - vx[i]) * nx + (vy[j] - vy[i]) * ny
            lam = -(vrel + bias) / wsum
            vx[i] -= lam * wi * nx
            vy[i] -= lam * wi * ny
            vx[j] += lam * wj * nx
            vy[j] += lam * wj * ny

    world.vel[:, 0] = vx
    world.vel[:, 1] = vy


def project_links(world):
    """Projection de position (§1.4, étape 4) : ramène chaque lien à sa longueur, pondéré par 1/m."""
    if len(world.links) == 0 or world.n_pos_iter <= 0:
        return
    w = world.inv_mass.tolist()
    px, py = world.pos[:, 0].tolist(), world.pos[:, 1].tolist()
    links = [(i, j, rest, w[i], w[j], w[i] + w[j])
             for (i, j), rest in zip(world.links.tolist(), world.rest.tolist())
             if w[i] + w[j] > 0.0]
    for _ in range(world.n_pos_iter):
        for i, j, rest, wi, wj, wsum in links:
            dx, dy = px[j] - px[i], py[j] - py[i]
            dist = math.hypot(dx, dy)
            if dist < 1e-12:
                continue
            k = (dist - rest) / (wsum * dist)
            px[i] += wi * k * dx
            py[i] += wi * k * dy
            px[j] -= wj * k * dx
            py[j] -= wj * k * dy
    world.pos[:, 0] = px
    world.pos[:, 1] = py


def spring_link(world, h, k=None, c=None):
    """Méthode naïve (vidéo « créatures aquatiques ») : un ressort amorti par lien.

    La correction arrive après l'écart, donc le lien est élastique. Sert uniquement
    de contre-exemple dans le banc 4.
    """
    if len(world.links) == 0:
        return
    k = config.SPRING_K if k is None else k
    c = config.SPRING_DAMP if c is None else c
    i, j = world.links[:, 0], world.links[:, 1]
    d = world.pos[j] - world.pos[i]
    dist = np.hypot(d[:, 0], d[:, 1])
    n = d / dist[:, None]
    vrel = np.sum((world.vel[j] - world.vel[i]) * n, axis=1)
    tension = k * (dist - world.rest) + c * vrel
    forces = np.zeros_like(world.pos)
    np.add.at(forces, i, tension[:, None] * n)
    np.add.at(forces, j, -tension[:, None] * n)
    free = ~world.held
    world.vel[free] += forces[free] / world.mass[free, None] * h


# ---------------------------------------------------------------------------
# Pas de temps
# ---------------------------------------------------------------------------

def substep(world, h):
    """Un sous-pas : forces -> vitesses, Hold, Link, Movement, projection (§1.4)."""
    gravity(world, h)
    contract(world, h)
    if world.damping > 0.0:
        world.vel *= max(0.0, 1.0 - world.damping * h)
    if world.link_mode == "spring":
        spring_link(world, h)
        hold(world)
        movement(world, h)
    else:
        hold(world)
        link(world, h)
        hold(world)
        movement(world, h)
        project_links(world)
    world.t += h


def step(world, dt=None, substeps=None):
    """Avance d'une frame `dt`, découpée en `substeps` sous-pas."""
    dt = config.DT if dt is None else dt
    substeps = config.SUBSTEPS if substeps is None else substeps
    h = dt / substeps
    for _ in range(substeps):
        substep(world, h)
