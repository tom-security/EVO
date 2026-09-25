"""Moteur physique maison (§1 de la spec).

Les fonctions portent les noms de la slide « Moteur physique » (image 19) :
Movement(), Gravity(), Hold(), Link(), Contract().

Un `World` = un seul système. Tout est en numpy, sauf le solveur de liens
(Gauss-Seidel sur les vitesses + projection de position), séquentiel par nature :
il est compilé avec numba. La même boucle en Python pur est gardée comme référence
(`backend="python"`), et les tests vérifient que les deux donnent le même résultat.

Butées articulaires (chantier B2) : contraintes à sens unique sur l'angle des articulations,
résolues dans les mêmes passes que les liens, avec le schéma du contact au sol (terme spéculatif,
biais BETA, projection de position) ; l'impulsion a la forme de Contract().
"""
import math

import numpy as np

import config

try:
    from numba import njit
    HAVE_NUMBA = True
except ImportError:  # repli : la référence Python pure
    HAVE_NUMBA = False

    def njit(*args, **kwargs):
        return lambda f: f


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
        # Butées (B2) : u = limit_sign[q]·θ_q doit rester dans [limit_lo[q], limit_hi[q]] (rad), θ_q étant l'angle
        # signé de l'articulation q (joint_angles). Tableaux vides : aucune butée (set_joint_limits les pose).
        self.limit_sign = np.zeros(0)
        self.limit_lo = np.zeros(0)
        self.limit_hi = np.zeros(0)
        self.limit_margin = math.radians(config.JOINT_LIMIT_MARGIN_DEG)
        self.limit_active = np.zeros(0, dtype=bool)  # butées entrées dans le solveur au dernier sous-pas
        self.contract_forces = np.zeros((n, 2))  # dernières forces de Contract(), pour affichage/vérif
        self.t = 0.0

        # Paramètres du solveur, propres à chaque monde (les bancs en font varier certains).
        self.g = config.G
        self.n_iter = config.N_ITER
        self.beta = config.BETA
        self.n_pos_iter = config.N_POS_ITER
        self.damping = config.DAMPING
        self.link_mode = "rigid"  # "rigid" (méthode de la vidéo) ou "spring" (méthode naïve, banc 4)
        self.backend = "numba" if (config.USE_NUMBA and HAVE_NUMBA) else "python"
        self.ground_y = None  # hauteur du sol (None = pas de sol) ; les bancs de la phase 1 n'en ont pas
        self.ground_friction = config.GROUND_FRICTION
        self.contact_margin = config.CONTACT_MARGIN

    def set_joint_limits(self, sign, lo, hi):
        """Une butée par articulation de `joints` : limit_sign·θ reste dans [lo, hi] (rad, hi − lo < 2π)."""
        sign, lo, hi = (np.array(x, dtype=np.float64).reshape(-1) for x in (sign, lo, hi))
        if not len(sign) == len(lo) == len(hi) == len(self.joints):
            raise ValueError("une butée par articulation")
        if np.any(hi <= lo) or np.any(hi - lo >= 2 * math.pi):
            raise ValueError("butées : il faut lo < hi et hi − lo < 2π")
        self.limit_sign, self.limit_lo, self.limit_hi = sign, lo, hi
        self.limit_active = np.zeros(len(lo), dtype=bool)

    def limit_violation(self):
        """(J,) distance (rad) de chaque articulation à sa butée la plus proche : > 0 dans la plage, < 0 au-delà."""
        a, p, b = self.joints.T if len(self.limit_lo) else (np.zeros(0, int),) * 3
        out = np.empty(len(self.limit_lo))
        for q in range(len(out)):
            out[q] = _limit_geometry_py(*self.pos[a[q]], *self.pos[p[q]], *self.pos[b[q]],
                                        self.limit_sign[q], self.limit_lo[q], self.limit_hi[q])[0]
        return out

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
        """Angle signé (rad) de rA = A−P vers rB = B−P, dans ]−π, π].

        math.atan2 (bibliothèque C) plutôt que np.arctan2 : la version vectorisée de numpy
        diffère d'un bit dans ~7 % des cas, et numba utilise la bibliothèque C. Avec la même
        fonction, l'évaluateur batché (evo/batch.py) reproduit ce moteur au bit près.
        """
        a, p, b = self.joints.T
        ra = self.pos[a] - self.pos[p]
        rb = self.pos[b] - self.pos[p]
        cross = ra[:, 0] * rb[:, 1] - ra[:, 1] * rb[:, 0]
        dot = np.sum(ra * rb, axis=1)
        return np.array([math.atan2(y, x) for y, x in zip(cross.tolist(), dot.tolist())])

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
    """Link() : liens rigides par correction des vitesses (§1.4), et contacts avec le sol.

    Pour chaque lien, on annule la vitesse relative le long de l'axe par deux
    impulsions opposées. On répète la passe sur tous les liens `n_iter` fois
    (Gauss-Seidel) : chaque passe réduit l'erreur. Le biais de Baumgarte
    (beta·C/h) ramène doucement les longueurs qui ont dérivé.
    Le sol (§1.7) est résolu dans les mêmes passes : impulsion normale ≥ 0 qui
    empêche de le traverser, frottement de Coulomb borné par μ × l'impulsion normale.
    """
    ground = world.ground_y is not None
    if (len(world.links) == 0 and not ground and len(world.limit_lo) == 0) or world.n_iter <= 0:
        return
    kernel = _link_velocities_numba if world.backend == "numba" else _link_velocities_python
    kernel(world.pos, world.vel, world.inv_mass, world.links, world.rest,
           float(h), int(world.n_iter), float(world.beta),
           ground, float(world.ground_y or 0.0), float(world.ground_friction), float(world.contact_margin),
           world.joints, world.limit_sign, world.limit_lo, world.limit_hi, float(world.limit_margin),
           world.limit_active)


