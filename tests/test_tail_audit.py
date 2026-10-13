"""Outils de mesure du chantier C2 (evo/tail_audit.py, evo/morphology.py, evo/planches.py), sur des signaux construits
et sur un petit run."""
import math
import os

import numpy as np
import pytest

import config
from evo import creature as cr
from evo import evolution as ev
from evo import morphology
from evo import planches
from evo import skeleton as sk
from evo import tail_audit as ta

H = config.DT / config.SUBSTEPS
T = int(round(config.SIM_DURATION / H)) + 1


@pytest.fixture(autouse=True)
def limits_on(monkeypatch):
    monkeypatch.setattr(config, "JOINT_LIMITS", True)
    monkeypatch.setattr(config, "BODY_LIMITS", True)


@pytest.fixture(scope="module")
def small_run(tmp_path_factory):
    saved = (config.JOINT_LIMITS, config.BODY_LIMITS)
    config.JOINT_LIMITS = config.BODY_LIMITS = True
    run = str(tmp_path_factory.mktemp("run") / "0")
    ev.train(0, generations=1, pop_size=24, run_dir=run, audit_every=0, log=lambda *_: None)
    config.JOINT_LIMITS, config.BODY_LIMITS = saved
    return run


def test_chatter_is_found_on_a_tail_flickering_against_the_cone():
    tau = config.TAIL_CONE_DEG
    n = np.arange(T)
    delta = (tau - 0.05 * (n % 2))[:, None]                    # contre la borne, change de sens à chaque sous-pas
    share, n_contact, amp = ta.chatter(delta, tau)
    assert n_contact == T - 2 and share > 0.99 and amp == pytest.approx(0.05)


def test_a_5_hz_swing_is_not_chatter():
    tau = config.TAIL_CONE_DEG
    t = np.arange(T) * H
    # balancement physique à 5 Hz arrêté par le bord du cône (butée inélastique : la queue y reste, puis repart)
    delta = np.clip(1.3 * tau * np.sin(2 * np.pi * 5.0 * t), -tau, tau)[:, None]
    share, n_contact, _ = ta.chatter(delta, tau)
    assert n_contact > 0 and share < 0.05


def _rest_series(c):
    return np.repeat(c.world.pos[None], T, axis=0)


def test_tail_stretched_two_percent_for_a_fifth_of_a_second_triggers_the_length_criterion():
    c = cr.Creature(cr.diagonal_gait_genome())
    P = _rest_series(c)
    last = len(c.world.pos) - 1
    bone = P[0, last] - P[0, last - 1]
    stretched = slice(1000, 1000 + int(round(0.2 / H)))
    P[stretched, last] += 0.02 * bone                           # dernier os de la queue +2 % pendant 0.2 s
    m = ta.tail_measures(P, c)
    assert m["longueur_max"] == pytest.approx(0.02, rel=1e-6)
    assert m["temps_plus_1"] == pytest.approx(0.2, abs=H) and m["temps_plus_5"] == 0.0
    assert m["os_le_plus_touche"] == config.TAIL_SEGMENTS - 1
    assert m["os_corps_max"] < 1e-12 and m["penetration_deg"]["queue"] == 0.0
    g = ta.tail_group([{"queue": m}])
    assert g["repli_longueur"] and not g["repli_oscillation"]
    assert ta.verdict_line(g).endswith("repli à 30°")
    calm = ta.tail_group([{"queue": ta.tail_measures(_rest_series(c), c)}])
    assert ta.verdict_line(calm).endswith(f"garder {config.TAIL_CONE_DEG:g}°")


def test_tail_bent_beyond_the_cone_is_measured_as_penetration_and_posture():
    c = cr.Creature(cr.diagonal_gait_genome())
    P = _rest_series(c)
    bent = config.TAIL_CONE_DEG + 4.0                          # 4° au-delà du bord du cône
    a = math.radians(bent)
    rot = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
    pelvis = P[0, sk.PELVIS]
    P[:, sk.TAIL_START:] = pelvis + (P[0, sk.TAIL_START:] - pelvis) @ rot.T   # queue entière hors du cône
    m = ta.tail_measures(P, c)
    assert m["penetration_deg"]["queue"] == pytest.approx(4.0, abs=1e-6)
    assert m["penetration_deg"]["pieds"] == 0.0 and m["penetration_deg"]["articulations"] < 1e-6
    assert m["ecart_median"] == pytest.approx(bent, abs=1e-6) and m["collee"] == 1.0
    assert m["courbure_mediane"] == pytest.approx(0.0, abs=1e-6)
    np.testing.assert_allclose(np.abs(ta.signed_tail_angles(P[:1])), bent, atol=1e-6)


