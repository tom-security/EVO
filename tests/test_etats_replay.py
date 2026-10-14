"""Fichiers d'états des champions de l'évolution (v2) : `replay --export-etats`, même empreinte qu'un essai du même
génome, refus d'exporter un rejeu qui diverge du run."""
import json

import numpy as np
import pytest

from evo import batch
from evo import etats
from evo import evolution as ev
from evo import genome_json as gj
from evo import physics
from evo import replay as rp

pytestmark = pytest.mark.skipif(not physics.HAVE_NUMBA, reason="numba non installé")


def _tiny_run(tmp_path, genome):
    """Run d'une génération à une créature (pour Replay), résultats de l'évaluateur batché."""
    run = tmp_path / "run" / "7"
    run.mkdir(parents=True)
    with open(run / "config.json", "w") as fh:
        json.dump(ev.config_snapshot(), fh)
    pop = ev.Population.from_genomes([genome])
    res = {k: v for k, v in batch.evaluate([genome]).items() if k in ev.RESULT_KEYS}
    ev.save_generation(str(run), 0, pop, res, {"parent": np.array([0]), "is_child": np.array([False])},
                       ev.generation_stats(0, pop, res))
    return str(run), res


def test_replay_exports_the_same_states_as_a_trial(tmp_path):
    genome = gj.depuis_json(gj.exemple(2), 2)
    run, _ = _tiny_run(tmp_path, genome)
    r = rp.Replay(run, gen=0, index=0, log=None)
    assert r.ok
    fp = r.export_etats(str(tmp_path / "champion.json"))
    _, imgs = etats.simuler(genome)
    assert fp == etats.empreinte(imgs)                 # Replay et essai : la même simulation, la même empreinte
    head, _, _ = etats.lire(str(tmp_path / "champion.json"))
    assert head["source"]["type"] == "evolution" and head["graine"] == "7"
    assert head["resultat"]["hauteur_accrochee"] == r.creature.hang_height()


def test_diverging_replay_is_never_exported(tmp_path):
    genome = gj.depuis_json(gj.exemple(2), 2)
    run, res = _tiny_run(tmp_path, genome)
    pop, results, lineage, stats = ev.load_generation(run, 0)
    results["height"] = results["height"] + 0.01
    ev.save_generation(run, 0, pop, results, {k: lineage[k] for k in ("parent", "is_child")}, stats)
    r = rp.Replay(run, gen=0, index=0, log=None)
    assert not r.ok
    with pytest.raises(RuntimeError, match="divergent"):
        r.export_etats(str(tmp_path / "x.json"))
    assert not (tmp_path / "x.json").exists()
