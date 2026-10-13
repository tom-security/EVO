"""Chantier D : report dissipatif de la projection (CLEAN_PROJECTION) et mains de leur côté de l'axe (HAND_LIMITS),
avec le cône de queue de C2 (TAIL_CONE_DEG).

Sur le modèle de tests/test_body_limits.py (C2). La queue tenue par sa courbure (TAIL_CURVATURE_LIMITS, candidat (d))
a été explorée puis écartée (docs/chantier_d.md) : son code reste derrière son drapeau (False), et ses tests de
disposition et d'égalité au bit près sont gardés en fin de fichier.
"""
import json
import math
import os

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
HANDS = slice(22, 24)
D_FLAGS = ("CLEAN_PROJECTION", "TAIL_CURVATURE_LIMITS", "HAND_LIMITS")
needs_numba = pytest.mark.skipif(not physics.HAVE_NUMBA, reason="numba non installé")


@pytest.fixture(autouse=True)
def d_on(monkeypatch):
    """Moteur du chantier D : butées articulaires et du corps, report dissipatif, mains ; pas de courbure."""
    for flag in ("JOINT_LIMITS", "BODY_LIMITS", "CLEAN_PROJECTION", "HAND_LIMITS"):
        monkeypatch.setattr(config, flag, True)
    monkeypatch.setattr(config, "TAIL_CURVATURE_LIMITS", False)


def _free_creature():
    """Vraie créature (masses, os, 24 butées), sans gravité ni sol, sans muscles : seules les contraintes agissent."""
    c = cr.Creature(cr.diagonal_gait_genome())
    c.world.g = 0.0
    c.world.ground_y = None
    return c


def _rotate(pos, points, center, degrees):
    a = math.radians(degrees)
    rot = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
    pos[points] = center + (pos[points] - center) @ rot.T


def _theta(pos, point):
    ra, rb = pos[sk.NECK] - pos[sk.PELVIS], pos[point] - pos[sk.PELVIS]
    return math.atan2(ra[0] * rb[1] - ra[1] * rb[0], ra @ rb)


def _cross(pos, pivot, points, end):
    """Fait passer `end` (pied ou main gauche) de l'autre côté de l'axe, en tournant le membre autour de `pivot`."""
    for degrees in range(5, 180, 5):
        trial = pos.copy()
        _rotate(trial, points, trial[pivot].copy(), -degrees)
        if _theta(trial, end) < -math.radians(5.0):
            pos[:] = trial
            return
    raise AssertionError("membre jamais passé de l'autre côté")


def _cross_left_foot(pos):
    _cross(pos, sk.L_HIP, [sk.L_KNEE, sk.L_FOOT], sk.L_FOOT)


def _cross_left_hand(pos):
    _cross(pos, sk.L_SHOULDER, [sk.L_ELBOW, sk.L_HAND], sk.L_HAND)


def test_layout_and_rest_pose():
    c = cr.Creature(cr.diagonal_gait_genome())
    w = c.world
    assert w.clean_projection is True
    assert len(w.limit_lo) == 24
    groups = cr.limit_groups(len(w.limit_lo))
    assert list(groups["pieds"]) == [8, 9] and list(groups["queue"]) == list(range(10, 22))
    assert list(groups["mains"]) == [22, 23]
    assert "mains" not in cr.limit_groups(22, hands=False)
    np.testing.assert_array_equal(w.limit_joints[:8], w.joints)
    # pieds, queue (cône de C2) et mains : triplets (NECK, PELVIS, X)
    np.testing.assert_array_equal(w.limit_joints[8:, :2], [[sk.NECK, sk.PELVIS]] * 16)
    np.testing.assert_array_equal(w.limit_joints[TAIL, 2], np.arange(sk.TAIL_START, sk.TAIL_START + 12))
    np.testing.assert_array_equal(w.limit_joints[HANDS, 2], [sk.L_HAND, sk.R_HAND])
    np.testing.assert_array_equal(w.limit_sign[HANDS], [1.0, -1.0])
    assert _theta(w.pos, sk.L_HAND) > 0 > _theta(w.pos, sk.R_HAND)               # main gauche à θ > 0
    # au repos, la queue est dans l'axe, au centre du cône ; les mains loin de l'axe
    np.testing.assert_allclose(w.limit_violation()[TAIL], math.radians(config.TAIL_CONE_DEG), atol=1e-9)
    assert np.all(w.limit_violation()[HANDS] > math.radians(10.0))


def _projection_world(vel):
    """Deux points liés, 2 mm sous le sol, avec la vitesse `vel` : la projection les remonte au sol."""
    w = physics.World([(0.0, -0.002), (1.0, -0.002)], links=[(0, 1)], vel=vel)
    w.ground_y = 0.0
    w.clean_projection = True
    return w


