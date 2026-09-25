"""Mesures de calibrage du moteur (phase 1) : stabilisation, pendule simple, vitesse.

`python main.py debug-physics --calibrate` affiche le tableau ; les chiffres retenus
sont recopiés dans config.py.
"""
import math
import time

import numpy as np

import config
from evo import physics
from evo import skeleton as sk

H = config.DT / config.SUBSTEPS

# Les 3 stratégies de stabilisation comparées (nom, BETA, N_POS_ITER).
STABILISATIONS = [
    ("BETA seul", 0.2, 0),
    ("projection seule", 0.0, 8),
    ("les deux", 0.2, 8),
    ("projection 12", 0.0, 12),
]


def energy(world):
    return world.kinetic_energy() + world.potential_energy()


# ---------------------------------------------------------------------------
# Pendule simple à 2 points
# ---------------------------------------------------------------------------

def simple_pendulum(length=1.0, theta0_deg=5.0):
    """Point fixé en (0, 0), second point lâché sans vitesse à theta0 de la verticale.

    Le lien est un os : sa masse est répartie moitié-moitié sur ses deux extrémités
    (§1.6), et la moitié du point fixé ne compte pas (masse infinie). C'est donc un
    pendule simple idéal : masse ponctuelle au bout d'une tige sans masse.
    """
    th = math.radians(theta0_deg)
    return physics.World([(0.0, 0.0), (length * math.sin(th), -length * math.cos(th))],
                         [(0, 1)], held=[True, False])


def pendulum_period_theory(length, theta0_deg, g=config.G, amplitude_correction=True):
    """T = 2π√(L/g), avec la correction d'amplitude 1 + θ0²/16 + 11θ0⁴/3072 si demandée."""
    t0 = 2 * math.pi * math.sqrt(length / g)
    if not amplitude_correction:
        return t0
    th = math.radians(theta0_deg)
    return t0 * (1 + th ** 2 / 16 + 11 * th ** 4 / 3072)


def measure_period(world, n_periods=10, substeps=None):
    """Période moyenne mesurée entre passages par la verticale (x = 0), interpolés linéairement."""
    substeps = config.SUBSTEPS if substeps is None else substeps
    h = config.DT / substeps
    crossings = []
    x_prev, t_prev = world.pos[1, 0], world.t
    while len(crossings) < 2 * n_periods + 1:
        physics.substep(world, h)
        x = world.pos[1, 0]
        if (x_prev > 0 >= x) or (x_prev < 0 <= x):
            crossings.append(t_prev + (world.t - t_prev) * x_prev / (x_prev - x))
        x_prev, t_prev = x, world.t
    return (crossings[-1] - crossings[0]) / n_periods


# ---------------------------------------------------------------------------
# Comparaison des stabilisations
# ---------------------------------------------------------------------------

def run_human_pendulum(beta, n_pos_iter, duration=10.0, anchor=sk.L_HAND, backend=None):
    """Banc 8 : erreurs de longueur max et bilan d'énergie sous-pas par sous-pas.

    injected = somme des hausses d'énergie mécanique d'un sous-pas au suivant,
    dissipated = somme des baisses. La gravité étant conservative, les deux sont
    purement numériques.
    """
    skel = sk.build_skeleton()
    world = skel.make_world(origin=-skel.pos[anchor])
    world.held[anchor] = True
    world.beta, world.n_pos_iter = beta, n_pos_iter
    if backend:
        world.backend = backend
    tail = np.array([n == "tail" for n in skel.link_names])
    e0 = e_prev = energy(world)
    stats = dict(body=0.0, tail=0.0, injected=0.0, dissipated=0.0, max_gain=0.0)
    for _ in range(int(round(duration / H))):
        physics.substep(world, H)
        e = energy(world)
        stats["injected"] += max(e - e_prev, 0.0)
        stats["dissipated"] += min(e - e_prev, 0.0)
        stats["max_gain"] = max(stats["max_gain"], e - e0)
        e_prev = e
        err = np.abs(world.link_lengths() - world.rest) / world.rest
        stats["body"] = max(stats["body"], float(err[~tail].max()))
        stats["tail"] = max(stats["tail"], float(err[tail].max()))
    stats["drift"] = e_prev - e0
    stats["finite"] = bool(np.isfinite(world.pos).all())
    return stats


