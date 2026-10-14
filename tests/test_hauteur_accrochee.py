"""Hauteur accrochée (v2, docs/SPEC_V2_GECKO.md) : hauteur du centre du torse au dernier instant où au moins une patte
tient le tronc. Moteur scalaire et évaluateur batché identiques au bit près ; simple mesure, sans effet sur la
simulation (les tests de test_batch.py et le rejeu des runs locaux le vérifient de leur côté)."""
import numpy as np
import pytest

import config
from evo import batch
from evo import creature as cr
from evo import physics

pytestmark = pytest.mark.skipif(not physics.HAVE_NUMBA, reason="numba non installé")

H = config.DT / config.SUBSTEPS


def _final_release_genome():
    """Marche diagonale dont la dernière pose ne tient rien : à 10 s, la créature est lâchée depuis 9,5 s."""
    g = cr.diagonal_gait_genome(period=2.0)
    g.holds[3] = False
    return g


def _always_held_genome():
    """Les 4 pattes tiennent dans toutes les poses, muscles au repos : accrochée jusqu'à 10 s."""
    g = cr.diagonal_gait_genome()
    g.holds[:] = True
    g.strengths[:] = 0.0
    return g


def _genomes():
    others = [cr.random_genome(np.random.default_rng(seed)) for seed in range(14)]
    return others + [cr.diagonal_gait_genome(), _final_release_genome(), _always_held_genome(), cr.limp_genome()]


@pytest.fixture(scope="module", params=["moteur D", "v1 sans butées"])
def reference(request):
    """Moteur scalaire avec la config courante (moteur D) et avec le moteur d'avant les butées."""
    with pytest.MonkeyPatch.context() as mp:
        if request.param != "moteur D":
            for key in ("JOINT_LIMITS", "BODY_LIMITS", "CLEAN_PROJECTION", "HAND_LIMITS"):
                mp.setattr(config, key, False)
        genomes = _genomes()
        scalar = [cr.Creature(g).simulate(10.0) for g in genomes]
        yield genomes, scalar, batch.evaluate(genomes)


def test_batch_hang_height_matches_scalar_bit_for_bit(reference):
    genomes, scalar, res = reference
    for k, c in enumerate(scalar):
        assert res["hang_height"][k] == c.hang_height()          # égalité exacte, pas approchée
        assert bool(res["hung"][k]) == c.hung
        if c.hung:
            assert res["hang_time"][k] == c.hang_time
        else:
            assert np.isnan(res["hang_time"][k])
        assert res["height"][k] == c.height()
    # la population couvre les trois cas : accrochée jusqu'au bout, lâchée avant la fin, jamais accrochée
    assert res["hung"].any() and not res["hung"].all()
    assert np.any(res["hang_height"] != res["height"])


def test_never_hung_keeps_final_height():
    c = cr.Creature(cr.limp_genome()).simulate(10.0)
    assert not c.hung and c.hang_time is None
    assert c.hang_height() == c.height()


def test_always_held_hangs_until_the_end():
    c = cr.Creature(_always_held_genome()).simulate(10.0)
    assert c.hung and not c.fallen
    assert c.hang_time == c.t                     # dernier sous-pas compris
    assert c.hang_height() == c.height()


def test_final_jump_does_not_count():
    """Un lâcher final ne rapporte rien : la hauteur retenue est celle du dernier instant tenu."""
    c = cr.Creature(_final_release_genome()).simulate(10.0)
    assert c.hung
    assert c.hang_time <= 9.5 + H
    assert c.hang_height() != c.height()


def test_hang_height_does_not_change_the_simulation(monkeypatch):
    """La mesure ne touche pas au moteur : mêmes positions finales et même score qu'en la neutralisant."""
    g = cr.diagonal_gait_genome()
    a = cr.Creature(g).simulate(10.0)
    monkeypatch.setattr(cr, "_LIMB_INDEX", np.array([], dtype=np.int64))   # aucune patte observée : plus de mesure
    b = cr.Creature(g).simulate(10.0)
    assert not b.hung
    np.testing.assert_array_equal(a.world.pos, b.world.pos)
    assert a.score() == b.score() and a.energy == b.energy
