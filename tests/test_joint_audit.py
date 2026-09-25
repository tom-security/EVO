"""Chantier B, phase B1 : audit des angles articulaires (conventions, mesures, commande `joints`)."""
import math

import numpy as np
import pytest

import config
from evo import creature as cr
from evo import evolution as ev
from evo import joint_audit as ja
from evo import skeleton as sk

ELBOW_L, KNEE_L = 1, 3          # indices dans l'ordre de creature.JOINTS (côté gauche)


@pytest.fixture(scope="module")
def small_run(tmp_path_factory):
    run = str(tmp_path_factory.mktemp("run") / "0")
    ev.train(0, generations=1, pop_size=24, run_dir=run, audit_every=0, log=lambda *_: None)
    return run


def _rest():
    return sk.build_skeleton().pos.copy()


def _reflect(point, pivot, through):
    """Symétrique de `point` par rapport à la droite (pivot, through)."""
    d = (through - pivot) / np.linalg.norm(through - pivot)
    v = point - pivot
    return pivot + 2 * (v @ d) * d - v


def test_rest_pose_angles():
    rest = ja.rest_angles()
    assert rest == {"épaule": 45.0, "coude": 35.0, "hanche": -45.0, "genou": 35.0}
    assert np.allclose(ja.anatomical_angles(_rest()), ja.rest_offsets(), atol=1e-9)
    for kind, (lo, hi) in config.JOINT_LIMITS_DEG.items():   # le repos est dans les butées
        assert lo < rest[kind] < hi


def test_angles_are_controller_phi_plus_rest():
    c = cr.Creature(cr.random_genome(np.random.default_rng(3)))
    h = config.DT / config.SUBSTEPS
    pos, phi = [], []
    for _ in range(600):
        c.substep(h)
        pos.append(c.world.pos.copy())
        phi.append(np.degrees(c.joint_phi()))
    gap = ja.anatomical_angles(np.array(pos)) - ja.rest_offsets() - np.array(phi)
    assert np.max(np.abs((gap + 180) % 360 - 180)) < 1e-9


def test_left_and_right_are_mirrored():
    c = cr.Creature(cr.random_genome(np.random.default_rng(5)))
    for _ in range(300):
        c.substep(config.DT / config.SUBSTEPS)
    P = c.world.pos
    swap = np.arange(len(P))
    for name in sk.BODY_POINTS:
        if name.startswith("L_"):
            left, right = sk.BODY_POINTS.index(name), sk.BODY_POINTS.index("R_" + name[2:])
            swap[left], swap[right] = right, left
    mirrored = P[swap] * (-1.0, 1.0)
    a, b = ja.anatomical_angles(P), ja.anatomical_angles(mirrored)
    assert np.allclose(b[:4], a[4:], atol=1e-9) and np.allclose(b[4:], a[:4], atol=1e-9)


def test_reversed_elbow_and_knee_are_negative():
    P = _rest()
    P[sk.L_HAND] = _reflect(P[sk.L_HAND], P[sk.L_ELBOW], 2 * P[sk.L_ELBOW] - P[sk.L_SHOULDER])
    P[sk.L_FOOT] = _reflect(P[sk.L_FOOT], P[sk.L_KNEE], 2 * P[sk.L_KNEE] - P[sk.L_HIP])
    A = ja.anatomical_angles(P)
    assert A[ELBOW_L] == pytest.approx(-35.0) and A[KNEE_L] == pytest.approx(-35.0)
    assert A[4 + 1] == pytest.approx(35.0) and A[4 + 3] == pytest.approx(35.0)    # côté droit intact


def test_full_turn_and_out_of_bounds_fraction():
    rest = _rest()
    turns = np.linspace(0.0, 4 * math.pi, 400)                  # l'avant-bras gauche fait deux tours
    frames = np.repeat(rest[None], len(turns), axis=0)
    r = rest[sk.L_HAND] - rest[sk.L_ELBOW]
    c, s = np.cos(turns), np.sin(turns)
    frames[:, sk.L_HAND] = rest[sk.L_ELBOW] + np.stack([c * r[0] - s * r[1], s * r[0] + c * r[1]], axis=1)
    A = ja.anatomical_angles(frames)
    assert np.ptp(A[:, ELBOW_L]) == pytest.approx(720.0, abs=2.0)
    stats = ja.joint_stats([A])
    assert stats["coude"]["tour_complet"] == 1.0 and stats["genou"]["tour_complet"] == 0.0
    lo, hi = config.JOINT_LIMITS_DEG["coude"]
    x = A[:, [ELBOW_L, 4 + ELBOW_L]].ravel()
    assert stats["coude"]["hors_butees"] == pytest.approx(np.mean((x < lo) | (x > hi)))
    assert stats["épaule"]["hors_butees"] == 0.0


def test_midline_and_crossings():
    P = _rest()
    assert np.all(ja.midline_distances(P) > 0)
    assert ja.limb_crossings(P) == (0.0, 0.0)
    middle = 0.5 * (P[sk.R_ELBOW] + P[sk.R_HAND])              # l'avant-bras gauche traverse le droit en son milieu
    P[sk.L_HAND] = P[sk.L_ELBOW] + 1.5 * (middle - P[sk.L_ELBOW])
    d = ja.midline_distances(P)
    assert d[0, 1] < 0 and np.all(np.delete(d.ravel(), 1) > 0)
    assert ja.limb_crossings(P)[1] == 1.0
    assert ja.girdle_drift(np.stack([P, P])) == 0.0


def test_targets_out_of_bounds():
    genomes = [cr.random_genome(np.random.default_rng(k)) for k in range(4)]
    pop = ev.Population.from_genomes(genomes)
    pop.targets[:] = 0.0                                        # toutes les cibles au repos : dans les butées
    assert all(v == 0.0 for v in ja.targets_out_of_bounds(pop).values())
    pop.targets[:, :, ELBOW_L] = math.radians(-60.0)            # coude gauche à β = −25° : pli à l'envers
    assert ja.targets_out_of_bounds(pop)["coude"] == pytest.approx(0.5)


def test_audit_replays_the_run(small_run, tmp_path):
    result = ja.audit(small_run, gen=1, top=2, sample=2, log=None)
    assert result["identique"] and result["gen"] == 1
    assert [r["groupe"] for r in result["creatures"]] == ["meilleures"] * 2 + ["hasard"] * 2
    assert [r["rang"] for r in result["creatures"][:2]] == [1, 2]
    for group in result["groupes"].values():
        for d in group["articulations"].values():
            assert 0.0 <= d["hors_butees"] <= 1.0 and d["min"] <= d["p1"] <= d["p99"] <= d["max"]
    assert all(0.0 <= v <= 1.0 for v in result["cibles_hors_butees"].values())
    lines = ja.report_lines(result)
    assert "hauteurs identiques au run" in lines[-1]
    path = ja.export(result, str(tmp_path))
    assert path.endswith("angles_s0_g1.json")
