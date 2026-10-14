"""Outils du duel (v2) : commande `essai` (partie, carnet, budget, rapport), fichiers d'états (empreinte, rejeu des
champions de l'évolution) et vérification d'une partie sur la plateforme officielle."""
import json
import os

import numpy as np
import pytest

import config
from evo import batch
from evo import creature as cr
from evo import essai
from evo import etats
from evo import genome_json as gj
from evo import physics

pytestmark = pytest.mark.skipif(not physics.HAVE_NUMBA, reason="numba non installé")

SECTIONS = ("1. Résultat", "2. Trajectoire", "3. Chute", "4. Prises", "5. Articulations", "6. Corps")


def _genome_file(tmp_path, data=None, name="g.json"):
    path = tmp_path / name
    path.write_text(gj.texte_json(gj.exemple(2) if data is None else data), encoding="utf-8")
    return str(path)


def _never_hung():
    data = gj.exemple(2)
    for pose in data["poses"]:
        pose["prises"] = {k: False for k in pose["prises"]}
    return data


@pytest.fixture(scope="module")
def partie(tmp_path_factory):
    """Une partie de deux essais : l'exemple, puis un génome qui ne s'accroche jamais."""
    tmp = tmp_path_factory.mktemp("duel")
    d = str(tmp / "P_test")
    first = essai.jouer(_genome_file(tmp), 2, partie=d, hypothese="Allure diagonale de l'exemple.", log=lambda *_: None)
    second = essai.jouer(_genome_file(tmp, _never_hung(), "jamais.json"), 2, partie=d, hypothese="Sans aucune prise.",
                         log=lambda *_: None)
    return d, first, second


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def test_partie_files_numbering_and_logbook(partie):
    d, first, second = partie
    assert os.path.basename(first) == "essai_001" and os.path.basename(second) == "essai_002"
    for f in ("genome.json", "rapport.txt", "resultat.json", "etats.json"):
        assert os.path.exists(os.path.join(first, f))
    info = _load(os.path.join(d, "partie.json"))
    assert info["manche"] == 2 and info["budget_annonce"] == 50 and info["budget_max"] == 200
    carnet = open(os.path.join(d, "carnet.md"), encoding="utf-8").read()
    assert carnet.index("Hypothèse : Allure diagonale") < carnet.index("Résultat : hauteur accrochée")
    assert carnet.index("## Essai 001") < carnet.index("## Essai 002")


def test_report_order_and_content(partie):
    _, first, second = partie
    text = open(os.path.join(first, "rapport.txt"), encoding="utf-8").read()
    positions = [text.index(s) for s in SECTIONS]
    assert positions == sorted(positions)
    res = _load(os.path.join(first, "resultat.json"))
    assert len(res["mesures"]["trajectoire"]) == 21                      # 0 à 10 s, toutes les 0,5 s
    assert "dernière prise tenue à" in text and "Pas de chute." in text
    assert "évolution" not in text.lower()                                # aucune comparaison avec les autres joueurs
    assert len(text.split()) < 700
    text2 = open(os.path.join(second, "rapport.txt"), encoding="utf-8").read()
    assert "(jamais accrochée : hauteur à 10 s)" in text2 and "touche le sol" in text2
    res2 = _load(os.path.join(second, "resultat.json"))["resultat"]
    assert res2["jamais_accrochee"] and res2["hauteur_accrochee"] == res2["hauteur_10s"] and res2["tombee"]


def test_result_notes_the_platform(partie):
    _, first, _ = partie
    res = _load(os.path.join(first, "resultat.json"))
    plat = res["plateforme"]
    assert plat["id"] == etats.plateforme_id()
    assert res["officiel"] == (plat["id"] == config.DUEL_PLATEFORME_OFFICIELLE)
    assert res["verification"] is None
    text = open(os.path.join(first, "rapport.txt"), encoding="utf-8").read()
    assert f"Plateforme : {plat['libelle']}" in text
    if not res["officiel"]:
        assert essai.MARQUE_ECART + "pas encore connu" in text


def test_result_matches_the_batched_evaluator(partie):
    _, first, _ = partie
    genome, _, _ = gj.charger(os.path.join(first, "genome.json"), 2)
    res = _load(os.path.join(first, "resultat.json"))["resultat"]
    b = batch.evaluate([genome])
    assert res["hauteur_accrochee"] == b["hang_height"][0] and res["hauteur_10s"] == b["height"][0]
    assert res["energie"] == b["energy"][0]


