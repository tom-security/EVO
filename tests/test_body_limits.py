"""Chantier C, phase C2 : butées du corps (pied de son côté de l'axe bassin–cou, queue dans un cône).

Même primitive que les butées articulaires de B2 (tests/test_joint_limits.py), sur les triplets (NECK, PELVIS, X).
"""
import json
import math

import numpy as np
import pytest

import config
from evo import audit
from evo import batch
from evo import creature as cr
from evo import evolution as ev
from evo import physics
from evo import skeleton as sk

H = config.DT / config.SUBSTEPS
TOL = math.radians(0.5)                              # pénétration tolérée (critère B2)
FEET = slice(8, 10)
TAIL = slice(10, 22)
needs_numba = pytest.mark.skipif(not physics.HAVE_NUMBA, reason="numba non installé")


@pytest.fixture(autouse=True)
def limits_on(monkeypatch):
    monkeypatch.setattr(config, "JOINT_LIMITS", True)
    monkeypatch.setattr(config, "BODY_LIMITS", True)


def _free_creature():
    """Vraie créature (masses, os, 22 butées), sans gravité ni sol, sans muscles : seules les contraintes agissent."""
    c = cr.Creature(cr.diagonal_gait_genome())
    c.world.g = 0.0
    c.world.ground_y = None
    return c


def _run(world, seconds, limits):
    """Sous-pas du moteur seul ; renvoie (énergies cinétiques, C minimal des butées `limits` à chaque sous-pas)."""
    energies, margins = [world.kinetic_energy()], []
    for _ in range(int(round(seconds / H))):
        physics.substep(world, H)
        energies.append(world.kinetic_energy())
        margins.append(world.limit_violation()[limits].min())
    return np.array(energies), np.array(margins)


def _rotate(pos, points, center, degrees):
    a = math.radians(degrees)
    rot = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
    pos[points] = center + (pos[points] - center) @ rot.T


def _theta(pos, point):
    ra, rb = pos[sk.NECK] - pos[sk.PELVIS], pos[point] - pos[sk.PELVIS]
    return math.atan2(ra[0] * rb[1] - ra[1] * rb[0], ra @ rb)


def _cross_left_foot(pos):
    """Fait passer le pied gauche de l'autre côté de l'axe, en tournant la jambe autour de la hanche (os intacts)."""
    for degrees in range(5, 180, 5):
        trial = pos.copy()
        _rotate(trial, [sk.L_KNEE, sk.L_FOOT], trial[sk.L_HIP].copy(), -degrees)
        if _theta(trial, sk.L_FOOT) < -math.radians(5.0):
            pos[:] = trial
            return
    raise AssertionError("pied gauche jamais passé de l'autre côté")


def test_body_limits_layout_and_rest_pose():
    c = cr.Creature(cr.diagonal_gait_genome())
    w = c.world
    assert len(w.limit_lo) == 22
    groups = cr.limit_groups(len(w.limit_lo))
    assert list(groups["pieds"]) == [8, 9] and list(groups["queue"]) == list(range(10, 22))
    np.testing.assert_array_equal(w.limit_joints[:8], w.joints)                    # muscles et butées B2
    np.testing.assert_array_equal(w.limit_joints[8:, :2], [[sk.NECK, sk.PELVIS]] * 14)
    assert _theta(w.pos, sk.L_FOOT) > 0 > _theta(w.pos, sk.R_FOOT)                 # pied gauche à θ > 0
    # au repos, la queue est dans l'axe, au centre du cône ; les pieds loin de l'axe
    np.testing.assert_allclose(w.limit_violation()[TAIL], math.radians(config.TAIL_CONE_DEG), atol=1e-9)
    assert np.all(w.limit_violation()[FEET] > math.radians(20.0))


@pytest.mark.parametrize("speed", [3.0, 6.0])
def test_free_foot_thrown_at_the_axis_stops_on_it(speed):
    c = _free_creature()
    c.world.vel[sk.L_FOOT] = (speed, 0.0)                      # vers l'axe (le pied gauche est à x < axe)
    energies, margins = _run(c.world, 1.0, [8])
    assert margins.min() >= -TOL                               # jamais au-delà de l'axe de plus de 0.5°
    assert np.any(margins < math.radians(0.01))                # la butée a bien servi
    assert np.all(np.diff(energies) <= 1e-9)                   # le choc ne crée pas d'énergie
    assert c.world.length_error() < 1e-4


