"""Critères chiffrés des 8 bancs d'essai de la phase 1 (§10 de la spec)."""
import math

import numpy as np
import pytest

import config
from evo import calibration, physics
from evo import skeleton as sk
from evo.benches import (H, ContractBench, GravityBench, HoldBench, IterationBench,
                         LinkBench, MassBench, MovementBench, PendulumBench)


def run(bench, seconds):
    for _ in range(int(round(seconds / H))):
        bench.substep(H)
    return bench


# 1. Movement() -----------------------------------------------------------------
def test_movement_straight_line():
    world = physics.World([(0.0, 0.0)], mass=[1.0], vel=[(2.0, 0.5)])
    world.g = 0.0
    for _ in range(60):
        physics.step(world)
    np.testing.assert_allclose(world.pos[0], (2.0, 0.5), atol=1e-12)
    np.testing.assert_allclose(world.vel[0], (2.0, 0.5), atol=0)
    assert run(MovementBench(), 2.0).max_err < 1e-12


# 2. Gravity() ------------------------------------------------------------------
def test_gravity_parabola_semi_implicit_euler():
    bench = run(GravityBench(), 1.0)
    t = bench.world.t
    # Euler semi-implicite : écart exact à la parabole = ½·g·h·t (erreur d'ordre 1 en h)
    assert bench.max_err == pytest.approx(0.5 * config.G * H * t, rel=1e-6)
    assert bench.max_err < 0.015


def test_gravity_error_is_first_order():
    errors = []
    for substeps in (4, 8, 16):
        world = physics.World([(0.0, 0.0)], mass=[1.0], vel=[(3.0, 6.0)])
        for _ in range(60):
            physics.step(world, substeps=substeps)
        exact = np.array([3.0, 6.0 - 0.5 * config.G])
        errors.append(np.linalg.norm(world.pos[0] - exact))
    assert errors[0] / errors[1] == pytest.approx(2.0, rel=1e-6)
    assert errors[1] / errors[2] == pytest.approx(2.0, rel=1e-6)


# 3. Hold() ---------------------------------------------------------------------
def test_held_point_does_not_move():
    bench = run(HoldBench(), 2.0)
    np.testing.assert_array_equal(bench.world.pos[0], (0.0, 0.0))
    np.testing.assert_array_equal(bench.world.vel[0], (0.0, 0.0))
    assert bench.max_drift == 0.0


def test_hold_release_and_catch():
    bench = HoldBench()
    bench.on_key("h")  # lâcher
    run(bench, 0.5)
    fallen = bench.world.pos[0].copy()
    assert fallen[1] < -1.0
    bench.on_key("h")  # re-fixer là où il est
    run(bench, 0.5)
    np.testing.assert_array_equal(bench.world.pos[0], fallen)


# 4. Link() ---------------------------------------------------------------------
def test_two_linked_points_stay_rigid_spring_does_not():
    bench = LinkBench()
    bench.on_key("m")  # comparaison rigide / ressort
    run(bench, 1.3)
    rigid_err, spring_err = bench.max_err
    assert rigid_err < 1e-3
    assert spring_err > 0.05


def test_link_conserves_momentum():
    world = physics.World([(0, 0), (1, 0), (1.5, 0.8)], [(0, 1), (1, 2)],
                          vel=[(0.3, -1.0), (0.0, 2.0), (-1.0, 0.5)])
    world.g = 0.0
    p0 = world.momentum()
    for _ in range(60):
        physics.step(world)
    np.testing.assert_allclose(world.momentum(), p0, atol=1e-12)


