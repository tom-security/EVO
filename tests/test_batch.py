"""Évaluateur batché (phase 3a) : mêmes résultats que le moteur scalaire à 1e-9 près."""
import numpy as np
import pytest

import config
from evo import batch
from evo import creature as cr
from evo import physics

pytestmark = pytest.mark.skipif(not physics.HAVE_NUMBA, reason="numba non installé")


def _test_genomes():
    rng = np.random.default_rng(123)
    climber = [cr.random_genome(rng) for _ in range(36)][35]  # la grimpeuse aléatoire (+9 m)
    others = [cr.random_genome(np.random.default_rng(seed)) for seed in range(16)]
    return others + [climber, cr.diagonal_gait_genome(), cr.diagonal_gait_genome(double_support=False),
                     cr.diagonal_gait_genome(period=1.3, strength=0.7, swing_deg=55.0), cr.limp_genome()]


@pytest.fixture(scope="module")
def reference():
    genomes = _test_genomes()
    return genomes, [cr.Creature(g).simulate(10.0) for g in genomes]


@pytest.mark.parametrize("block", [8, 64])  # blocs pleins + bloc incomplet ; un seul bloc incomplet
def test_batch_matches_scalar_engine(reference, block, monkeypatch):
    genomes, scalar = reference
    assert len(genomes) >= 20
    monkeypatch.setattr(config, "BATCH_BLOCK", block)
    res = batch.evaluate(genomes)
    for k, c in enumerate(scalar):
        np.testing.assert_allclose(res["pos"][k], c.world.pos, rtol=0, atol=1e-9)
        np.testing.assert_allclose(res["vel"][k], c.world.vel, rtol=0, atol=1e-9)
        assert res["height"][k] == pytest.approx(c.height(), abs=1e-9)
        assert res["energy"][k] == pytest.approx(c.energy, abs=1e-9)
        assert bool(res["fallen"][k]) == c.fallen
        assert res["muscle_mass"][k] == pytest.approx(c.muscle_mass())
        assert res["score"][k] == pytest.approx(c.score(), abs=1e-9)
    # la population contient des grimpeuses et des créatures au sol
    assert res["fallen"].any() and (res["height"] > 3.0).any()
