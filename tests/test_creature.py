"""Critères chiffrés de la phase 2 : sol, mur, muscles, contrôleur, génome, grimpe (§1.7, §2, §10)."""
import math

import numpy as np
import pytest

import config
from evo import audit
from evo import creature as cr
from evo import physics
from evo import skeleton as sk
from evo.benches import GroundBench, H


# Sol (§1.7) ------------------------------------------------------------------------
def test_point_dropped_on_ground_does_not_penetrate_or_bounce():
    world = physics.World([(0.0, config.START_HEIGHT)], mass=[1.0])
    world.ground_y = config.GROUND_Y
    lowest, highest_after_contact, touched = math.inf, -math.inf, False
    for _ in range(int(3.0 / H)):
        physics.substep(world, H)
        lowest = min(lowest, world.pos[0, 1])
        touched = touched or world.pos[0, 1] <= config.GROUND_Y
        if touched:
            highest_after_contact = max(highest_after_contact, world.pos[0, 1])
    assert lowest >= config.GROUND_Y - 1e-12            # jamais sous le sol
    assert highest_after_contact <= config.GROUND_Y + 1e-12  # aucun rebond (restitution 0)
    np.testing.assert_allclose(world.vel[0], 0.0, atol=1e-12)


@pytest.mark.parametrize("mu", [0.5, 1.0, 2.0])
def test_sliding_point_stops_at_coulomb_distance(mu):
    """Distance d'arrêt v0²/(2μg). Euler semi-implicite freine avant de déplacer :
    d = v0²/(2μg) − v0·h/2 + O(h²). Tolérance : v0·h (= 1 cm à 5 m/s)."""
    v0 = 5.0
    world = physics.World([(0.0, config.GROUND_Y)], mass=[1.0], vel=[(v0, 0.0)])
    world.ground_y = config.GROUND_Y
    world.ground_friction = mu
    for _ in range(int(3.0 / H)):
        physics.substep(world, H)
    assert world.vel[0, 0] == 0.0
    assert world.pos[0, 0] == pytest.approx(v0 ** 2 / (2 * mu * config.G), abs=v0 * H)


def test_limp_creature_falls_and_lies_on_ground():
    bench = GroundBench()
    for _ in range(int(10.0 / H)):
        bench.substep(H)
    c = bench.creature
    assert c.fallen
    assert bench.min_y >= config.GROUND_Y - 1e-9
    assert -config.START_HEIGHT < c.height() < -config.START_HEIGHT + 2.0
    # Le torse est au repos sur le sol (frottement fort : il ne glisse pas). Les bras, sans
    # muscles et sans frottement aux articulations, peuvent continuer à osciller comme des
    # pendules : l'énergie cinétique restante est bornée, pas nulle.
    torso_speed = np.linalg.norm(c.world.vel[[sk.NECK, sk.PELVIS]], axis=1).max()
    assert torso_speed < 0.1
    fall_energy = c.world.mass.sum() * config.G * config.START_HEIGHT
    assert c.world.kinetic_energy() < 0.02 * fall_energy
    assert bench.max_body < 0.01
    # La queue, droite et légère, touche le sol la première à ~7 m/s : pic de compression
    # passager (~5 % pendant ~30 ms avec SUBSTEPS = 8, moitié moins avec 16), puis < 1 %.
    assert bench.max_tail < 0.08
    err = np.abs(c.world.link_lengths() - c.world.rest) / c.world.rest
    assert err.max() < 0.01


@pytest.mark.skipif(not physics.HAVE_NUMBA, reason="numba non installé")
def test_numba_matches_python_reference_with_ground():
    creatures = []
    for backend in ("numba", "python"):
        c = cr.Creature(cr.limp_genome())
        c.world.backend = backend
        creatures.append(c.simulate(3.0))
    a, b = (c.world for c in creatures)
    np.testing.assert_allclose(a.pos, b.pos, rtol=0, atol=1e-9)
    np.testing.assert_allclose(a.vel, b.vel, rtol=0, atol=1e-9)


# Mur ---------------------------------------------------------------------------------
def _all_holds_genome():
    genome = cr.diagonal_gait_genome()
    genome.holds[:] = True
    return genome


def test_limbs_can_hold_only_on_trunk_band():
    x = config.TRUNK_X + config.TRUNK_WIDTH / 2 - 0.5  # bord droit du tronc
    c = cr.Creature(_all_holds_genome(), x=x)
    c.substep(H)
    inside = [c.on_trunk(c.world.pos[limb]) for limb in cr.LIMBS]
    assert any(inside) and not all(inside)  # les pattes de gauche sur le tronc, pas celles de droite
    assert [bool(c.world.held[limb]) for limb in cr.LIMBS] == inside