def test_simple_pendulum_small_oscillation_period():
    """Pendule à 2 points : un point fixé, un point lié par un os, lâché à 5°.

    Hypothèse : la masse de l'os est répartie sur ses deux extrémités (§1.6) et celle du
    point fixé ne compte pas (masse infinie) ; c'est donc un pendule simple idéal (masse
    ponctuelle, tige sans masse), de période T = 2π√(L/g) indépendante de la masse.
    Ce n'est PAS une tige pesante (qui donnerait 2π√(2L/3g)).
    """
    for length in (0.5, 1.0, 2.0):
        measured = calibration.measure_period(calibration.simple_pendulum(length, 5.0))
        bare = calibration.pendulum_period_theory(length, 5.0, amplitude_correction=False)
        corrected = calibration.pendulum_period_theory(length, 5.0)
        # À 5°, l'amplitude finie allonge la période de θ0²/16 ≈ 4.8e-4 : tolérance 1e-3 sur 2π√(L/g).
        assert measured == pytest.approx(bare, rel=1e-3)
        # Avec la correction d'amplitude, il reste l'erreur du schéma : Euler semi-implicite
        # ~(ωh)²/24 ≈ 2e-6 pour h = DT/SUBSTEPS = 1/480 s, plus la légère décroissance
        # d'amplitude due à la dissipation. Mesuré : ≤ 4e-6 (SUBSTEPS 8), ≤ 1.5e-5 (SUBSTEPS 4).
        # Tolérance 1e-4 : valable pour SUBSTEPS ≥ 4.
        assert measured == pytest.approx(corrected, rel=1e-4)


# 5. Itérations -----------------------------------------------------------------
@pytest.mark.parametrize("n_points", [3, 5])
def test_link_iterations_converge(n_points):
    bench = IterationBench()
    bench.n_points = n_points
    bench.reset()
    residuals = [w.velocity_residual() for w in bench.frozen]  # après 0, 1, 2, 5, 20 passes
    assert all(a > b for a, b in zip(residuals, residuals[1:]))
    assert residuals[-1] < 1e-3 * residuals[0]


def test_hanging_chain_needs_iterations_and_stabilisation():
    bench = run(IterationBench(), 3.0)
    one_pass, _, _, twenty_passes, full_engine = bench.chain_max_err
    assert one_pass > 2 * twenty_passes  # plus de passes = beaucoup moins d'élasticité
    assert full_engine < 1e-3            # Baumgarte + projection suppriment la dérive


# 6. Contract() -----------------------------------------------------------------
def test_contraction_forces_obey_newton_third_law():
    rng = np.random.default_rng(0)
    for _ in range(50):
        pos = rng.normal(size=(3, 2))
        torque = rng.normal(size=1)
        forces = physics.contraction_forces(pos, np.array([[0, 1, 2]]), torque)
        moment = np.sum(pos[:, 0] * forces[:, 1] - pos[:, 1] * forces[:, 0])
        np.testing.assert_allclose(forces.sum(axis=0), 0.0, atol=1e-12)
        assert abs(moment) < 1e-12
        # norme τ/|A−P| sur A (§1.5)
        assert np.linalg.norm(forces[0]) == pytest.approx(abs(torque[0]) / np.linalg.norm(pos[0] - pos[1]))


def test_positive_torque_opens_the_angle():
    bench = ContractBench()
    bench.world.torque[0] = 0.3
    theta0 = bench.world.joint_angles()[0]
    for _ in range(100):
        physics.substep(bench.world, H)
    assert bench.world.joint_angles()[0] > theta0


def test_torque_work_becomes_kinetic_energy():
    """Sans gravité, le travail du couple (Σ τ·Δθ) se retrouve en énergie cinétique."""
    world = ContractBench().world
    world.torque[0] = -0.3
    work = 0.0
    for _ in range(int(0.8 / H)):
        theta = world.joint_angles()[0]
        physics.substep(world, H)
        work += world.torque[0] * (world.joint_angles()[0] - theta)
    assert work > 0.05
    assert world.kinetic_energy() == pytest.approx(work, rel=0.01)


def test_contract_bench_closes_and_opens_without_drift():
    bench = ContractBench()
    angles = []
    for _ in range(int(12.0 / H)):
        bench.substep(H)
        angles.append(math.degrees(bench.world.joint_angles()[0]))
    late = angles[int(3.0 / H):]
    assert min(late) < 36 and max(late) > 59     # suit les deux consignes
    assert min(late) > 30 and max(late) < 65     # sans dériver
    assert bench.max_sum_force < 1e-12
    assert bench.max_sum_moment < 1e-12
    assert bench.max_momentum < 1e-12
    assert bench.world.length_error() < 1e-3