def test_projection_report_removes_the_speed_into_the_ground():
    w = _projection_world([(0.0, -2.0), (0.0, -2.0)])
    before, ke = w.pos.copy(), w.kinetic_energy()
    physics.project_links(w)
    alpha = physics.projection_velocity(w, before, H)
    assert alpha == 1.0                                        # −2B/A = 2·2 m/s·h / 2 mm > 1 : v += Δp/h en entier
    np.testing.assert_allclose(w.vel[:, 1], -2.0 + 0.002 / H)
    assert w.kinetic_energy() < ke


def test_projection_report_never_adds_kinetic_energy():
    w = _projection_world([(0.0, 3.0), (0.0, 3.0)])            # déjà en train de remonter : rien à retirer
    before = w.pos.copy()
    physics.project_links(w)
    assert physics.projection_velocity(w, before, H) == 0.0
    np.testing.assert_array_equal(w.vel[:, 1], [3.0, 3.0])
    rng = np.random.default_rng(3)
    alphas = []
    for _ in range(200):                                       # postures faussées, vitesses quelconques
        c = cr.Creature(cr.random_genome(rng))
        w = c.world
        w.pos += rng.normal(scale=0.05, size=w.pos.shape)
        w.vel = rng.normal(scale=2.0, size=w.pos.shape)
        w.held[sk.L_HAND] = True
        w.vel[sk.L_HAND] = 0.0
        before, ke = w.pos.copy(), w.kinetic_energy()
        physics.project_links(w)
        alpha = physics.projection_velocity(w, before, H)
        alphas.append(alpha)
        assert 0.0 <= alpha <= 1.0
        assert w.kinetic_energy() <= ke * (1 + 1e-12)
        assert np.all(w.vel[sk.L_HAND] == 0.0)                 # un point tenu n'est pas corrigé
    assert 0 < np.mean(np.array(alphas) > 0) < 1               # le report agit sur une partie des cas seulement


@needs_numba
def test_numba_matches_python_reference_with_the_24_limits_and_the_report():
    rng = np.random.default_rng(7)
    c = cr.Creature(cr.random_genome(rng))
    assert len(c.world.limit_lo) == 24
    for _ in range(20):                    # postures faussées, certaines au-delà des butées du corps
        pos = c.world.pos + rng.normal(scale=0.25, size=c.world.pos.shape)
        vel = rng.normal(scale=3.0, size=c.world.pos.shape)
        worlds, alphas = [], []
        for backend in ("numba", "python"):
            w = cr.Creature(c.genome).world
            w.pos, w.vel, w.backend = pos.copy(), vel.copy(), backend
            w.held[sk.R_FOOT] = True
            physics.link(w, H)
            physics.movement(w, H)
            before = w.pos.copy()
            physics.project_links(w)
            alphas.append(physics.projection_velocity(w, before, H))
            worlds.append(w)
        np.testing.assert_allclose(worlds[0].vel, worlds[1].vel, rtol=0, atol=1e-12)
        np.testing.assert_allclose(worlds[0].pos, worlds[1].pos, rtol=0, atol=1e-12)
        np.testing.assert_array_equal(worlds[0].limit_active, worlds[1].limit_active)
        assert alphas[0] == pytest.approx(alphas[1], abs=1e-12)


def _engaging_genomes():
    rng = np.random.default_rng(123)
    climber = [cr.random_genome(rng) for _ in range(36)][35]
    others = [cr.random_genome(np.random.default_rng(seed)) for seed in range(4)]
    return others + [climber, cr.diagonal_gait_genome()]


def _batch_matches_scalar(monkeypatch, n_limits):
    genomes = _engaging_genomes()
    arrays = batch.pack(genomes)
    assert arrays["lim_joints"].shape == (n_limits, 3) and arrays["clean_projection"] is True
    for k in (0, 2):                                           # pied gauche au-delà de l'axe au départ
        _cross_left_foot(arrays["pos"][k])
    for k in (1, 3):                                           # main gauche au-delà de l'axe au départ
        _cross_left_hand(arrays["pos"][k])
    reports = []
    original = physics.projection_velocity
    monkeypatch.setattr(physics, "projection_velocity", lambda *a: reports.append(original(*a)) or reports[-1])
    engaged = np.zeros(n_limits, dtype=int)
    scalar = []
    for k, g in enumerate(genomes):
        c = cr.Creature(g)
        c.world.pos[:] = arrays["pos"][k]
        for _ in range(int(round(10.0 / H))):
            c.substep(H)
            engaged += c.world.limit_active
        scalar.append(c)
    assert sum(a > 0.0 for a in reports) > 100                                    # le report a agi
    res = batch.evaluate(genomes, packed=arrays)
    for k, c in enumerate(scalar):
        np.testing.assert_array_equal(res["pos"][k], c.world.pos)
        np.testing.assert_array_equal(res["vel"][k], c.world.vel)
        assert res["energy"][k] == c.energy and res["height"][k] == c.height()
        assert bool(res["fallen"][k]) == c.fallen
    return engaged