def test_held_foot_stops_the_body_crossing_over_it():
    c = _free_creature()
    w = c.world
    w.held[sk.L_FOOT] = True
    w.vel[:] = (-4.0, 0.0)                                     # tout le corps file vers le pied gauche, tenu
    w.vel[sk.L_FOOT] = 0.0
    energies, margins = _run(w, 1.0, [8])
    assert margins.min() >= -TOL
    assert np.any(margins < math.radians(0.01))
    assert np.all(np.diff(energies) <= 1e-9)
    assert w.length_error() < 1e-3


@pytest.mark.parametrize("speed", [2.0, 5.0, 10.0])
def test_tail_thrown_against_the_cone_stops_without_bounce_or_energy_gain(speed):
    c = _free_creature()
    w = c.world
    w.vel[sk.TAIL_START:] = (speed, 0.0)
    energies, C = [w.kinetic_energy()], [w.limit_violation()[TAIL]]   # marge de chaque butée de queue
    for _ in range(int(round(1.0 / H))):
        physics.substep(w, H)
        energies.append(w.kinetic_energy())
        C.append(w.limit_violation()[TAIL])
    C = np.array(C)
    assert C.min() >= -TOL                                     # aucun point de queue hors du cône de plus de 0.5°
    # première butée de queue à toucher le bord, suivie seule (le minimum sur la chaîne saute d'un point à l'autre) ;
    # un contact arrive pile sur la borne (terme spéculatif : C ≈ 1e-12), un point qui l'effleure seulement non
    hit, q = np.unravel_index(np.argmax(C < 1e-8), C.shape)
    assert C[hit, q] < 1e-8 and hit >= 1                       # la queue arrive sur le bord du cône
    approach = C[max(hit - 2, 0), q] - C[hit - 1, q]           # vitesse d'approche juste avant (rad par sous-pas)
    assert approach > 0
    # pas de rebond : le point ne repart pas du bord (départ < 5 % de l'approche), ou n'en sort pas de plus de 0.5°
    # pendant 0.05 s ; un rebond ferait les deux. Cône étroit : la chaîne lancée vite écarte un peu le point de la
    # borne en le gardant contre elle ; cône large : elle s'en éloigne ensuite en douceur.
    assert C[hit + 1, q] - C[hit, q] < 0.05 * approach or C[hit:hit + 24, q].max() < math.radians(0.5)
    assert np.all(np.diff(energies) <= 1e-9)
    tail = np.array([name == "tail" for name in c.skel.link_names])
    err = np.abs(w.link_lengths() - w.rest) / w.rest
    assert err[tail].max() < 0.01                              # os de la queue < 1 %


def test_start_beyond_the_body_limits_recovers_by_the_short_side():
    c = cr.Creature(cr.diagonal_gait_genome())
    P = c.world.pos
    bent = config.TAIL_CONE_DEG + 34.0                         # queue pliée 34° au-delà du cône (40° pour 6°)
    _rotate(P, list(range(sk.TAIL_START, len(P))), P[sk.PELVIS].copy(), bent)
    _cross_left_foot(P)                                                            # pied de l'autre côté
    assert c.world.limit_violation()[TAIL].min() < -math.radians(30.0)
    assert c.world.limit_violation()[8] < 0
    swing = []
    for k in range(int(round(2.0 / H))):
        c.substep(H)
        assert np.all(np.isfinite(c.world.pos)) and np.all(np.isfinite(c.world.vel))
        tip = c.world.pos[-1] - c.world.pos[sk.PELVIS]
        axis = c.world.pos[sk.PELVIS] - c.world.pos[sk.NECK]
        swing.append(math.atan2(axis[0] * tip[1] - axis[1] * tip[0], axis @ tip))
        if k >= 60:                                                                # 1/8 s plus tard : revenu
            assert c.world.limit_violation()[8:].min() >= -TOL
    swing = np.degrees(np.unwrap(swing))
    assert np.abs(swing).max() < bent + 5.0                    # revenue par le côté court, sans tour
    assert np.hypot(*c.world.vel[c.body_points].T).max() < config.AUDIT_MAX_SPEED


def _engaging_genomes():
    rng = np.random.default_rng(123)
    climber = [cr.random_genome(rng) for _ in range(36)][35]
    others = [cr.random_genome(np.random.default_rng(seed)) for seed in range(4)]
    return others + [climber, cr.diagonal_gait_genome()]


