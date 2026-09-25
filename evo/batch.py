"""Évaluateur batché (§4, phase 3a) : toute la simulation de 10 s dans un noyau numba.

Un appel = toute la population, `prange` sur des blocs de BATCH_BLOCK créatures, sans
repasser par Python. Chaque créature refait exactement les mêmes opérations, dans le même
ordre, que le moteur scalaire (`Creature.substep` → `physics.substep`) : contrôleur à
horloge + PD, forces des muscles (même ordre d'accumulation que `np.add.at`), prises sur le
tronc, liens + butées articulaires + contacts sol (même calcul que `_link_velocities_numba`, mêmes
fonctions partagées pour les butées), projection, chute, énergie. Dans un bloc, la boucle intérieure passe d'une créature à l'autre : leurs calculs
indépendants s'entrelacent et masquent la latence de Gauss-Seidel (×5 par rapport à une
créature à la fois). Les tests vérifient l'égalité avec le moteur scalaire à 1e-9 près.

Seule l'initialisation (construction du squelette de chaque génome, posture de repos,
masses) passe par Python, via `Creature` : c'est la même que pour le moteur scalaire.
"""
import math
import time

import numpy as np

import config
from evo import creature as cr
from evo import physics
from evo import skeleton as sk
from evo.physics import _limit_geometry, _limit_mass, _limit_rate, njit

try:
    from numba import get_num_threads, prange
except ImportError:  # sans numba : même code, séquentiel
    prange = range

    def get_num_threads():
        return 1


# ---------------------------------------------------------------------------
# Préparation des tableaux de la population
# ---------------------------------------------------------------------------

def pack(genomes):
    """Génomes → tableaux (N, …) : état initial (via Creature) et paramètres du contrôleur."""
    creatures = [cr.Creature(g) for g in genomes]
    first = creatures[0]
    n = len(creatures)
    k = genomes[0].n_poses
    if any(g.n_poses != k for g in genomes):
        raise ValueError("toutes les créatures doivent avoir le même nombre de poses")
    arrays = {
        "pos": np.stack([c.world.pos for c in creatures]),
        "rest": np.stack([c.world.rest for c in creatures]),
        "mass": np.stack([c.world.mass for c in creatures]),
        "phi_rest": np.stack([c.phi_rest for c in creatures]),
        "ref_y0": np.array([c.ref_y0 for c in creatures]),
        "s_plus": np.stack([g.strengths[:, :, 0].reshape(-1) for g in genomes]),
        "s_minus": np.stack([g.strengths[:, :, 1].reshape(-1) for g in genomes]),
        "period": np.array([g.period for g in genomes], dtype=np.float64),
        "targets": np.stack([g.targets for g in genomes]).astype(np.float64),
        "holds": np.stack([g.holds for g in genomes]).astype(np.bool_),
        "muscle_mass": np.array([g.muscle_mass() for g in genomes]),
        "links": first.world.links.copy(),
        "joints": first.world.joints.copy(),
        # butées (B2) en u = signe·θ, celles que pose Creature ; (N, 0) sans butées
        "lim_lo": np.stack([c.world.limit_lo for c in creatures]),
        "lim_hi": np.stack([c.world.limit_hi for c in creatures]),
    }
    if any(not np.array_equal(c.world.limit_sign, first.world.limit_sign) for c in creatures):
        raise ValueError("toutes les créatures doivent avoir les mêmes sens de butée")
    arrays["lim_sign"] = first.world.limit_sign.copy()
    assert arrays["pos"].shape[0] == n
    return arrays


# ---------------------------------------------------------------------------
# Noyau
# ---------------------------------------------------------------------------

@njit(cache=True)
def _pairwise_sum8(a):
    """Somme de 8 valeurs dans l'ordre de numpy (sommation par paires)."""
    return ((a[0] + a[1]) + (a[2] + a[3])) + ((a[4] + a[5]) + (a[6] + a[7]))


@njit(cache=True, error_model="numpy")
def _wrap(x):
    return (x + np.pi) % (2 * np.pi) - np.pi