@needs_numba
def test_batch_matches_scalar_bit_for_bit_with_the_chantier_d_engine(monkeypatch):
    engaged = _batch_matches_scalar(monkeypatch, 24)
    assert engaged[8] > 0 and engaged[22] > 0 and np.any(engaged[TAIL] > 0)     # pied, main, queue engagés


def _run(world, seconds, limits):
    energies, margins = [world.kinetic_energy()], []
    for _ in range(int(round(seconds / H))):
        physics.substep(world, H)
        energies.append(world.kinetic_energy())
        margins.append(world.limit_violation()[limits].min())
    return np.array(energies), np.array(margins)


@pytest.mark.parametrize("speed", [6.0, 10.0])
def test_free_hand_thrown_at_the_axis_stops_on_it(speed):
    c = _free_creature()
    c.world.vel[sk.L_HAND] = (speed, 0.0)                      # vers l'axe (la main gauche est à x < axe)
    energies, margins = _run(c.world, 1.0, [22])
    assert margins.min() >= -TOL                               # jamais au-delà de l'axe de plus de 0.5°
    assert np.any(margins < math.radians(0.01))                # la butée a bien servi
    assert np.all(np.diff(energies) <= 1e-9)                   # le choc ne crée pas d'énergie
    assert c.world.length_error() < 1e-4


@pytest.mark.parametrize("speed", [2.0, 5.0, 10.0])
def test_tail_thrown_against_the_cone_stops_without_energy_gain(speed):
    c = _free_creature()
    w = c.world
    w.vel[sk.TAIL_START:] = (speed, 0.0)
    energies, margins = _run(w, 1.0, TAIL)
    assert margins.min() >= -TOL                               # aucun point de queue hors du cône de plus de 0.5°
    assert np.any(margins < math.radians(0.01))                # le cône a servi
    assert np.all(np.diff(energies) <= 1e-9)
    tail = np.array([name == "tail" for name in c.skel.link_names])
    err = np.abs(w.link_lengths() - w.rest) / w.rest
    assert err[tail].max() < 0.01                              # os de la queue < 1 %


def test_start_beyond_the_limits_recovers_by_the_short_side():
    c = cr.Creature(cr.diagonal_gait_genome())
    P = c.world.pos
    bent = config.TAIL_CONE_DEG + 34.0                         # queue pliée 34° au-delà du cône
    _rotate(P, list(range(sk.TAIL_START, len(P))), P[sk.PELVIS].copy(), bent)
    _cross_left_foot(P)
    _cross_left_hand(P)
    v = c.world.limit_violation()
    assert v[TAIL].min() < -math.radians(30.0) and v[8] < 0 and v[22] < 0
    for k in range(int(round(2.0 / H))):
        c.substep(H)
        assert np.all(np.isfinite(c.world.pos)) and np.all(np.isfinite(c.world.vel))
        if k >= 60:                                                                # 1/8 s plus tard : revenu
            assert c.world.limit_violation()[8:].min() >= -TOL
    assert np.hypot(*c.world.vel[c.body_points].T).max() < config.AUDIT_MAX_SPEED


@pytest.mark.parametrize("name", ["grimpeuse aléatoire", "marche écrite à la main", "inerte"])
def test_no_energy_created_by_the_report_and_the_hands(name):
    genome = {"grimpeuse aléatoire": lambda: _engaging_genomes()[4], "marche écrite à la main": cr.diagonal_gait_genome,
              "inerte": cr.limp_genome}[name]()
    c, ledger = audit.audit(genome)
    weight = c.world.mass.sum() * config.G
    assert ledger["liens_contacts+"] < 1e-9                    # liens + butées + sol : dissipatifs
    assert ledger["report_projection+"] < 1e-9                 # le report ne fait que retirer (arrondis : 1e-12)
    assert ledger["saut_engagement_max"] / weight < config.AUDIT_MAX_LIMIT_JUMP
    # seuils de tests/test_creature.py, inchangés (PASSATION §10) : 0,23 J ; créature inerte avec les butées du
    # corps : 6 J
    limit = 6.0 if name == "inerte" else 1e-4 * weight * config.START_HEIGHT
    assert ledger["hors_muscles+"] < limit
    if name != "inerte":
        c = cr.Creature(genome)
        worst = np.inf
        for _ in range(int(round(10.0 / H))):
            c.substep(H)
            worst = min(worst, c.world.limit_violation().min())
        assert worst >= -TOL                                   # les 24 butées tenues à 0.5° près tout du long