def test_joints_tail_on_a_small_run(small_run):
    from evo import joint_audit as ja

    result = ja.audit(small_run, gen=1, top=2, sample=2, tail=True, log=None)
    assert result["identique"] and result["butees_corps"]
    g = result["groupes"]["meilleures"]["queue"]
    assert g["n"] == 2 and g["penetration_deg"]["queue"] <= 0.5
    lines = ja.report_lines(result)
    assert any("critère de repli" in line for line in lines)


def test_fallen_audit_on_a_small_run(small_run):
    result = ta.fallen_audit(small_run, 0, log=None)
    _, res, _, _ = ev.load_generation(small_run, 0)
    assert result["n_tombees"] == int(res["fallen"].sum()) > 0
    assert result["identique"]
    for row in result["creatures"]:
        assert row["cree_J"] >= 0.0 and row["queue_max"] >= 0.0
    assert ta.fallen_lines(result)[0].startswith("créatures tombées")


def test_trace_replays_a_creature_step_by_step(small_run, tmp_path):
    from evo import trace

    _, res, _, _ = ev.load_generation(small_run, 0)
    i = int(np.flatnonzero(res["fallen"])[0])
    r = trace.trace(small_run, 0, i, log=None, out_dir=str(tmp_path))
    assert r["identique"] and r["tombee_a"] is not None
    assert len(r["rows"]) == T - 1 and os.path.getsize(r["csv"]) > 0
    assert sum(x["cree_J"] for x in r["rows"]) == pytest.approx(r["cree_J"])
    lines = trace.summary_lines(r)
    assert lines[0].startswith("trace") and "identique" in lines[0]


def test_diag_projection_leaves_the_engine_untouched(small_run):
    from evo import diag_projection
    from evo import physics

    original, n_iter = physics.project_links, config.N_ITER
    r = diag_projection.compare(small_run, 0, 0, log=None)
    assert physics.project_links is original and config.N_ITER == n_iter   # variantes le temps de la mesure seulement
    assert r["identique"]                                      # moteur tel quel : rejeu au bit près
    assert set(diag_projection.VARIANTS) <= set(r)
    assert r["vitesse_proj"]["cree_J"] >= 0.0 and r["tel_quel"]["sorties_cone"] >= 0


def test_diag_projection_variants_do_what_they_say():
    from evo import diag_projection as dp
    from evo import physics

    with dp.variant("passes120"):
        assert cr.Creature(cr.diagonal_gait_genome()).world.n_iter == dp.PASSES
    assert cr.Creature(cr.diagonal_gait_genome()).world.n_iter == config.N_ITER
    for name, sign in (("dissipatif", -1), ("vitesse_proj", 0)):
        with dp.variant(name):
            c = cr.Creature(cr.limp_genome())                 # chute puis impact : la projection corrige beaucoup
            added = []
            for _ in range(int(round(2.0 / H))):
                c.substep(H)
                added.append(dp.LAST["ke_vitesse"])
        added = np.array(added)
        if sign < 0:
            assert added.max() <= 1e-9                         # le report dissipatif ne crée jamais d'énergie cinétique
            assert added.min() < 0.0                           # et il en retire à l'impact
        else:
            assert np.abs(added).max() > 0.0
    assert physics.project_links.__name__ == "project_links"
    with pytest.raises(ValueError):
        with dp.variant("inconnue"):
            pass