# 7. Masses ---------------------------------------------------------------------
def test_masses_match_image_20():
    np.testing.assert_allclose(MassBench().world.mass, MassBench.EXPECTED)


def test_skeleton_masses_ignore_braces():
    skel = sk.build_skeleton()
    world = skel.make_world()
    L = config.BONE_REF_LENGTHS
    tail_seg = config.TAIL_LENGTH_FACTOR * L["spine"] / config.TAIL_SEGMENTS
    assert world.mass[sk.PELVIS] == pytest.approx(L["spine"] / 2 + L["pelvis"] + tail_seg / 2)
    assert world.mass[sk.L_HAND] == pytest.approx(L["forearm"] / 2)
    assert world.mass[sk.HEAD] == pytest.approx(config.HEAD_LENGTH / 2)


def test_skeleton_topology_and_symmetry():
    skel = sk.build_skeleton()
    names = skel.link_names
    assert len(sk.BODY_POINTS) == 14 and len(sk.BODY_BONES) == 13
    assert names.count("tail") == config.TAIL_SEGMENTS
    assert not skel.is_bone[np.array(names) == "brace"].any()
    for left, right in [(sk.L_HAND, sk.R_HAND), (sk.L_ELBOW, sk.R_ELBOW), (sk.L_FOOT, sk.R_FOOT)]:
        np.testing.assert_allclose(skel.pos[left] * (-1, 1), skel.pos[right], atol=1e-12)
    assert skel.pos[sk.L_HAND, 1] > skel.pos[sk.NECK, 1]   # bras levés
    assert skel.pos[sk.L_FOOT, 1] < skel.pos[sk.PELVIS, 1]  # jambes vers le bas


# Solveur numba vs référence Python ----------------------------------------------
needs_numba = pytest.mark.skipif(not physics.HAVE_NUMBA, reason="numba non installé")


@needs_numba
def test_numba_kernels_match_python_reference_single_call():
    rng = np.random.default_rng(1)
    skel = sk.build_skeleton()
    for _ in range(20):
        pos = skel.pos + rng.normal(scale=0.02, size=skel.pos.shape)  # liens un peu faussés
        vel = rng.normal(size=skel.pos.shape)
        worlds = []
        for backend in ("numba", "python"):
            world = physics.World(pos, skel.links, skel.rest, skel.is_bone, vel=vel)
            world.held[sk.R_FOOT] = True
            world.backend = backend
            physics.link(world, H)
            physics.project_links(world)
            worlds.append(world)
        np.testing.assert_allclose(worlds[0].vel, worlds[1].vel, rtol=0, atol=1e-12)
        np.testing.assert_allclose(worlds[0].pos, worlds[1].pos, rtol=0, atol=1e-12)


@needs_numba
def test_numba_matches_python_reference_on_human_pendulum():
    """Même trajectoire à 1e-9 près sur les 10 s du banc 8 (en pratique identique au bit près)."""
    benches = []
    for backend in ("numba", "python"):
        bench = PendulumBench()
        bench.world.backend = backend
        benches.append(run(bench, PendulumBench.DURATION))
    a, b = (bench.world for bench in benches)
    np.testing.assert_allclose(a.pos, b.pos, rtol=0, atol=1e-9)
    np.testing.assert_allclose(a.vel, b.vel, rtol=0, atol=1e-9)


# Stabilisation -------------------------------------------------------------------
def test_chosen_stabilisation_injects_no_energy():
    chosen = calibration.run_human_pendulum(config.BETA, config.N_POS_ITER)
    assert chosen["injected"] < 1e-6
    assert chosen["body"] < 0.01 and chosen["tail"] < 0.01
    # Contre-exemple documenté dans config.py : Baumgarte seul injecte de l'énergie.
    beta_only = calibration.run_human_pendulum(0.2, 0)
    assert beta_only["injected"] > 0.1


# 8. Pendule humain -------------------------------------------------------------
def test_human_pendulum_hanging_by_one_hand():
    bench = run(PendulumBench(), PendulumBench.DURATION)
    assert bench.finite
    assert bench.max_body < 0.01
    assert bench.max_tail < 0.01
    assert bench.max_energy_gain < 0.01  # J : le solveur ne crée pas d'énergie
