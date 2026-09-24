"""Évolution (§3) : mutations, sélection, runs déterministes, reprise, relecture."""
import csv
import filecmp
import math
import os

import numpy as np
import pytest

import config
from evo import creature as cr
from evo import evolution as ev
from evo import physics

pytestmark = pytest.mark.skipif(not physics.HAVE_NUMBA, reason="numba non installé")


def _pop(n=400, seed=0):
    return ev.random_population(np.random.default_rng(seed), n)


# Mutations (§3.3) ---------------------------------------------------------------------
def test_mutations_respect_bounds_symmetry_and_rates():
    parents = _pop()
    children = ev.mutate(parents, np.random.default_rng(1))
    ref = cr.reference_lengths()
    lo, hi = config.LENGTH_FACTOR_RANGE
    assert np.all(children.lengths >= ref * lo - 1e-12) and np.all(children.lengths <= ref * hi + 1e-12)
    assert np.all((children.strengths >= 0) & (children.strengths <= config.S_MAX))
    np.testing.assert_array_equal(children.strengths[:, 0], children.strengths[:, 1])  # symétrie
    assert np.all((children.period >= config.PERIOD_BOUNDS[0]) & (children.period <= config.PERIOD_BOUNDS[1]))
    span = math.radians(config.TARGET_RANGE_DEG)
    assert np.all(np.abs(children.targets) <= span + 1e-12)
    # fréquence des mutations : P_MUT par gène continu (±4 écarts-types), P_FLIP par booléen
    changed = np.mean(children.targets != parents.targets)
    n = parents.targets.size
    assert abs(changed - config.P_MUT) < 4 * math.sqrt(config.P_MUT * (1 - config.P_MUT) / n) + 0.01
    flipped = np.mean(children.holds != parents.holds)
    assert abs(flipped - config.P_FLIP) < 4 * math.sqrt(config.P_FLIP * (1 - config.P_FLIP) / parents.holds.size)


def test_big_mutations_make_a_long_tail():
    """Distribution en cloche avec une longue queue (§3.3) : P_BIG des mutations ×BIG_FACTOR."""
    parents = _pop(2000)
    parents.targets[:] = 0.0
    children = ev.mutate(parents, np.random.default_rng(2))
    delta = children.targets[children.targets != 0.0]
    sigma = config.MUT_SIGMA_FRAC * 2 * math.radians(config.TARGET_RANGE_DEG)
    beyond = np.mean(np.abs(delta) > 4 * sigma)  # quasi impossible pour une gaussienne seule
    assert config.P_BIG * 0.4 < beyond < config.P_BIG * 1.2


def test_log_period_mutation_is_multiplicative(monkeypatch):
    monkeypatch.setattr(config, "PERIOD_MUTATION", "log")
    parents = _pop(2000)
    parents.period[:] = 2.0
    children = ev.mutate(parents, np.random.default_rng(3))
    ratio = children.period[children.period != 2.0] / 2.0
    assert np.all(ratio > 0)
    assert abs(np.median(np.log(ratio))) < 0.02  # symétrique en log


# Sélection (§3.1) ---------------------------------------------------------------------
def test_next_generation_keeps_best_half_without_reevaluation(monkeypatch):
    pop = _pop(40)
    results = ev.evaluate(pop)
    calls = []
    real = ev.evaluate
    monkeypatch.setattr(ev, "evaluate", lambda p: calls.append(len(p)) or real(p))
    new_pop, new_results, lineage = ev.next_generation(pop, results, np.random.default_rng(5))
    assert calls == [20]  # seuls les 20 enfants sont évalués
    order = ev.ranking(results["score"])[:20]
    for key in ev.RESULT_KEYS:
        np.testing.assert_array_equal(new_results[key][:20], results[key][order])  # scores conservés
    np.testing.assert_array_equal(new_pop.period[:20], pop.period[order])
    np.testing.assert_array_equal(lineage["parent"], np.concatenate([order, order]))
    assert lineage["is_child"].sum() == 20 and not lineage["is_child"][:20].any()


# Runs --------------------------------------------------------------------------------
def test_run_is_deterministic_resumable_and_replayable(tmp_path):
    a, b, c = (str(tmp_path / name) for name in "abc")
    ev.train(0, generations=3, pop_size=40, run_dir=a, audit_every=0, log=lambda *_: None)
    ev.train(0, generations=3, pop_size=40, run_dir=b, audit_every=0, log=lambda *_: None)
    ev.train(0, generations=2, pop_size=40, run_dir=c, audit_every=0, log=lambda *_: None)
    ev.train(0, generations=3, pop_size=40, run_dir=c, audit_every=0, log=lambda *_: None)  # reprise
    for gen in range(4):
        for other in (b, c):
            x, y = np.load(ev.gen_path(a, gen)), np.load(ev.gen_path(other, gen))
            for key in x.files:
                if key != "stats":  # stats contient le temps de calcul
                    np.testing.assert_array_equal(x[key], y[key])
    assert filecmp.cmp(os.path.join(a, "config.json"), os.path.join(c, "config.json"), shallow=False)

    # stats.csv : une ligne par génération, histogramme 1 m de −10 à 40
    with open(os.path.join(c, "stats.csv")) as f:
        rows = list(csv.DictReader(f))
    assert [int(r["gen"]) for r in rows] == [0, 1, 2, 3]
    assert sum(int(rows[0][col]) for col in ev.HIST_COLUMNS) == 40
    assert len(ev.HIST_COLUMNS) == 50

    # lignée : root (ancêtre de gén. 0) = remontée des parents ; ancêtres distincts, part au sol
    root = ev.load_generation(c, 3)[2]["root"]
    np.testing.assert_array_equal(root, ev.roots_from_parents(c, 3))
    assert int(rows[0]["ancestors"]) == 40 and int(rows[3]["ancestors"]) == np.unique(root).size <= 20
    pop3, results3, _, _ = ev.load_generation(c, 3)
    assert float(rows[3]["fallen_frac"]) == pytest.approx(results3["fallen"].mean(), abs=1e-6)
    assert float(rows[3]["period_std"]) == pytest.approx(pop3.period.std(), rel=1e-5)

    # une créature relue et rejouée avec le moteur scalaire retrouve son score
    pop, results, _, _ = ev.load_generation(c, 3)
    for i in (0, 25):
        replay = cr.Creature(pop.genome(i)).simulate(config.SIM_DURATION)
        assert replay.score() == pytest.approx(results["score"][i], abs=1e-9)


def test_audit_of_champion_writes_report(tmp_path):
    run = str(tmp_path / "run")
    ev.train(0, generations=0, pop_size=24, run_dir=run, audit_every=25, log=lambda *_: None)
    with open(os.path.join(run, "audit.csv")) as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1 and rows[0]["gen"] == "0"
    assert float(rows[0]["height"]) == pytest.approx(float(rows[0]["height_replay"]), abs=1e-6)
    assert float(rows[0]["created_height_m"]) < config.AUDIT_MAX_CREATED_HEIGHT