def test_diag_projection_population_and_trace_variant(small_run, tmp_path):
    from evo import diag_projection as dp
    from evo import trace

    r = dp.population(small_run, 0, "tombees", variants=("tel_quel", "dissipatif"), log=None)
    assert r["identique"] and r["n"] > 0
    assert r["variantes"]["tel_quel"]["n"] == r["variantes"]["dissipatif"]["n"] == r["n"]
    assert dp.population_lines(r)[0].startswith("diag-projection")
    _, res, _, _ = ev.load_generation(small_run, 0)
    i = int(np.flatnonzero(res["fallen"])[0])
    t = trace.trace(small_run, 0, i, log=None, out_dir=str(tmp_path), variante="dissipatif")
    assert t["csv"].endswith("_dissipatif.csv")
    assert max(x["variante_ke_vitesse_J"] for x in t["rows"]) <= 1e-9
    assert min(x["queue_dist_bassin_min_m"] for x in t["rows"]) > 0.0
    base = trace.trace(small_run, 0, i, log=None)
    more = trace.trace(small_run, 0, i, log=None, variante="passes120")   # la variante s'applique bien (N_ITER)
    assert base["identique"] and more["hauteur"] != base["hauteur"]
    b = dp.benchmark(small_run, 0, n=1, rounds=1, variants=("tel_quel", "dissipatif:courbure5"), log=None)
    assert set(b["secondes"]) == {"tel_quel", "dissipatif:courbure5"}


def test_curvature_tail_limits_replace_the_cone_without_touching_the_engine():
    from evo import diag_projection as dp

    original = cr.body_limits
    with dp.tail_limits("courbure5"):
        w = cr.Creature(cr.diagonal_gait_genome()).world
    assert cr.body_limits is original
    assert len(w.limit_lo) == 22                               # 8 articulations, 2 pieds, 12 butées de queue
    tail = sk.TAIL_START
    np.testing.assert_array_equal(w.limit_joints[10], [sk.NECK, sk.PELVIS, tail])          # cône du 1er segment
    np.testing.assert_array_equal(w.limit_joints[11], [sk.PELVIS, tail, tail + 1])          # courbure, 1re jonction
    np.testing.assert_array_equal(w.limit_joints[21], [tail + 9, tail + 10, tail + 11])     # dernière jonction
    np.testing.assert_allclose(w.limit_violation()[10:], math.radians(5.0), atol=1e-9)      # queue droite au repos
    with dp.tail_limits("courbure1"):
        m = dp.measure(cr.diagonal_gait_genome(), "dissipatif:courbure1")
    assert m["cree_J"] >= 0.0 and m["ecart_p95_deg"] < 15.0     # queue presque droite
    assert dp.split("dissipatif") == ("dissipatif", "cone")
    with pytest.raises(ValueError):
        dp.split("dissipatif:spirale")


def test_morphology_factors_stay_within_the_genome_bounds(small_run, tmp_path):
    table = morphology.factors(small_run, gens=(0, 1, 5))
    assert sorted(table) == [0, 1]                              # générations absentes ignorées
    lo, hi = config.LENGTH_FACTOR_RANGE
    for f in table.values():
        assert f.shape == (7,) and np.all((f >= lo) & (f <= hi))
    paths = morphology.export(small_run, compare=small_run, out_dir=str(tmp_path), gens=(0, 1), log=None)
    assert all(os.path.getsize(p) > 0 for p in paths)


def test_planche_puts_images_side_by_side(tmp_path):
    import pygame

    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    paths = []
    for k, size in enumerate(((200, 100), (100, 50))):
        s = pygame.Surface(size)
        s.fill((40 * (k + 1), 0, 0))
        paths.append(str(tmp_path / f"{k}.png"))
        pygame.image.save(s, paths[-1])
    sheet = planches.assemble(paths, labels=["avant", "après"])
    assert sheet.get_size() == (100 + 100 + planches.GAP, 50 + planches.CAPTION_H)   # même hauteur (50 px)
    out = planches.export(paths, str(tmp_path / "planche.png"), crop=(0.0, 0.0, 0.5, 1.0))
    assert os.path.getsize(out) > 0
    bare = planches.assemble(paths[:1], labels=[""], crop=(0.5, 0.0, 1.0, 1.0))   # recadrage seul, sans bandeau
    assert bare.get_size() == (100, 100)