# error_model="numpy" : pas de test « division par zéro » avant chaque division (numba les
# ajoute par défaut pour lever ZeroDivisionError comme Python). Même arithmétique IEEE.
@njit(cache=True, error_model="numpy")
def _simulate_block(pos, rest, mass, phi_rest, s_plus, s_minus, period, targets, holds, first, last,
                    links, joints, joint_signs, lim_sign, lim_lo, lim_hi, lim_margin, limbs, n_body, n_steps, h,
                    g, n_iter, beta, n_pos_iter, ground_y, friction, margin,
                    kp, kd, torque_unit, trunk_x, trunk_half, fall_eps, fall_disables_hold,
                    energy_out, fallen_out, vel_out):
    """Créatures first..last-1 simulées en même temps (même suite d'opérations que _simulate_one
    pour chacune) : les calculs indépendants de plusieurs créatures s'entrelacent dans la boucle
    intérieure, ce qui masque la latence de Gauss-Seidel. Résultat identique au bit près."""
    nb = last - first
    n_points = pos.shape[1]
    n_links = links.shape[0]
    n_joints = joints.shape[0]
    n_poses = targets.shape[1]
    n_limbs = limbs.shape[0]
    px = np.empty((n_points, nb))
    py = np.empty((n_points, nb))
    vx = np.zeros((n_points, nb))
    vy = np.zeros((n_points, nb))
    m = np.empty((n_points, nb))
    inv = np.zeros((n_points, nb))
    held = np.zeros((n_points, nb), dtype=np.bool_)
    rst = np.empty((n_links, nb))
    for b in range(nb):
        for p in range(n_points):
            px[p, b] = pos[first + b, p, 0]
            py[p, b] = pos[first + b, p, 1]
            m[p, b] = mass[first + b, p]
        for k in range(n_links):
            rst[k, b] = rest[first + b, k]
    theta = np.zeros((n_joints, nb))
    theta_rate = np.zeros((n_joints, nb))
    activation = np.zeros((n_joints, nb))
    torque = np.zeros((n_joints, nb))
    fax = np.zeros((n_joints, nb))
    fay = np.zeros((n_joints, nb))
    fbx = np.zeros((n_joints, nb))
    fby = np.zeros((n_joints, nb))
    fx = np.zeros((n_points, nb))
    fy = np.zeros((n_points, nb))
    nx = np.zeros((n_links, nb))
    ny = np.zeros((n_links, nb))
    bias = np.zeros((n_links, nb))
    active = np.zeros((n_links, nb), dtype=np.bool_)
    contact = np.zeros((n_points, nb), dtype=np.bool_)
    vn_min = np.zeros((n_points, nb))
    lam_n = np.zeros((n_points, nb))
    lam_t = np.zeros((n_points, nb))
    n_lim = lim_lo.shape[1]
    l_on = np.zeros((n_lim, nb), dtype=np.bool_)
    l_s = np.zeros((n_lim, nb))
    l_j = np.zeros((n_lim, 6, nb))
    l_k = np.zeros((n_lim, nb))
    l_min = np.zeros((n_lim, nb))
    l_lam = np.zeros((n_lim, nb))
    l_near = np.zeros((n_lim, nb), dtype=np.bool_)
    pose_index = np.full(nb, -1)
    pose = np.zeros(nb, dtype=np.int64)
    energy = np.zeros(nb)
    fallen = np.zeros(nb, dtype=np.bool_)
    abs_act = np.zeros(8)
    t = 0.0
    gh = g * h

    for _ in range(n_steps):
        # --- horloge, prendre / lâcher ---
        for b in range(nb):
            per = period[first + b]
            phase = (t % per) / per
            pz = min(int(phase * n_poses), n_poses - 1)
            pose[b] = pz
            if pz != pose_index[b]:
                for l in range(n_limbs):
                    p = limbs[l]
                    held[p, b] = holds[first + b, pz, l] and (not fallen[b]) and abs(px[p, b] - trunk_x) <= trunk_half
                pose_index[b] = pz
        # --- contrôleur PD ---
        for j in range(n_joints):
            a, pv, bb = joints[j, 0], joints[j, 1], joints[j, 2]
            for b in range(nb):
                ra0 = px[a, b] - px[pv, b]
                ra1 = py[a, b] - py[pv, b]
                rb0 = px[bb, b] - px[pv, b]
                rb1 = py[bb, b] - py[pv, b]
                theta[j, b] = math.atan2(ra0 * rb1 - ra1 * rb0, ra0 * rb0 + ra1 * rb1)
                va0 = vx[a, b] - vx[pv, b]
                va1 = vy[a, b] - vy[pv, b]
                vb0 = vx[bb, b] - vx[pv, b]
                vb1 = vy[bb, b] - vy[pv, b]
                wa = (ra0 * va1 - ra1 * va0) / (ra0 * ra0 + ra1 * ra1)
                wb = (rb0 * vb1 - rb1 * vb0) / (rb0 * rb0 + rb1 * rb1)
                theta_rate[j, b] = wb - wa
        for j in range(n_joints):
            sgn = joint_signs[j]
            for b in range(nb):
                c = first + b
                phi = _wrap(sgn * theta[j, b] - phi_rest[c, j])
                error = _wrap(targets[c, pose[b], j] - phi)
                u = kp * error - kd * (sgn * theta_rate[j, b])
                u = min(max(u, -s_minus[c, j]), s_plus[c, j])
                activation[j, b] = u
                torque[j, b] = sgn * u * torque_unit
        # --- Gravity(), Contract() ---
        for p in range(n_points):
            for b in range(nb):
                if not held[p, b]:
                    vy[p, b] -= gh
                fx[p, b] = 0.0
                fy[p, b] = 0.0
        for j in range(n_joints):
            a, pv, bb = joints[j, 0], joints[j, 1], joints[j, 2]
            for b in range(nb):
                ra0 = px[a, b] - px[pv, b]
                ra1 = py[a, b] - py[pv, b]
                rb0 = px[bb, b] - px[pv, b]
                rb1 = py[bb, b] - py[pv, b]
                den_a = ra0 * ra0 + ra1 * ra1
                den_b = rb0 * rb0 + rb1 * rb1
                tq = torque[j, b]
                fax[j, b] = -tq * -ra1 / den_a
                fay[j, b] = -tq * ra0 / den_a
                fbx[j, b] = tq * -rb1 / den_b
                fby[j, b] = tq * rb0 / den_b
        for j in range(n_joints):
            a = joints[j, 0]
            for b in range(nb):
                fx[a, b] += fax[j, b]
                fy[a, b] += fay[j, b]
        for j in range(n_joints):
            bb = joints[j, 2]
            for b in range(nb):
                fx[bb, b] += fbx[j, b]
                fy[bb, b] += fby[j, b]
        for j in range(n_joints):
            pv = joints[j, 1]
            for b in range(nb):
                fx[pv, b] += -(fax[j, b] + fbx[j, b])
                fy[pv, b] += -(fay[j, b] + fby[j, b])
        for p in range(n_points):
            for b in range(nb):
                if not held[p, b]:
                    vx[p, b] += fx[p, b] / m[p, b] * h
                    vy[p, b] += fy[p, b] / m[p, b] * h
                else:  # Hold()
                    vx[p, b] = 0.0
                    vy[p, b] = 0.0
                inv[p, b] = 0.0 if held[p, b] else 1.0 / m[p, b]
        # --- Link() + contacts (même calcul que physics._link_velocities_numba) ---
        for k in range(n_links):
            i, j2 = links[k, 0], links[k, 1]
            for b in range(nb):
                dx = px[j2, b] - px[i, b]
                dy = py[j2, b] - py[i, b]
                dist = math.sqrt(dx * dx + dy * dy)
                if inv[i, b] + inv[j2, b] == 0.0 or dist < 1e-12:
                    active[k, b] = False
                    continue
                active[k, b] = True
                nx[k, b] = dx / dist
                ny[k, b] = dy / dist
                bias[k, b] = beta * (dist - rst[k, b]) / h
        for p in range(n_points):
            for b in range(nb):
                gap = py[p, b] - ground_y
                lam_n[p, b] = 0.0
                lam_t[p, b] = 0.0
                if inv[p, b] > 0.0 and (gap < margin or gap + vy[p, b] * h < 0.0):
                    contact[p, b] = True
                    vn_min[p, b] = -gap / h if gap > 0.0 else -beta * gap / h
                else:
                    contact[p, b] = False
        for q in range(n_lim):  # butées : même calcul que physics._link_velocities_numba
            a, pv, bb = joints[q, 0], joints[q, 1], joints[q, 2]
            for b in range(nb):
                c = first + b
                cq, s, jax, jay, jbx, jby = _limit_geometry(px[a, b], py[a, b], px[pv, b], py[pv, b],
                                                            px[bb, b], py[bb, b], lim_sign[q], lim_lo[c, q],
                                                            lim_hi[c, q])
                kk, jpx, jpy = _limit_mass(inv[a, b], inv[bb, b], inv[pv, b], jax, jay, jbx, jby)
                rate = s * _limit_rate(jax, jay, jbx, jby, jpx, jpy, vx[a, b], vy[a, b], vx[bb, b], vy[bb, b],
                                       vx[pv, b], vy[pv, b])
                on = kk > 0.0 and (cq < lim_margin or cq + rate * h < 0.0)
                l_on[q, b] = on
                l_lam[q, b] = 0.0
                if on:
                    l_s[q, b] = s
                    l_j[q, 0, b] = jax
                    l_j[q, 1, b] = jay
                    l_j[q, 2, b] = jbx
                    l_j[q, 3, b] = jby
                    l_j[q, 4, b] = jpx
                    l_j[q, 5, b] = jpy
                    l_k[q, b] = kk
                    l_min[q, b] = -cq / h if cq > 0.0 else -beta * cq / h
        for _it in range(n_iter):
            for k in range(n_links):
                i, j2 = links[k, 0], links[k, 1]
                for b in range(nb):
                    if not active[k, b]:
                        continue
                    wi = inv[i, b]
                    wj = inv[j2, b]
                    vrel = (vx[j2, b] - vx[i, b]) * nx[k, b] + (vy[j2, b] - vy[i, b]) * ny[k, b]
                    lam = -(vrel + bias[k, b]) / (wi + wj)
                    vx[i, b] -= lam * wi * nx[k, b]
                    vy[i, b] -= lam * wi * ny[k, b]
                    vx[j2, b] += lam * wj * nx[k, b]
                    vy[j2, b] += lam * wj * ny[k, b]
            for q in range(n_lim):
                a, pv, bb = joints[q, 0], joints[q, 1], joints[q, 2]
                for b in range(nb):
                    if not l_on[q, b]:
                        continue
                    rate = l_s[q, b] * _limit_rate(l_j[q, 0, b], l_j[q, 1, b], l_j[q, 2, b], l_j[q, 3, b],
                                                   l_j[q, 4, b], l_j[q, 5, b], vx[a, b], vy[a, b], vx[bb, b],
                                                   vy[bb, b], vx[pv, b], vy[pv, b])
                    new = max(l_lam[q, b] + (l_min[q, b] - rate) / l_k[q, b], 0.0)
                    d = (new - l_lam[q, b]) * l_s[q, b]
                    l_lam[q, b] = new
                    wa = inv[a, b]
                    wb = inv[bb, b]
                    wp = inv[pv, b]
                    vx[a, b] += wa * l_j[q, 0, b] * d
                    vy[a, b] += wa * l_j[q, 1, b] * d
                    vx[bb, b] += wb * l_j[q, 2, b] * d
                    vy[bb, b] += wb * l_j[q, 3, b] * d
                    vx[pv, b] += wp * l_j[q, 4, b] * d
                    vy[pv, b] += wp * l_j[q, 5, b] * d
            for p in range(n_points):
                for b in range(nb):
                    if not contact[p, b]:
                        continue
                    new_n = max(lam_n[p, b] + vn_min[p, b] - vy[p, b], 0.0)
                    vy[p, b] += new_n - lam_n[p, b]
                    lam_n[p, b] = new_n
                    bound = friction * new_n
                    new_t = min(max(lam_t[p, b] - vx[p, b], -bound), bound)
                    vx[p, b] += new_t - lam_t[p, b]
                    lam_t[p, b] = new_t
        # --- Hold() + Movement() ---
        for p in range(n_points):
            for b in range(nb):
                if held[p, b]:
                    vx[p, b] = 0.0
                    vy[p, b] = 0.0
                px[p, b] += vx[p, b] * h
                py[p, b] += vy[p, b] * h
        # --- projection (même calcul que physics._project_links_numba) ---
        for q in range(n_lim):  # butées candidates : à moins de la marge au début de la projection
            a, pv, bb = joints[q, 0], joints[q, 1], joints[q, 2]
            for b in range(nb):
                c = first + b
                l_near[q, b] = _limit_geometry(px[a, b], py[a, b], px[pv, b], py[pv, b], px[bb, b], py[bb, b],
                                               lim_sign[q], lim_lo[c, q], lim_hi[c, q])[0] < lim_margin
        for _it in range(n_pos_iter):
            for k in range(n_links):
                i, j2 = links[k, 0], links[k, 1]
                for b in range(nb):
                    wi = inv[i, b]
                    wj = inv[j2, b]
                    if wi + wj == 0.0:
                        continue
                    dx = px[j2, b] - px[i, b]
                    dy = py[j2, b] - py[i, b]
                    dist = math.sqrt(dx * dx + dy * dy)
                    if dist < 1e-12:
                        continue
                    cc = (dist - rst[k, b]) / ((wi + wj) * dist)
                    px[i, b] += wi * cc * dx
                    py[i, b] += wi * cc * dy
                    px[j2, b] -= wj * cc * dx
                    py[j2, b] -= wj * cc * dy
            for q in range(n_lim):  # butées franchies (même calcul que physics._project_links_numba)
                a, pv, bb = joints[q, 0], joints[q, 1], joints[q, 2]
                for b in range(nb):
                    if not l_near[q, b]:
                        continue
                    c = first + b
                    cq, s, jax, jay, jbx, jby = _limit_geometry(px[a, b], py[a, b], px[pv, b], py[pv, b],
                                                                px[bb, b], py[bb, b], lim_sign[q], lim_lo[c, q],
                                                                lim_hi[c, q])
                    if cq >= 0.0:
                        continue
                    wa = inv[a, b]
                    wb = inv[bb, b]
                    wp = inv[pv, b]
                    kk, jpx, jpy = _limit_mass(wa, wb, wp, jax, jay, jbx, jby)
                    if kk == 0.0:
                        continue
                    mu = -cq / kk * s
                    px[a, b] += wa * jax * mu
                    py[a, b] += wa * jay * mu
                    px[bb, b] += wb * jbx * mu
                    py[bb, b] += wb * jby * mu
                    px[pv, b] += wp * jpx * mu
                    py[pv, b] += wp * jpy * mu
            for p in range(n_points):
                for b in range(nb):
                    if inv[p, b] > 0.0 and py[p, b] < ground_y:
                        py[p, b] = ground_y
        # --- énergie, chute ---
        for b in range(nb):
            for j in range(8):
                abs_act[j] = abs(activation[j, b])
            energy[b] += _pairwise_sum8(abs_act) * h
            if not fallen[b]:
                for p in range(n_body):
                    if py[p, b] <= ground_y + fall_eps:
                        fallen[b] = True
                        break
                if fallen[b] and fall_disables_hold:
                    for p in range(n_points):
                        held[p, b] = False
        t += h

    for b in range(nb):
        c = first + b
        for p in range(n_points):
            pos[c, p, 0] = px[p, b]
            pos[c, p, 1] = py[p, b]
            vel_out[c, p, 0] = vx[p, b]
            vel_out[c, p, 1] = vy[p, b]
        energy_out[c] = energy[b]
        fallen_out[c] = fallen[b]


