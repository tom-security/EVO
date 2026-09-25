"""Chantier B, phase B2 : butées articulaires dans le moteur (contrainte à sens unique sur l'angle)."""
import json
import math

import numpy as np
import pytest

import config
from evo import audit
from evo import batch
from evo import creature as cr
from evo import evolution as ev
from evo import joint_audit as ja
from evo import physics
from evo import skeleton as sk

H = config.DT / config.SUBSTEPS
LO, HI = math.radians(-120.0), math.radians(-60.0)   # butées du banc à 3 points, en θ (repos : −90°)
TOL = math.radians(0.5)                              # pénétration tolérée (critère B2)
needs_numba = pytest.mark.skipif(not physics.HAVE_NUMBA, reason="numba non installé")


@pytest.fixture(autouse=True)
def limits_on(monkeypatch):
    monkeypatch.setattr(config, "JOINT_LIMITS", True)


def _hinge(held_end="A"):
    """A (0, 1) — pivot P (0, 0) — B (1, 0) : θ = −90°, butées [−120°, −60°], sans gravité ni sol.
    held_end "A" : A et P tenus, B libre (le membre tourne autour du pivot) ; "B" : seule l'extrémité B tenue."""
    world = physics.World([(0.0, 1.0), (0.0, 0.0), (1.0, 0.0)], links=[(0, 1), (1, 2)], joints=[(0, 1, 2)])
    world.g = 0.0
    if held_end == "A":
        world.held[[0, 1]] = True
    else:
        world.held[2] = True
    world.set_joint_limits([1.0], [LO], [HI])
    return world


def _theta(world):
    return float(world.joint_angles()[0])


@pytest.mark.parametrize("direction", [+1.0, -1.0])
def test_joint_pushed_against_its_limit_stops_on_it(direction):
    world = _hinge()
    bound = HI if direction > 0 else LO                 # τ > 0 ouvre l'angle signé A→B (vers HI)
    world.torque = np.array([direction * 0.5])
    thetas = []
    for _ in range(int(round(2.0 / H))):
        physics.substep(world, H)
        thetas.append(_theta(world))
    thetas = np.array(thetas)
    beyond = (thetas - HI) if direction > 0 else (LO - thetas)
    assert beyond.max() <= TOL                                          # jamais au-delà de 0.5°
    assert abs(thetas[-1] - bound) < math.radians(0.05)                 # arrêtée pile sur la butée
    assert abs(float(world.joint_velocities()[0])) < 1e-6               # et immobile
    reached = int(np.argmax(np.abs(thetas - bound) < math.radians(0.1)))
    assert np.all(np.abs(thetas[reached:] - bound) < math.radians(0.1))  # sans rebond


@pytest.mark.parametrize("held_end", ["A", "B"])
@pytest.mark.parametrize("direction", [+1.0, -1.0])
def test_limb_thrown_against_its_limit_stops_without_bounce_or_energy_gain(direction, held_end):
    world = _hinge(held_end)
    moving = 2 if held_end == "A" else 0               # B tourne autour de P, ou A (et P) autour de B
    r = world.pos[moving] - world.pos[1]
    spin = direction if held_end == "A" else -direction  # A qui tourne dans un sens = θ dans l'autre
    world.vel[moving] = 3.0 * spin * np.array([-r[1], r[0]])   # vitesse tangentielle : θ va vers la butée
    bound = HI if direction > 0 else LO
    approach = float(world.joint_velocities()[0])
    energies, thetas, rates = [world.kinetic_energy()], [], []
    for _ in range(int(round(1.0 / H))):
        physics.substep(world, H)
        energies.append(world.kinetic_energy())
        thetas.append(_theta(world))
        rates.append(float(world.joint_velocities()[0]))
    thetas = np.array(thetas)
    assert np.all(np.diff(energies) <= 1e-9)                            # le choc ne crée pas d'énergie
    beyond = (thetas - HI) if direction > 0 else (LO - thetas)
    assert beyond.max() <= TOL
    hit = int(np.argmax(np.abs(thetas - bound) < math.radians(0.01)))    # arrivée pile sur la butée
    assert abs(thetas[hit] - bound) < math.radians(0.01)
    assert abs(rates[hit + 1]) < 0.01 * abs(approach)                   # choc inélastique : pas de rebond
    if held_end == "A":   # un seul degré de liberté : le membre reste sur la butée, immobile
        assert np.all(np.abs(thetas[hit:] - bound) < math.radians(0.01)) and energies[-1] < 1e-12
    # (extrémité tenue : la chaîne peut ensuite se rouvrir librement, la butée est à sens unique)
    assert world.length_error() < 1e-6


def _test_genomes():
    rng = np.random.default_rng(123)
    climber = [cr.random_genome(rng) for _ in range(36)][35]
    others = [cr.random_genome(np.random.default_rng(seed)) for seed in range(8)]
    return others + [climber, cr.diagonal_gait_genome(), cr.limp_genome()]


@needs_numba
def test_batch_matches_scalar_bit_for_bit_with_limits_engaged():
    genomes = _test_genomes()
    engaged = np.zeros(8, dtype=int)
    scalar = []
    for g in genomes:
        c = cr.Creature(g)
        for _ in range(int(round(10.0 / H))):
            c.substep(H)
            engaged += c.world.limit_active
        scalar.append(c)
    assert np.all(engaged > 100)          # chacune des 8 butées est entrée dans le solveur, souvent
    res = batch.evaluate(genomes)
    for k, c in enumerate(scalar):
        np.testing.assert_array_equal(res["pos"][k], c.world.pos)
        np.testing.assert_array_equal(res["vel"][k], c.world.vel)
        assert res["energy"][k] == c.energy and res["height"][k] == c.height()
        assert bool(res["fallen"][k]) == c.fallen