def project_links(world):
    """Projection de position (§1.4, étape 4) : ramène chaque lien à sa longueur, pondéré par 1/m.

    Avec un sol, chaque passe remonte aussi au niveau du sol les points passés dessous.
    """
    ground = world.ground_y is not None
    if (len(world.links) == 0 and not ground and len(world.limit_lo) == 0) or world.n_pos_iter <= 0:
        return
    kernel = _project_links_numba if world.backend == "numba" else _project_links_python
    kernel(world.pos, world.inv_mass, world.links, world.rest, int(world.n_pos_iter),
           ground, float(world.ground_y or 0.0), world.joints, world.limit_sign, world.limit_lo, world.limit_hi,
           float(world.limit_margin))


# Noyaux du solveur. Les versions numba et Python font exactement les mêmes
# opérations dans le même ordre ; elles modifient `vel` / `pos` sur place.

# Butées : trois petites fonctions partagées par les noyaux scalaires, leur référence Python et
# l'évaluateur batché (evo/batch.py), pour que tous fassent les mêmes opérations dans le même ordre.
@njit(cache=True)
def _limit_geometry(ax, ay, px, py, bx, by, sign, lo, hi):
    """Butée de l'articulation (A, pivot P, B) : (C, s, J_A, J_B).

    u = sign·θ doit rester dans [lo, hi]. C = distance (rad) à la borne la plus proche sur le cercle
    (> 0 dans la plage, < 0 au-delà : un angle très hors bornes repart par le côté le plus court) ;
    Ċ = s·θ̇. J_A, J_B : gradient de θ par rapport à A et B (celui de P vaut −(J_A + J_B)), soit la
    forme des forces de Contract().
    """
    rax = ax - px
    ray = ay - py
    rbx = bx - px
    rby = by - py
    da = rax * rax + ray * ray
    db = rbx * rbx + rby * rby
    theta = math.atan2(rax * rby - ray * rbx, rax * rbx + ray * rby)
    delta = (sign * theta - 0.5 * (lo + hi) + math.pi) % (2.0 * math.pi) - math.pi
    half = 0.5 * (hi - lo)
    if delta >= 0.0:  # borne haute : C = demi-largeur − δ, Ċ = −sign·θ̇
        return half - delta, -sign, ray / da, -rax / da, -rby / db, rbx / db
    return half + delta, sign, ray / da, -rax / da, -rby / db, rbx / db