def test_fallen_creature_cannot_hold_again():
    far = config.TRUNK_X + config.TRUNK_WIDTH + 50.0  # hors du tronc : aucune prise, elle tombe
    c = cr.Creature(_all_holds_genome(), x=far).simulate(3.0)
    assert c.fallen and not c.world.held.any()
    c.world.pos[:, 0] -= far  # on la replace devant le tronc…
    c.apply_holds(0)
    assert not c.world.held.any()  # … mais une créature tombée reste au sol


# Muscles et contrôleur (§2.3, §2.4) ------------------------------------------------
def test_rest_pose_joint_angles_are_zero():
    c = cr.Creature(cr.diagonal_gait_genome())
    np.testing.assert_allclose(c.joint_phi(), 0.0, atol=1e-12)


@pytest.mark.parametrize("j", range(8))
def test_plus_muscle_acts_as_named(j):
    """Deltoïde et fléchisseurs de hanche amènent le membre vers la tête ; biceps et
    ischios ferment l'articulation. Torse tenu, pas de gravité, seul le muscle « + » de j tire."""
    c = cr.Creature(cr.diagonal_gait_genome())
    w = c.world
    w.g, w.ground_y = 0.0, None
    w.held[[sk.NECK, sk.PELVIS, sk.L_SHOULDER, sk.R_SHOULDER, sk.L_HIP, sk.R_HIP, sk.HEAD]] = True
    a, piv, b = cr.JOINTS[j]

    def measures():
        seg = w.pos[b] - w.pos[piv]
        back = w.pos[a] - w.pos[piv]
        interior = math.acos(np.dot(seg, back) / np.linalg.norm(seg) / np.linalg.norm(back))
        return seg[1] / np.linalg.norm(seg), interior

    y0, interior0 = measures()
    for _ in range(40):
        u = np.zeros(8)
        u[j] = 0.3
        w.torque = cr.JOINT_SIGNS * u * cr.torque_unit()
        physics.substep(w, H)
    y1, interior1 = measures()
    assert c.joint_phi()[j] > 0
    if j % 4 in (0, 2):   # épaule, hanche : le segment distal pointe plus vers la tête
        assert y1 > y0
    else:                 # coude, genou : l'angle intérieur se ferme (flexion)
        assert interior1 < interior0


def test_pd_torque_is_clamped_by_asymmetric_strengths():
    genome = cr.diagonal_gait_genome()
    genome.strengths[:, :, 0] = 1.2   # « + »
    genome.strengths[:, :, 1] = 0.3   # « − »
    genome.targets[0] = np.radians([90, -90, 90, -90, -90, 90, -90, 90])
    c = cr.Creature(genome)
    c.control(0)
    np.testing.assert_allclose(c.activation, [1.2, -0.3, 1.2, -0.3, -0.3, 1.2, -0.3, 1.2])
    # couple physique = signe de l'articulation × force × unité de couple
    np.testing.assert_allclose(c.world.torque, cr.JOINT_SIGNS * c.activation * cr.torque_unit())


def test_clock_selects_pose_and_applies_holds_at_interval_start():
    genome = cr.diagonal_gait_genome(period=2.0)
    c = cr.Creature(genome)
    assert [c.current_pose(t) for t in (0.0, 0.49, 0.5, 1.2, 1.99, 2.0, 2.6)] == [0, 0, 1, 2, 3, 0, 1]
    seen = set()
    for _ in range(int(4.0 / H)):
        c.substep(H)
        got = [bool(c.world.held[limb]) for limb in cr.LIMBS]
        assert got == [bool(v) for v in genome.holds[c.pose_index]]  # toutes les pattes sont sur le tronc
        seen.add(c.pose_index)
    assert seen == {0, 1, 2, 3}


def test_energy_is_time_integral_of_muscle_force():
    c = cr.Creature(cr.diagonal_gait_genome())
    expected = 0.0
    for _ in range(int(1.0 / H)):
        c.substep(H)
        expected += np.abs(c.activation).sum() * H
    assert c.energy == pytest.approx(expected, rel=1e-12)