@njit(parallel=True, cache=True, error_model="numpy")
def _simulate_population(pos, rest, mass, phi_rest, s_plus, s_minus, period, targets, holds, block,
                         links, joints, joint_signs, lim_sign, lim_lo, lim_hi, lim_margin, limbs, n_body, n_steps, h,
                         g, n_iter, beta, n_pos_iter, ground_y, friction, margin,
                         kp, kd, torque_unit, trunk_x, trunk_half, fall_eps, fall_disables_hold,
                         energy_out, fallen_out):
    n = pos.shape[0]
    vel = np.zeros_like(pos)
    n_blocks = (n + block - 1) // block
    for blk in prange(n_blocks):
        first = blk * block
        last = min(first + block, n)
        _simulate_block(pos, rest, mass, phi_rest, s_plus, s_minus, period, targets, holds, first, last,
                        links, joints, joint_signs, lim_sign, lim_lo, lim_hi, lim_margin, limbs, n_body, n_steps,
                        h, g, n_iter, beta, n_pos_iter,
                        ground_y, friction, margin, kp, kd, torque_unit, trunk_x, trunk_half, fall_eps,
                        fall_disables_hold, energy_out, fallen_out, vel)
    return vel


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

def evaluate(genomes, duration=10.0, packed=None):
    """Simule toute la population ; renvoie hauteur, énergie, masse musculaire, score, chute, positions finales."""
    if config.ENERGY_MODE != "torque":
        raise NotImplementedError("évaluateur batché écrit pour ENERGY_MODE = 'torque'")
    if config.DAMPING != 0.0:
        raise NotImplementedError("évaluateur batché écrit pour DAMPING = 0")
    arrays = pack(genomes) if packed is None else packed
    pos = arrays["pos"].copy()
    n = len(pos)
    h = config.DT / config.SUBSTEPS
    energy = np.zeros(n)
    fallen = np.zeros(n, dtype=np.bool_)
    vel = _simulate_population(
        pos, arrays["rest"], arrays["mass"], arrays["phi_rest"], arrays["s_plus"], arrays["s_minus"],
        arrays["period"], arrays["targets"], arrays["holds"], int(config.BATCH_BLOCK),
        arrays["links"], arrays["joints"],
        cr.JOINT_SIGNS, arrays["lim_sign"], arrays["lim_lo"], arrays["lim_hi"],
        float(math.radians(config.JOINT_LIMIT_MARGIN_DEG)),
        np.array(cr.LIMBS, dtype=np.int64), sk.TAIL_START, int(round(duration / h)), h,
        float(config.G), int(config.N_ITER), float(config.BETA), int(config.N_POS_ITER),
        float(config.GROUND_Y), float(config.GROUND_FRICTION), float(config.CONTACT_MARGIN),
        float(config.KP), float(config.KD), float(cr.torque_unit()), float(config.TRUNK_X),
        float(config.TRUNK_WIDTH / 2), float(config.FALL_CONTACT_EPS), bool(config.FALL_DISABLES_HOLD),
        energy, fallen)
    energy = config.ENERGY_SCALE * energy  # même opération que Creature.energy
    height = 0.5 * (pos[:, sk.NECK, 1] + pos[:, sk.PELVIS, 1]) - arrays["ref_y0"]
    muscle_mass = arrays["muscle_mass"]
    return {
        "height": height,
        "energy": energy,
        "muscle_mass": muscle_mass,
        "score": cr.fitness(height, energy, muscle_mass),
        "fallen": fallen,
        "pos": pos,
        "vel": vel,
    }


def benchmark(n=1000, seed=0, duration=10.0):
    """Temps d'évaluation d'une génération de n créatures aléatoires (compilation exclue)."""
    rng = np.random.default_rng(seed)
    genomes = [cr.random_genome(rng) for _ in range(n)]
    evaluate(genomes[:2], duration=0.1)  # chauffe : compilation / chargement du cache numba
    t0 = time.perf_counter()
    packed = pack(genomes)
    t1 = time.perf_counter()
    result = evaluate(genomes, duration=duration, packed=packed)
    t2 = time.perf_counter()
    return {"n": n, "threads": get_num_threads(), "pack_s": t1 - t0, "simulate_s": t2 - t1,
            "total_s": t2 - t0, "result": result}


__all__ = ["evaluate", "pack", "benchmark", "physics"]  # physics : pour HAVE_NUMBA