@njit(cache=True)
def _limit_mass(wa, wb, wp, jax, jay, jbx, jby):
    """(K, J_P) : masse effective inverse de la butée (w = 1/m, 0 si tenu) et gradient pour le pivot."""
    jpx = -(jax + jbx)
    jpy = -(jay + jby)
    return wa * (jax * jax + jay * jay) + wb * (jbx * jbx + jby * jby) + wp * (jpx * jpx + jpy * jpy), jpx, jpy


@njit(cache=True)
def _limit_rate(jax, jay, jbx, jby, jpx, jpy, vax, vay, vbx, vby, vpx, vpy):
    """θ̇ = J·v de l'articulation."""
    return jax * vax + jay * vay + jbx * vbx + jby * vby + jpx * vpx + jpy * vpy


# versions Python pures (référence) : mêmes opérations
_limit_geometry_py = getattr(_limit_geometry, "py_func", _limit_geometry)
_limit_mass_py = getattr(_limit_mass, "py_func", _limit_mass)
_limit_rate_py = getattr(_limit_rate, "py_func", _limit_rate)

@njit(cache=True)
def _link_velocities_numba(pos, vel, inv_mass, links, rest, h, n_iter, beta,
                           ground, ground_y, friction, margin,
                           joints, lim_sign, lim_lo, lim_hi, lim_margin, lim_active):
    n_links = links.shape[0]
    n_points = pos.shape[0]
    nx = np.zeros(n_links)
    ny = np.zeros(n_links)
    bias = np.zeros(n_links)
    active = np.zeros(n_links, dtype=np.bool_)
    # Les positions ne bougent pas pendant les passes : axes et biais calculés une fois.
    for k in range(n_links):
        i, j = links[k, 0], links[k, 1]
        dx = pos[j, 0] - pos[i, 0]
        dy = pos[j, 1] - pos[i, 1]
        dist = math.sqrt(dx * dx + dy * dy)
        if inv_mass[i] + inv_mass[j] == 0.0 or dist < 1e-12:
            continue
        active[k] = True
        nx[k] = dx / dist
        ny[k] = dy / dist
        bias[k] = beta * (dist - rest[k]) / h
    # Contacts avec le sol : points libres proches du sol ou qui vont le traverser.
    # vn_min = vitesse verticale minimale : s'approcher jusqu'au sol, ou en ressortir.
    contact = np.zeros(n_points, dtype=np.bool_)
    vn_min = np.zeros(n_points)
    lam_n = np.zeros(n_points)
    lam_t = np.zeros(n_points)
    if ground:
        for p in range(n_points):
            gap = pos[p, 1] - ground_y
            if inv_mass[p] > 0.0 and (gap < margin or gap + vel[p, 1] * h < 0.0):
                contact[p] = True
                vn_min[p] = -gap / h if gap > 0.0 else -beta * gap / h
    # Butées : comme le contact au sol. Entrent dans le solveur à moins de lim_margin, ou si le sous-pas les
    # franchirait ; Ċ ≥ −C/h avant la butée (y arriver, pas au-delà), Ċ ≥ −beta·C/h au-delà ; impulsion cumulée ≥ 0.
    n_lim = lim_lo.shape[0]
    l_on = np.zeros(n_lim, dtype=np.bool_)
    l_s = np.zeros(n_lim)
    l_j = np.zeros((n_lim, 6))
    l_k = np.zeros(n_lim)
    l_min = np.zeros(n_lim)
    l_lam = np.zeros(n_lim)
    for q in range(n_lim):
        a, p, b = joints[q, 0], joints[q, 1], joints[q, 2]
        c, s, jax, jay, jbx, jby = _limit_geometry(pos[a, 0], pos[a, 1], pos[p, 0], pos[p, 1],
                                                   pos[b, 0], pos[b, 1], lim_sign[q], lim_lo[q], lim_hi[q])
        kk, jpx, jpy = _limit_mass(inv_mass[a], inv_mass[b], inv_mass[p], jax, jay, jbx, jby)
        rate = s * _limit_rate(jax, jay, jbx, jby, jpx, jpy, vel[a, 0], vel[a, 1], vel[b, 0], vel[b, 1],
                               vel[p, 0], vel[p, 1])
        on = kk > 0.0 and (c < lim_margin or c + rate * h < 0.0)
        lim_active[q] = on
        if on:
            l_on[q] = True
            l_s[q] = s
            l_j[q, 0], l_j[q, 1], l_j[q, 2], l_j[q, 3], l_j[q, 4], l_j[q, 5] = jax, jay, jbx, jby, jpx, jpy
            l_k[q] = kk
            l_min[q] = -c / h if c > 0.0 else -beta * c / h
    for _ in range(n_iter):
        for k in range(n_links):
            if not active[k]:
                continue
            i, j = links[k, 0], links[k, 1]
            wi, wj = inv_mass[i], inv_mass[j]
            vrel = (vel[j, 0] - vel[i, 0]) * nx[k] + (vel[j, 1] - vel[i, 1]) * ny[k]
            lam = -(vrel + bias[k]) / (wi + wj)
            vel[i, 0] -= lam * wi * nx[k]
            vel[i, 1] -= lam * wi * ny[k]
            vel[j, 0] += lam * wj * nx[k]
            vel[j, 1] += lam * wj * ny[k]
        for q in range(n_lim):
            if not l_on[q]:
                continue
            a, p, b = joints[q, 0], joints[q, 1], joints[q, 2]
            rate = l_s[q] * _limit_rate(l_j[q, 0], l_j[q, 1], l_j[q, 2], l_j[q, 3], l_j[q, 4], l_j[q, 5],
                                        vel[a, 0], vel[a, 1], vel[b, 0], vel[b, 1], vel[p, 0], vel[p, 1])
            new = max(l_lam[q] + (l_min[q] - rate) / l_k[q], 0.0)
            d = (new - l_lam[q]) * l_s[q]
            l_lam[q] = new
            wa, wb, wp = inv_mass[a], inv_mass[b], inv_mass[p]
            vel[a, 0] += wa * l_j[q, 0] * d
            vel[a, 1] += wa * l_j[q, 1] * d
            vel[b, 0] += wb * l_j[q, 2] * d
            vel[b, 1] += wb * l_j[q, 3] * d
            vel[p, 0] += wp * l_j[q, 4] * d
            vel[p, 1] += wp * l_j[q, 5] * d
        if ground:
            for p in range(n_points):
                if not contact[p]:
                    continue
                # impulses cumulées (par unité de masse) : normale ≥ 0, |tangente| ≤ μ·normale
                new_n = max(lam_n[p] + vn_min[p] - vel[p, 1], 0.0)
                vel[p, 1] += new_n - lam_n[p]
                lam_n[p] = new_n
                bound = friction * new_n
                new_t = min(max(lam_t[p] - vel[p, 0], -bound), bound)
                vel[p, 0] += new_t - lam_t[p]
                lam_t[p] = new_t


