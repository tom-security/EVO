"""Chantier D, diagnostic (lecture seule) : noyaux du solveur avec un sens de parcours alterné des butées de queue.

Copies de physics._link_velocities_numba et physics._project_links_numba, mêmes signatures, mêmes opérations, à une
différence près : le bloc des butées de queue (indices ≥ TAIL_FROM, quand le monde a les 22 butées des articulations,
des pieds et de la queue) est parcouru de la racine vers le bout aux passes paires, du bout vers la racine aux passes
impaires. Les autres butées, les liens et le sol gardent leur ordre. Substituées le temps d'une mesure par
evo/diag_projection.py (« …:alterne ») ; le moteur du dépôt n'est pas modifié.
"""
import math

import numpy as np

from evo.physics import _limit_geometry, _limit_mass, _limit_rate, njit

TAIL_FROM = 10      # 8 articulations + 2 pieds : les butées de queue suivent (creature.limit_groups)


@njit(cache=True)
def _order(q, n_lim, pass_index):
    """Indice de la q-ième butée visitée pendant la passe `pass_index`."""
    if n_lim <= TAIL_FROM or q < TAIL_FROM or pass_index % 2 == 0:
        return q
    return TAIL_FROM + (n_lim - 1 - q)


@njit(cache=True)
def link_velocities_alterne(pos, vel, inv_mass, links, rest, h, n_iter, beta,
                            ground, ground_y, friction, margin,
                            lim_joints, lim_sign, lim_lo, lim_hi, lim_margin, lim_active):
    n_links = links.shape[0]
    n_points = pos.shape[0]
    nx = np.zeros(n_links)
    ny = np.zeros(n_links)
    bias = np.zeros(n_links)
    active = np.zeros(n_links, dtype=np.bool_)
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
    n_lim = lim_lo.shape[0]
    l_on = np.zeros(n_lim, dtype=np.bool_)
    l_s = np.zeros(n_lim)
    l_j = np.zeros((n_lim, 6))
    l_k = np.zeros(n_lim)
    l_min = np.zeros(n_lim)
    l_lam = np.zeros(n_lim)
    for q in range(n_lim):
        a, p, b = lim_joints[q, 0], lim_joints[q, 1], lim_joints[q, 2]
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
    for it in range(n_iter):
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
        for qq in range(n_lim):
            q = _order(qq, n_lim, it)
            if not l_on[q]:
                continue
            a, p, b = lim_joints[q, 0], lim_joints[q, 1], lim_joints[q, 2]
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
                new_n = max(lam_n[p] + vn_min[p] - vel[p, 1], 0.0)
                vel[p, 1] += new_n - lam_n[p]
                lam_n[p] = new_n
                bound = friction * new_n
                new_t = min(max(lam_t[p] - vel[p, 0], -bound), bound)
                vel[p, 0] += new_t - lam_t[p]
                lam_t[p] = new_t


@njit(cache=True)
def project_links_alterne(pos, inv_mass, links, rest, n_pos_iter, ground, ground_y,
                          lim_joints, lim_sign, lim_lo, lim_hi, lim_margin):
    n_lim = lim_lo.shape[0]
    near = np.zeros(n_lim, dtype=np.bool_)
    for q in range(n_lim):
        a, p, b = lim_joints[q, 0], lim_joints[q, 1], lim_joints[q, 2]
        near[q] = _limit_geometry(pos[a, 0], pos[a, 1], pos[p, 0], pos[p, 1], pos[b, 0], pos[b, 1],
                                  lim_sign[q], lim_lo[q], lim_hi[q])[0] < lim_margin
    for it in range(n_pos_iter):
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
        for qq in range(n_lim):
            q = _order(qq, n_lim, it)
            if not near[q]:
                continue
            a, p, b = lim_joints[q, 0], lim_joints[q, 1], lim_joints[q, 2]
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