# Génome (§2.5) -----------------------------------------------------------------------
def test_random_genome_respects_init_ranges():
    rng = np.random.default_rng(0)
    ref = cr.reference_lengths()
    for _ in range(200):
        g = cr.random_genome(rng)
        assert np.all(g.lengths >= ref * config.LENGTH_FACTOR_RANGE[0] - 1e-12)
        assert np.all(g.lengths <= ref * config.LENGTH_FACTOR_RANGE[1] + 1e-12)
        assert np.all((g.strengths >= 0) & (g.strengths <= config.S_MAX))
        if config.SYMMETRIC_MORPHOLOGY:
            np.testing.assert_array_equal(g.strengths[0], g.strengths[1])
        assert config.PERIOD_INIT[0] <= g.period <= config.PERIOD_INIT[1]
        assert g.targets.shape == (config.N_POSES, 8) and g.holds.shape == (config.N_POSES, 4)
        assert np.all(np.abs(g.targets) <= math.radians(config.TARGET_RANGE_DEG))


def test_muscle_mass_is_sum_of_16_strengths_without_tail():
    g = cr.random_genome(np.random.default_rng(1))
    assert g.strengths.size == 16
    assert g.muscle_mass() == pytest.approx(g.strengths.sum())
    assert all(p < sk.TAIL_START for joint in cr.JOINTS for p in joint)  # aucune articulation dans la queue
    # §2.3 : 16 forces uniformes dans [0, 1.6] → masse musculaire moyenne ≈ 12.8 à la génération 0
    rng = np.random.default_rng(2)
    mean = np.mean([cr.random_genome(rng).muscle_mass() for _ in range(2000)])
    assert mean == pytest.approx(8 * config.S_MAX, rel=0.02)


def test_fitness_satisfies_calibration_constraints():
    """§3.2 : rester immobile bat tomber, le champion de la génération 200 reste très positif."""
    immobile = cr.fitness(-0.1, 0.5, 13.0)
    fallen = cr.fitness(-8.0, 25.0, 13.0)
    champion = cr.fitness(36.0, 32.5, 13.5)
    assert immobile > fallen
    assert champion > 30.0
    # à hauteur égale, moins d'énergie et moins de muscles gagnent
    assert cr.fitness(2.0, 5.0, 8.0) > cr.fitness(2.0, 10.0, 8.0) > cr.fitness(2.0, 10.0, 12.0)


# Fin de phase 2 : les poses écrites à la main font monter la créature ----------------
def test_hand_written_diagonal_gait_climbs():
    c = cr.Creature(cr.diagonal_gait_genome())
    heights, max_err = [], 0.0
    for k in range(int(round(10.0 / H))):
        c.substep(H)
        max_err = max(max_err, c.world.length_error())
        if (k + 1) % int(round(2.0 / H)) == 0:
            heights.append(c.height())
    assert not c.fallen
    assert heights[-1] > 3.0                                 # mesuré : +3.75 m en 10 s
    assert all(b > a for a, b in zip(heights, heights[1:]))  # gagne de la hauteur à chaque cycle
    assert max_err < 0.01


# Audit d'énergie (avant la phase 3) --------------------------------------------------
def _random_climber():
    """La créature aléatoire n°35 de la graine 123 : elle grimpe de ~9 m dès la génération 0."""
    rng = np.random.default_rng(123)
    return [cr.random_genome(rng) for _ in range(36)][35]


def test_energy_audit_replays_the_engine_exactly():
    genome = _random_climber()
    audited, _ = audit.audit(genome)
    reference = cr.Creature(genome).simulate(10.0)
    np.testing.assert_array_equal(audited.world.pos, reference.world.pos)
    assert audited.energy == pytest.approx(reference.energy, rel=1e-12)


@pytest.mark.parametrize("name", ["grimpeuse aléatoire", "marche écrite à la main", "inerte"])
def test_no_mechanism_but_muscles_creates_energy(name):
    genome = {"grimpeuse aléatoire": _random_climber,
              "marche écrite à la main": cr.diagonal_gait_genome,
              "inerte": cr.limp_genome}[name]()
    c, ledger = audit.audit(genome)
    fall_energy = c.world.mass.sum() * config.G * config.START_HEIGHT
    # Énergie apparue dans un sous-pas au-delà de l'apport des muscles. Seul reste : la
    # projection qui décomprime la queue à l'impact de la créature inerte (≈ 0.14 J sur 1 900 J).
    assert ledger["hors_muscles+"] < 1e-4 * fall_energy
    assert ledger["hold+"] == 0.0 and ledger["hold2+"] == 0.0  # prendre / lâcher ne crée rien
    assert ledger["liens_contacts+"] < 1e-9                    # liens + contacts sol : dissipatifs
    # tout ce qui est gagné (hauteur, vitesse) a été payé par les muscles
    assert ledger["E_fin"] - ledger["E_debut"] <= ledger["muscles"] + ledger["hors_muscles+"]