@njit(cache=True)
def _project_links_numba(pos, inv_mass, links, rest, n_pos_iter, ground, ground_y,
                         joints, lim_sign, lim_lo, lim_hi, lim_margin):
    # butées candidates : à moins de lim_margin de la borne au début de la projection (les passes ne déplacent
    # les points que de corrections de longueur, bien plus petites) ; les autres ne sont pas recalculées
    n_lim = lim_lo.shape[0]
    near = np.zeros(n_lim, dtype=np.bool_)
    for q in range(n_lim):
        a, p, b = joints[q, 0], joints[q, 1], joints[q, 2]
        near[q] = _limit_geometry(pos[a, 0], pos[a, 1], pos[p, 0], pos[p, 1], pos[b, 0], pos[b, 1],
                                  lim_sign[q], lim_lo[q], lim_hi[q])[0] < lim_margin
    for _ in range(n_pos_iter):
        for k in range(links.shape[0]):
            i, j = links[k, 0], links[k, 1]
            wi, wj = inv_mass[i], inv_mass[j]
            if wi + wj == 0.0:
                continue
            dx = pos[j, 0] - pos[i, 0]
            dy = pos[j, 1] - pos[i, 1]
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < 1e-12:
                continue
            c = (dist - rest[k]) / ((wi + wj) * dist)
            pos[i, 0] += wi * c * dx
            pos[i, 1] += wi * c * dy
            pos[j, 0] -= wj * c * dx
            pos[j, 1] -= wj * c * dy
        for q in range(n_lim):  # butées franchies : ramenées sur la borne (linéarisé, affiné à chaque passe)
            if not near[q]:
                continue
            a, p, b = joints[q, 0], joints[q, 1], joints[q, 2]
            cq, s, jax, jay, jbx, jby = _limit_geometry(pos[a, 0], pos[a, 1], pos[p, 0], pos[p, 1],
                                                        pos[b, 0], pos[b, 1], lim_sign[q], lim_lo[q], lim_hi[q])
            if cq >= 0.0:
                continue
            wa, wb, wp = inv_mass[a], inv_mass[b], inv_mass[p]
            kk, jpx, jpy = _limit_mass(wa, wb, wp, jax, jay, jbx, jby)
            if kk == 0.0:
                continue
            mu = -cq / kk * s
            pos[a, 0] += wa * jax * mu
            pos[a, 1] += wa * jay * mu
            pos[b, 0] += wb * jbx * mu
            pos[b, 1] += wb * jby * mu
            pos[p, 0] += wp * jpx * mu
            pos[p, 1] += wp * jpy * mu
        if ground:
            for p in range(pos.shape[0]):
                if inv_mass[p] > 0.0 and pos[p, 1] < ground_y:
                    pos[p, 1] = ground_y


