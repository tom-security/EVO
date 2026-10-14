"""Courbes du duel (v2, GECKO-10) : réévaluation des runs d'évolution (garde-fou au bit près) et hasard pur."""
import csv
import json
import os

import numpy as np
import pytest

import config
from evo import batch
from evo import courbes
from evo import creature as cr
from evo import evolution as ev
from evo import physics

pytestmark = pytest.mark.skipif(not physics.HAVE_NUMBA, reason="numba non installé")


@pytest.fixture
def config_intacte():
    """courbe_evolution applique la config du run : on rétablit celle du module après le test."""
    snap = ev.config_snapshot()
    yield
    ev.apply_config(snap, strict=False)
    cr._torque_unit.cache_clear()


@pytest.fixture(scope="module")
def mini_run(tmp_path_factory):
    run = str(tmp_path_factory.mktemp("courbes") / "run" / "0")
    snap = ev.config_snapshot()
    ev.train(0, generations=3, pop_size=20, run_dir=run, audit_every=0, log=lambda *_: None)
    ev.apply_config(snap, strict=False)
    return run


def _paliers(path):
    with open(path, encoding="utf-8") as fh:
        return [(int(r["evaluations"]), float(r["meilleure_hauteur_accrochee"])) for r in csv.DictReader(fh)]


def test_evolution_curve_counts_every_evaluation_in_order(mini_run, tmp_path, config_intacte):
    res = courbes.courbe_evolution(mini_run, str(tmp_path), nom="mini", log=lambda *_: None)
    assert res["evaluations"] == 20 + 3 * 10 and res["reevaluations_identiques"]   # gén. 0, puis 10 enfants par gén.
    data = np.load(tmp_path / "mini_evaluations.npz")
    np.testing.assert_array_equal(data["generation"], [0] * 20 + [1] * 10 + [2] * 10 + [3] * 10)
    np.testing.assert_array_equal(data["indice"][20:30], np.arange(10, 20))
    # les hauteurs réévaluées sont celles du run ; la hauteur accrochée est celle de l'évaluateur batché
    pop, stored, _, _ = ev.load_generation(mini_run, 2)
    kids = np.arange(10, 20)
    np.testing.assert_array_equal(data["hauteur_10s"][30:40], stored["height"][kids])
    np.testing.assert_array_equal(data["hauteur_accrochee"][30:40],
                                  batch.evaluate(pop.take(kids).to_genomes())["hang_height"])
    steps = _paliers(tmp_path / "mini_paliers.csv")
    assert steps[0][0] == 1 and steps[-1][0] == 50
    assert all(b[1] >= a[1] for a, b in zip(steps, steps[1:]))           # courbe croissante
    assert steps[-1][1] == data["hauteur_accrochee"].max() == res["meilleure_hauteur_accrochee"]


def test_evolution_curve_stops_on_a_diverging_reevaluation(mini_run, tmp_path, config_intacte):
    bad = str(tmp_path / "run" / "0")
    os.makedirs(bad)
    for f in os.listdir(mini_run):
        with open(os.path.join(mini_run, f), "rb") as src, open(os.path.join(bad, f), "wb") as dst:
            dst.write(src.read())
    pop, results, lineage, stats = ev.load_generation(bad, 1)
    results["height"][15] += 1e-12
    ev.save_generation(bad, 1, pop, results, lineage, stats)
    with pytest.raises(RuntimeError, match="gén. 1 : 1 réévaluations"):
        courbes.courbe_evolution(bad, str(tmp_path / "out"), log=lambda *_: None)


@pytest.mark.parametrize("manche", [1, 2])
def test_random_draw_uses_the_generation_zero_generator(manche):
    genomes, graine = courbes.tirage_hasard(manche, 1, n=12)
    assert graine == config.HASARD_GRAINES[1] and config.FROZEN_BODY is False     # drapeau rétabli
    snapshot = config.FROZEN_BODY
    config.FROZEN_BODY = manche == 1
    try:
        expected = ev.random_population(np.random.default_rng([graine, 0]), 12)
    finally:
        config.FROZEN_BODY = snapshot
    got = ev.Population.from_genomes(genomes)
    for f in ev.Population.FIELDS:
        np.testing.assert_array_equal(getattr(got, f), getattr(expected, f))
    if manche == 1:
        assert np.all(got.lengths == cr.reference_lengths())
    else:
        assert not np.all(got.lengths == cr.reference_lengths())


def test_chart_groups_players_by_round(tmp_path):
    from evo import graphique_courbes as gc

    def resume(nom, source, frozen, paliers, total, manche=None):
        r = {"nom": nom, "source": source, "frozen_body": frozen, "evaluations": total, "paliers": paliers,
             "meilleure_hauteur_accrochee": paliers[-1][1]}
        if manche:
            r["manche"] = manche
        with open(tmp_path / f"{nom}_resume.json", "w", encoding="utf-8") as fh:
            json.dump(r, fh)

    for k in range(3):
        resume(f"evo_{k}", "evolution", False, [[1, -8.0], [500, 10.0 + k], [101000, 40.0 + k]], 101000)
        resume(f"fige_{k}", "evolution", True, [[1, -5.0], [2000, 20.0 + k]], 101000)
        for m in (1, 2):
            resume(f"h{m}_{k}", "hasard", m == 1, [[1, -9.0], [50, 1.0 + k]], 200, manche=m)
    data = gc.donnees(str(tmp_path))
    assert [f["manche"] for f in data["figures"]] == [1, 2]
    for f in data["figures"]:
        assert [s["cle"] for s in f["series"]] == ["evolution", "corps_fige", "hasard"]
        evo, fige, hasard = f["series"]
        assert hasard["n"][-1] == 200 and evo["n"][-1] == 101000
        i = evo["n"].index(500)
        assert evo["moy"][i] == 11.0 and evo["min"][i] == 10.0 and evo["max"][i] == 12.0
        assert evo["moy"][evo["n"].index(499)] == -8.0                     # escalier : pas d'interpolation
    assert gc.escalier({"paliers": [[1, -1.0], [10, 2.0]]}, 9) == -1.0
    page = gc.graphique(str(tmp_path), str(tmp_path / "c.html"))
    text = open(page, encoding="utf-8").read()
    assert "Manche 1" in text and "__DONNEES__" not in text and "Évolution à corps figé" in text


def test_random_curve(tmp_path):
    res = courbes.hasard(1, 0, str(tmp_path), n=15, log=lambda *_: None)
    again = courbes.hasard(1, 0, str(tmp_path / "bis"), n=15, log=lambda *_: None)
    assert res["evaluations"] == 15 and res["frozen_body"] and res["graine"] == config.HASARD_GRAINES[0]
    assert res["meilleure_hauteur_accrochee"] == again["meilleure_hauteur_accrochee"]   # déterministe
    with open(tmp_path / "hasard_m1_t0_resume.json", encoding="utf-8") as fh:
        assert json.load(fh)["source"] == "hasard"
    steps = _paliers(tmp_path / "hasard_m1_t0_paliers.csv")
    assert steps[-1][0] == 15 and all(b[1] >= a[1] for a, b in zip(steps, steps[1:]))