@needs_numba
def test_batch_matches_scalar_bit_for_bit_with_body_limits_engaged():
    genomes = _engaging_genomes()
    arrays = batch.pack(genomes)
    assert arrays["lim_joints"].shape == (22, 3)
    for k in (0, 2, 4):                                        # trois créatures partent le pied gauche au-delà de l'axe
        _cross_left_foot(arrays["pos"][k])
    engaged = np.zeros(22, dtype=int)
    scalar = []
    for k, g in enumerate(genomes):
        c = cr.Creature(g)
        c.world.pos[:] = arrays["pos"][k]
        for _ in range(int(round(10.0 / H))):
            c.substep(H)
            engaged += c.world.limit_active
        scalar.append(c)
    assert engaged[8] > 0 and np.all(engaged[TAIL] > 100)      # pied et queue réellement engagés
    res = batch.evaluate(genomes, packed=arrays)
    for k, c in enumerate(scalar):
        np.testing.assert_array_equal(res["pos"][k], c.world.pos)
        np.testing.assert_array_equal(res["vel"][k], c.world.vel)
        assert res["energy"][k] == c.energy and res["height"][k] == c.height()
        assert bool(res["fallen"][k]) == c.fallen


@needs_numba
def test_numba_matches_python_reference_with_the_22_limits():
    rng = np.random.default_rng(7)
    c = cr.Creature(cr.random_genome(rng))
    assert len(c.world.limit_lo) == 22
    for _ in range(20):                    # postures faussées, certaines au-delà des butées du corps
        pos = c.world.pos + rng.normal(scale=0.25, size=c.world.pos.shape)
        vel = rng.normal(scale=3.0, size=c.world.pos.shape)
        worlds = []
        for backend in ("numba", "python"):
            w = cr.Creature(c.genome).world
            w.pos, w.vel, w.backend = pos.copy(), vel.copy(), backend
            w.held[sk.R_FOOT] = True
            physics.link(w, H)
            physics.project_links(w)
            worlds.append(w)
        np.testing.assert_allclose(worlds[0].vel, worlds[1].vel, rtol=0, atol=1e-12)
        np.testing.assert_allclose(worlds[0].pos, worlds[1].pos, rtol=0, atol=1e-12)
        np.testing.assert_array_equal(worlds[0].limit_active, worlds[1].limit_active)


@pytest.mark.parametrize("name", ["grimpeuse aléatoire", "marche écrite à la main"])
def test_body_limits_create_no_energy_on_a_climb(name):
    genome = {"grimpeuse aléatoire": lambda: _engaging_genomes()[4],
              "marche écrite à la main": cr.diagonal_gait_genome}[name]()
    c, ledger = audit.audit(genome)
    weight = c.world.mass.sum() * config.G
    assert ledger["liens_contacts+"] < 1e-9                    # liens + butées + sol : dissipatifs
    assert ledger["hors_muscles+"] < 1e-4 * weight * config.START_HEIGHT
    assert ledger["saut_engagement_max"] / weight < config.AUDIT_MAX_LIMIT_JUMP
    c = cr.Creature(genome)
    worst = np.inf
    for _ in range(int(round(10.0 / H))):
        c.substep(H)
        worst = min(worst, c.world.limit_violation().min())
    assert worst >= -TOL                                       # les 22 butées tenues à 0.5° près tout du long


def test_flag_off_keeps_only_the_joint_limits(monkeypatch):
    monkeypatch.setattr(config, "BODY_LIMITS", False)
    c = cr.Creature(cr.diagonal_gait_genome())
    np.testing.assert_array_equal(c.world.limit_joints, c.world.joints)
    assert batch.pack([cr.diagonal_gait_genome()])["lim_joints"].shape == (8, 3)
    monkeypatch.setattr(config, "JOINT_LIMITS", False)        # sans butées articulaires, pas de butées du corps
    assert len(cr.Creature(cr.diagonal_gait_genome()).world.limit_lo) == 0


def test_run_without_the_key_replays_without_body_limits(tmp_path):
    (tmp_path / "config.json").write_text(json.dumps({"G": config.G, "JOINT_LIMITS": True}))
    ev.use_run_config(str(tmp_path))
    assert config.JOINT_LIMITS is True and config.BODY_LIMITS is False      # run de B2 : butées articulaires seules


def test_new_run_records_the_body_limits(tmp_path):
    run = str(tmp_path / "0")
    ev.train(0, generations=1, pop_size=12, run_dir=run, audit_every=0, log=lambda *_: None)
    with open(f"{run}/config.json") as fh:
        saved = json.load(fh)
    assert saved["BODY_LIMITS"] is True and saved["TAIL_CONE_DEG"] == config.TAIL_CONE_DEG