@needs_numba
def test_numba_matches_python_reference_with_limits():
    rng = np.random.default_rng(4)
    c = cr.Creature(cr.random_genome(rng))
    for _ in range(20):                    # un appel : postures faussées, certaines au-delà des butées
        pos = c.world.pos + rng.normal(scale=0.15, size=c.world.pos.shape)
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
    runs = []
    for backend in ("numba", "python"):    # une seconde de grimpe
        c = cr.Creature(_test_genomes()[8])
        c.world.backend = backend
        for _ in range(int(round(1.0 / H))):
            c.substep(H)
        runs.append(c.world)
    np.testing.assert_allclose(runs[0].pos, runs[1].pos, rtol=0, atol=1e-9)


def _rotate(pos, points, center, degrees):
    a = math.radians(degrees)
    rot = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
    pos[points] = center + (pos[points] - center) @ rot.T


def test_start_beyond_the_limits_recovers_without_breaking():
    c = cr.Creature(cr.diagonal_gait_genome())
    P = c.world.pos
    _rotate(P, [sk.L_HAND], P[sk.L_ELBOW].copy(), 90.0)                 # coude gauche plié à l'envers
    _rotate(P, [sk.L_KNEE, sk.L_FOOT], P[sk.L_HIP].copy(), 105.0)       # fémur gauche rabattu derrière le bassin
    start = ja.anatomical_angles(P)
    assert start[1] == pytest.approx(-55.0) and start[2] == pytest.approx(-150.0)
    hip = []
    for k in range(int(round(2.0 / H))):
        c.substep(H)
        hip.append(ja.anatomical_angles(c.world.pos)[2])
        assert np.all(np.isfinite(c.world.pos)) and np.all(np.isfinite(c.world.vel))
        if k >= 60:                                                     # 1/8 s plus tard : revenu dans les butées
            assert c.world.limit_violation().min() >= -TOL
    hip = np.unwrap(np.radians(hip))
    assert np.degrees(hip.min()) > -151.0                   # revenu par le côté court (−150° → −80°), sans tour
    assert c.world.length_error() < 0.01
    assert np.hypot(*c.world.vel[c.body_points].T).max() < config.AUDIT_MAX_SPEED


def test_old_genome_with_targets_beyond_the_limits_climbs_safely(monkeypatch):
    monkeypatch.setattr(config, "JOINT_LIMITS", False)
    genome = cr.random_genome(np.random.default_rng(11))   # cibles ±90° : une partie hors de la plage articulaire
    low, high = cr.joint_limits_phi().T
    assert np.any((genome.targets < low) | (genome.targets > high))
    monkeypatch.setattr(config, "JOINT_LIMITS", True)
    c, ledger = audit.audit(genome)
    weight = c.world.mass.sum() * config.G
    assert np.all(np.isfinite(c.world.pos))
    assert c.world.limit_violation().min() >= -TOL
    assert ledger["butees_engagements"] > 0
    assert ledger["saut_engagement_max"] / weight < config.AUDIT_MAX_LIMIT_JUMP
    assert ledger["hors_muscles+"] / weight < config.AUDIT_MAX_CREATED_HEIGHT


@pytest.mark.parametrize("name", ["grimpeuse aléatoire", "marche écrite à la main", "inerte"])
def test_limits_create_no_energy(name):
    genome = {"grimpeuse aléatoire": lambda: _test_genomes()[8], "marche écrite à la main": cr.diagonal_gait_genome,
              "inerte": cr.limp_genome}[name]()
    c, ledger = audit.audit(genome)
    weight = c.world.mass.sum() * config.G
    assert ledger["liens_contacts+"] < 1e-9                 # liens + butées + sol : dissipatifs
    assert ledger["saut_engagement_max"] / weight < config.AUDIT_MAX_LIMIT_JUMP
    stats = ja.joint_stats([ja.anatomical_angles(ja.record(genome)[0])])   # angles à chaque sous-pas
    assert all(d["exces_max"] <= 0.5 for d in stats.values())               # pénétration ≤ 0.5° tout du long


def test_flag_off_leaves_the_engine_untouched(monkeypatch):
    monkeypatch.setattr(config, "JOINT_LIMITS", False)
    c = cr.Creature(cr.diagonal_gait_genome())
    assert len(c.world.limit_lo) == 0 and len(c.world.limit_active) == 0
    assert batch.pack([cr.diagonal_gait_genome()])["lim_lo"].shape == (1, 0)
    span = math.radians(config.TARGET_RANGE_DEG)
    assert cr.target_bounds() == (-span, span)


def test_run_without_the_key_replays_without_limits(tmp_path, monkeypatch):
    (tmp_path / "config.json").write_text(json.dumps({"G": config.G}))
    ev.use_run_config(str(tmp_path))
    assert config.JOINT_LIMITS is False                     # run d'avant B2 : sans butées


def test_new_run_records_the_flag_and_keeps_targets_in_range(tmp_path):
    run = str(tmp_path / "0")
    ev.train(0, generations=1, pop_size=12, run_dir=run, audit_every=0, log=lambda *_: None)
    with open(f"{run}/config.json") as fh:
        assert json.load(fh)["JOINT_LIMITS"] is True
    low, high = cr.joint_limits_phi().T
    for gen in (0, 1):
        pop, _, _, _ = ev.load_generation(run, gen)
        assert np.all((pop.targets >= low - 1e-12) & (pop.targets <= high + 1e-12))
    children = ev.mutate(pop, np.random.default_rng(0))
    assert np.all((children.targets >= low - 1e-12) & (children.targets <= high + 1e-12))