RUN_CASES = [  # créatures du diagnostic (docs/chantier_d_diagnostic.md) : génomes des runs de la v1, moteur D
    ("B2 n°868, couchée", ("butees_articulaires", "2"), 0, 868),
    ("B2 n°760, couchée", ("butees_articulaires", "1"), 200, 760),
    ("C2 n°808, sorties de cône", ("1",), 200, 808),
    ("C2 n°677, queue étirée", ("0",), 200, 677),
]


@pytest.mark.parametrize("name, run, gen, index", RUN_CASES, ids=[c[0] for c in RUN_CASES])
def test_energy_non_regression_on_the_diagnostic_creatures(name, run, gen, index):
    """Runs locaux (hors git, test ignoré s'ils manquent). Moteur de la v1 : 1 292,5 J et 825,2 J créés (couchées),
    queue étirée à 43,8 % (n°677), 16 sorties de cône (n°808), 0 J pour ces deux-là. Le génome est rejoué avec le moteur
    du chantier D (la config du run n'est pas appliquée)."""
    run_dir = os.path.join(config.RUNS_DIR, *run)
    if not os.path.exists(os.path.join(run_dir, "config.json")):
        pytest.skip("pas de runs locaux")
    pop, _, _, _ = ev.load_generation(run_dir, gen)
    c, ledger = audit.audit(pop.genome(index))
    weight = c.world.mass.sum() * config.G
    assert ledger["hors_muscles+"] < 1e-4 * weight * config.START_HEIGHT       # 0,23 J
    assert ledger["max_tail_error"] < config.AUDIT_MAX_TAIL_ERROR                # queue < 5 %
    assert ledger["liens_contacts+"] < 1e-9 and ledger["report_projection+"] < 1e-9


def test_flags_off_give_the_c2_engine(monkeypatch):
    for flag in D_FLAGS:
        monkeypatch.setattr(config, flag, False)
    c = cr.Creature(cr.diagonal_gait_genome())
    assert c.world.clean_projection is False and len(c.world.limit_lo) == 22
    np.testing.assert_array_equal(c.world.limit_joints[10:, :2], [[sk.NECK, sk.PELVIS]] * 12)   # cône de C2
    arrays = batch.pack([cr.diagonal_gait_genome()])
    assert arrays["clean_projection"] is False and arrays["lim_joints"].shape == (22, 3)
    monkeypatch.setattr(config, "BODY_LIMITS", False)          # sans butées du corps, ni mains ni courbure
    monkeypatch.setattr(config, "TAIL_CURVATURE_LIMITS", True)
    monkeypatch.setattr(config, "HAND_LIMITS", True)
    assert len(cr.Creature(cr.diagonal_gait_genome()).world.limit_lo) == 8


def test_run_without_the_keys_replays_without_the_chantier_d(tmp_path):
    (tmp_path / "config.json").write_text(json.dumps({"G": config.G, "JOINT_LIMITS": True, "BODY_LIMITS": True}))
    ev.use_run_config(str(tmp_path))
    assert config.BODY_LIMITS is True                          # run de C2
    assert not (config.CLEAN_PROJECTION or config.TAIL_CURVATURE_LIMITS or config.HAND_LIMITS)


def test_new_run_records_the_chantier_d_flags(tmp_path):
    run = str(tmp_path / "0")
    ev.train(0, generations=1, pop_size=12, run_dir=run, audit_every=0, log=lambda *_: None)
    with open(f"{run}/config.json") as fh:
        saved = json.load(fh)
    assert saved["CLEAN_PROJECTION"] is True and saved["HAND_LIMITS"] is True
    assert saved["TAIL_CURVATURE_LIMITS"] is False and saved["TAIL_CONE_DEG"] == config.TAIL_CONE_DEG


# --- Candidat (d), queue tenue par sa courbure : exploré puis écarté, code gardé derrière son drapeau ---------------

@pytest.fixture
def curvature_on(monkeypatch):
    monkeypatch.setattr(config, "TAIL_CURVATURE_LIMITS", True)


def test_curvature_layout(curvature_on):
    w = cr.Creature(cr.diagonal_gait_genome()).world
    t = sk.TAIL_START
    np.testing.assert_array_equal(w.limit_joints[10], (sk.NECK, sk.PELVIS, t))   # cône du premier segment
    np.testing.assert_array_equal(w.limit_joints[11], (sk.PELVIS, t, t + 1))     # puis courbure à chaque jonction
    np.testing.assert_array_equal(w.limit_joints[21], (t + 9, t + 10, t + 11))
    np.testing.assert_allclose(w.limit_violation()[TAIL], math.radians(config.TAIL_CURVATURE_DEG), atol=1e-9)


@needs_numba
def test_curvature_batch_matches_scalar_bit_for_bit(curvature_on, monkeypatch):
    engaged = _batch_matches_scalar(monkeypatch, 24)
    assert np.all(engaged[TAIL] > 100)
