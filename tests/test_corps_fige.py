"""Évolution témoin à corps figé (v2, manche 1, config.FROZEN_BODY) : longueurs des os aux valeurs de référence, jamais
mutées ; les autres gènes suivent les mêmes tirages qu'à corps libre ; drapeau absent d'un run = corps libre."""
import json
import os

import numpy as np
import pytest

import config
from evo import creature as cr
from evo import evolution as ev
from evo import physics

GENES = ("strengths", "period", "targets", "holds")


def _population(seed, frozen, monkeypatch, n=30):
    monkeypatch.setattr(config, "FROZEN_BODY", frozen)
    return ev.random_population(np.random.default_rng([seed, 0]), n)


def test_flag_is_off_by_default_and_for_old_runs():
    assert config.FROZEN_BODY is False
    assert ev.LEGACY_DEFAULTS["FROZEN_BODY"] is False


def test_frozen_generation_zero_has_the_reference_body_and_the_same_other_genes(monkeypatch):
    free = _population(3, False, monkeypatch)
    frozen = _population(3, True, monkeypatch)
    ref = cr.reference_lengths()
    assert np.all(frozen.lengths == ref)
    assert not np.all(free.lengths == ref)
    for f in GENES:                                       # tirage des longueurs fait puis écarté : même flux aléatoire
        np.testing.assert_array_equal(getattr(frozen, f), getattr(free, f))


def test_frozen_mutation_never_touches_the_lengths(monkeypatch):
    parents = _population(5, True, monkeypatch)
    monkeypatch.setattr(config, "P_MUT", 1.0)             # chaque gène muté : les longueurs le seraient toutes
    kids = ev.mutate(parents, np.random.default_rng(11))
    np.testing.assert_array_equal(kids.lengths, parents.lengths)
    monkeypatch.setattr(config, "FROZEN_BODY", False)
    free_kids = ev.mutate(parents, np.random.default_rng(11))
    assert not np.array_equal(free_kids.lengths, parents.lengths)
    for f in GENES:
        np.testing.assert_array_equal(getattr(kids, f), getattr(free_kids, f))


def test_flag_off_keeps_the_current_behaviour(monkeypatch):
    """Drapeau désactivé : même population et mêmes enfants qu'avant son introduction (code inchangé sur ce chemin)."""
    pop = _population(7, False, monkeypatch)
    rng = np.random.default_rng([7, 0])
    expected = ev.Population.from_genomes([cr.random_genome(rng) for _ in range(30)])
    for f in ev.Population.FIELDS:
        np.testing.assert_array_equal(getattr(pop, f), getattr(expected, f))


@pytest.mark.skipif(not physics.HAVE_NUMBA, reason="numba non installé")
def test_frozen_run_keeps_the_reference_body_and_records_the_flag(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "FROZEN_BODY", True)
    run = str(tmp_path / "corps_fige" / "0")
    ev.train(0, generations=3, pop_size=20, run_dir=run, audit_every=0, log=lambda *_: None)
    with open(os.path.join(run, "config.json")) as fh:
        assert json.load(fh)["FROZEN_BODY"] is True
    for gen in range(4):
        pop, _, _, _ = ev.load_generation(run, gen)
        assert np.all(pop.lengths == cr.reference_lengths())
    # un run sans la clé (runs d'avant GECKO-10) se relit à corps libre
    with open(os.path.join(run, "config.json")) as fh:
        snap = json.load(fh)
    del snap["FROZEN_BODY"]
    with open(os.path.join(run, "config.json"), "w") as fh:
        json.dump(snap, fh)
    assert ev.run_config(run)["FROZEN_BODY"] is False