def simple_pendulum_energy_drift(beta, n_pos_iter, theta0_deg=30.0, duration=20.0):
    """Dérive d'énergie relative (E − E0) / E_oscillation d'un pendule simple, système conservatif."""
    world = simple_pendulum(1.0, theta0_deg)
    world.beta, world.n_pos_iter = beta, n_pos_iter
    e0 = energy(world)
    e_bottom = world.mass[1] * world.g * -1.0
    for _ in range(int(round(duration / H))):
        physics.substep(world, H)
    return (energy(world) - e0) / (e0 - e_bottom)


def compare_stabilisations():
    rows = []
    for name, beta, n_pos in STABILISATIONS:
        stats = run_human_pendulum(beta, n_pos)
        stats["simple_drift"] = simple_pendulum_energy_drift(beta, n_pos)
        rows.append((name, beta, n_pos, stats))
    return rows


# ---------------------------------------------------------------------------
# Vitesse du banc 8
# ---------------------------------------------------------------------------

def time_per_frame(backend, frames=600):
    """Temps moyen (ms) d'une frame (DT, SUBSTEPS sous-pas) du pendule humain, compilation exclue."""
    skel = sk.build_skeleton()

    def fresh():
        world = skel.make_world(origin=-skel.pos[sk.L_HAND])
        world.held[sk.L_HAND] = True
        world.backend = backend
        return world

    physics.step(fresh())  # chauffe : compilation numba
    world = fresh()
    start = time.perf_counter()
    for _ in range(frames):
        physics.step(world)
    return (time.perf_counter() - start) / frames * 1000


def report():
    lines = ["Stabilisation (banc 8 : pendu par une main 10 s ; pendule simple 30° pendant 20 s)",
             f"{'config':<18}{'BETA':>5}{'proj':>5}{'corps %':>9}{'queue %':>9}{'E-E0 J':>9}"
             f"{'injecté J':>11}{'dissipé J':>11}{'simple ΔE/E':>13}"]
    for name, beta, n_pos, s in compare_stabilisations():
        lines.append(f"{name:<18}{beta:>5.1f}{n_pos:>5d}{s['body'] * 100:>9.3f}{s['tail'] * 100:>9.3f}"
                     f"{s['drift']:>9.3f}{s['injected']:>11.4f}{s['dissipated']:>11.3f}"
                     f"{s['simple_drift'] * 100:>12.2f}%")
    lines.append("")
    lines.append("Pendule simple, petites oscillations (5°), période mesurée / théorie")
    for length in (0.5, 1.0, 2.0):
        measured = measure_period(simple_pendulum(length, 5.0))
        bare = pendulum_period_theory(length, 5.0, amplitude_correction=False)
        corrected = pendulum_period_theory(length, 5.0)
        lines.append(f"L = {length:.1f} m   T = {measured:.6f} s   2π√(L/g) = {bare:.6f} s ({measured / bare - 1:+.4%})"
                     f"   avec correction d'amplitude {corrected:.6f} s ({measured / corrected - 1:+.5%})")
    lines.append("")
    backends = ["numba", "python"] if physics.HAVE_NUMBA else ["python"]
    timings = {b: time_per_frame(b) for b in backends}
    lines.append("Banc 8, temps de calcul d'une frame (1/60 s, 8 sous-pas ; temps réel = 16.7 ms)")
    for b, ms in timings.items():
        lines.append(f"{b:<8}{ms:8.3f} ms/frame   ({1000 / 60 / ms:.0f}× le temps réel)")
    return lines