def _link_velocities_python(pos, vel, inv_mass, links, rest, h, n_iter, beta,
                            ground, ground_y, friction, margin,
                            joints, lim_sign, lim_lo, lim_hi, lim_margin, lim_active):
    """Référence Python pure de `_link_velocities_numba` (listes Python pour la vitesse)."""
    w = inv_mass.tolist()
    px, py = pos[:, 0].tolist(), pos[:, 1].tolist()
    vx, vy = vel[:, 0].tolist(), vel[:, 1].tolist()
    constraints = []
    for (i, j), r in zip(links.tolist(), rest.tolist()):
        dx, dy = px[j] - px[i], py[j] - py[i]
        dist = math.sqrt(dx * dx + dy * dy)
        if w[i] + w[j] == 0.0 or dist < 1e-12:
            continue
        constraints.append((i, j, dx / dist, dy / dist, beta * (dist - r) / h))
    contacts = []  # [point, vn_min, impulsion normale cumulée, impulsion tangente cumulée]
    if ground:
        for p in range(len(px)):
            gap = py[p] - ground_y
            if w[p] > 0.0 and (gap < margin or gap + vy[p] * h < 0.0):
                contacts.append([p, -gap / h if gap > 0.0 else -beta * gap / h, 0.0, 0.0])
    stops = []  # [a, p, b, s, J (6), K, Ċ minimal, impulsion cumulée]
    for q, ((a, p, b), sign, lo, hi) in enumerate(zip(joints.tolist()[:len(lim_lo)], lim_sign.tolist(),
                                                       lim_lo.tolist(), lim_hi.tolist())):
        c, s, jax, jay, jbx, jby = _limit_geometry_py(px[a], py[a], px[p], py[p], px[b], py[b], sign, lo, hi)
        kk, jpx, jpy = _limit_mass_py(w[a], w[b], w[p], jax, jay, jbx, jby)
        rate = s * _limit_rate_py(jax, jay, jbx, jby, jpx, jpy, vx[a], vy[a], vx[b], vy[b], vx[p], vy[p])
        on = kk > 0.0 and (c < lim_margin or c + rate * h < 0.0)
        lim_active[q] = on
        if on:
            stops.append([a, p, b, s, (jax, jay, jbx, jby, jpx, jpy), kk, -c / h if c > 0.0 else -beta * c / h, 0.0])
    for _ in range(n_iter):
        for i, j, nx, ny, bias in constraints:
            wi, wj = w[i], w[j]
            vrel = (vx[j] - vx[i]) * nx + (vy[j] - vy[i]) * ny
            lam = -(vrel + bias) / (wi + wj)
            vx[i] -= lam * wi * nx
            vy[i] -= lam * wi * ny
            vx[j] += lam * wj * nx
            vy[j] += lam * wj * ny
        for st in stops:
            a, p, b, s, J, kk, cmin, lam = st
            rate = s * _limit_rate_py(*J, vx[a], vy[a], vx[b], vy[b], vx[p], vy[p])
            new = max(lam + (cmin - rate) / kk, 0.0)
            d = (new - lam) * s
            st[7] = new
            wa, wb, wp = w[a], w[b], w[p]
            vx[a] += wa * J[0] * d
            vy[a] += wa * J[1] * d
            vx[b] += wb * J[2] * d
            vy[b] += wb * J[3] * d
            vx[p] += wp * J[4] * d
            vy[p] += wp * J[5] * d
        for c in contacts:
            p, vmin, lam_n, lam_t = c
            new_n = max(lam_n + vmin - vy[p], 0.0)
            vy[p] += new_n - lam_n
            bound = friction * new_n
            new_t = min(max(lam_t - vx[p], -bound), bound)
            vx[p] += new_t - lam_t
            c[2], c[3] = new_n, new_t
    vel[:, 0] = vx
    vel[:, 1] = vy