def test_states_file_and_fingerprint(partie):
    _, first, _ = partie
    path = os.path.join(first, "etats.json")
    head, imgs, fp = etats.lire(path)
    assert etats.verifier_empreinte(path)
    assert fp == _load(os.path.join(first, "resultat.json"))["empreinte_etats"]
    assert imgs["positions"].shape == (601, 15 + config.TAIL_SEGMENTS, 2)
    assert imgs["prises"].shape == (601, 4) and imgs["activations"].shape == (601, 16)
    assert np.all(imgs["activations"] >= 0)
    assert head["images_par_seconde"] == 60 and len(head["points"]) == 27 and len(head["muscles"]) == 16
    assert len(head["os"]) == 13 + 1 + config.TAIL_SEGMENTS and len(head["liens_invisibles"]) == 6
    assert head["source"] == {"type": "essai", "partie": "P_test", "essai": 1, "manche": 2}
    assert head["genome"] == gj.exemple(2) and "blender" in head["axes"]
    # une simulation refaite donne la même empreinte ; une image modifiée en donne une autre
    genome = gj.depuis_json(gj.exemple(2), 2)
    _, again = etats.simuler(genome)
    assert etats.empreinte(again) == fp
    again["positions"][300, 0, 0] += 1e-12
    assert etats.empreinte(again) != fp


def test_refusals_consume_no_trial(tmp_path, monkeypatch):
    d = str(tmp_path / "P")
    g = _genome_file(tmp_path)
    with pytest.raises(essai.EssaiRefuse, match="hypothèse"):
        essai.jouer(g, 2, partie=d, hypothese=" ", log=lambda *_: None)
    bad = gj.exemple(2)
    bad["periode_s"] = 99
    with pytest.raises(gj.GenomeInvalide):
        essai.jouer(_genome_file(tmp_path, bad, "bad.json"), 2, partie=d, hypothese="h", log=lambda *_: None)
    assert not os.path.exists(d)                                          # rien n'est écrit, aucun essai consommé
    monkeypatch.setattr(config, "DUEL_BUDGET_MAX", 1)
    essai.jouer(g, 2, partie=d, hypothese="h", log=lambda *_: None)
    with pytest.raises(essai.EssaiRefuse, match="budget épuisé"):
        essai.jouer(g, 2, partie=d, hypothese="h", log=lambda *_: None)
    with pytest.raises(essai.EssaiRefuse, match="manche 2, pas de la manche 1"):
        essai.jouer(_genome_file(tmp_path, gj.exemple(1), "m1.json"), 1, partie=d, hypothese="h", log=lambda *_: None)


def test_official_platform_is_configurable(tmp_path, monkeypatch):
    """Basculer la plateforme officielle (par ex. vers WSL) ne demande qu'une constante de config.py."""
    monkeypatch.setattr(config, "DUEL_PLATEFORME_OFFICIELLE", etats.plateforme_id())
    out = essai.jouer(_genome_file(tmp_path), 2, sortie=str(tmp_path / "e"), log=lambda *_: None)
    res = _load(os.path.join(out, "resultat.json"))
    assert res["officiel"] and res["plateforme"]["officielle"]
    text = open(os.path.join(out, "rapport.txt"), encoding="utf-8").read()
    assert ", officielle." in text and essai.MARQUE_ECART not in text


def test_partie_verification_and_integration(partie, tmp_path):
    d, first, _ = partie
    rows = essai.verifier_partie(d, str(tmp_path / "verif"), log=lambda *_: None)
    assert len(rows) == 2
    for row in rows:                                   # même plateforme : écart nul, états identiques
        assert row["ecart_hauteur_accrochee"] == 0.0 and row["etats_identiques"] and not row["chute_differente"]
    out = tmp_path / "verif" / "P_test" / "essai_001"
    for f in ("resultat.json", "rapport.txt", "rapport_officiel.txt", "etats_officiels.json"):
        assert (out / f).exists()
    assert (tmp_path / "verif" / "P_test" / "verification.csv").exists()
    text = (out / "rapport.txt").read_text(encoding="utf-8")
    if essai.MARQUE_ECART in open(os.path.join(first, "rapport.txt"), encoding="utf-8").read():
        assert essai.MARQUE_ECART + "aucun" in text
    assert essai.integrer(str(tmp_path / "verif"), d, log=lambda *_: None) == 2
    res = _load(os.path.join(first, "resultat.json"))
    assert res["verification"]["identique"] and res["verification"]["empreinte_etats"] == res["empreinte_etats"]
    assert os.path.exists(os.path.join(d, "verification.csv"))


def test_observed_creature_does_not_change_the_simulation():
    genome = gj.depuis_json(gj.exemple(2), 2)
    a = cr.Creature(genome).simulate(10.0)
    b, _, _ = essai.executer(genome)
    np.testing.assert_array_equal(a.world.pos, b.world.pos)
    assert a.hang_height() == b.hang_height() and a.energy == b.energy