def _project_links_python(pos, inv_mass, links, rest, n_pos_iter, ground, ground_y,
                          joints, lim_sign, lim_lo, lim_hi, lim_margin):
    """Référence Python pure de `_project_links_numba`."""
    w = inv_mass.tolist()
    px, py = pos[:, 0].tolist(), pos[:, 1].tolist()
    pairs = list(zip(links.tolist(), rest.tolist()))
    stops = [((a, p, b), sign, lo, hi) for (a, p, b), sign, lo, hi
             in zip(joints.tolist()[:len(lim_lo)], lim_sign.tolist(), lim_lo.tolist(), lim_hi.tolist())
             if _limit_geometry_py(px[a], py[a], px[p], py[p], px[b], py[b], sign, lo, hi)[0] < lim_margin]
    for _ in range(n_pos_iter):
        for (i, j), r in pairs:
            wi, wj = w[i], w[j]
            if wi + wj == 0.0:
                continue
            dx, dy = px[j] - px[i], py[j] - py[i]
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < 1e-12:
                continue
            c = (dist - r) / ((wi + wj) * dist)
            px[i] += wi * c * dx
            py[i] += wi * c * dy
            px[j] -= wj * c * dx
            py[j] -= wj * c * dy
        for (a, p, b), sign, lo, hi in stops:
            cq, s, jax, jay, jbx, jby = _limit_geometry_py(px[a], py[a], px[p], py[p], px[b], py[b], sign, lo, hi)
            if cq >= 0.0:
                continue
            wa, wb, wp = w[a], w[b], w[p]
            kk, jpx, jpy = _limit_mass_py(wa, wb, wp, jax, jay, jbx, jby)
            if kk == 0.0:
                continue
            mu = -cq / kk * s
            px[a] += wa * jax * mu
            py[a] += wa * jay * mu
            px[b] += wb * jbx * mu
            py[b] += wb * jby * mu
            px[p] += wp * jpx * mu
            py[p] += wp * jpy * mu
        if ground:
            for p in range(len(py)):
                if w[p] > 0.0 and py[p] < ground_y:
                    py[p] = ground_y
    pos[:, 0] = px
    pos[:, 1] = py


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
