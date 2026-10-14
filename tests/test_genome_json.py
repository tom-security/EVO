"""Génome JSON du duel (v2) : format lisible, bornes vérifiées avec des messages clairs, conversion vers le moteur."""
import copy
import json
import math

import numpy as np
import pytest

import config
from evo import creature as cr
from evo import genome_json as gj
from evo import joint_audit as ja


def _errors(data, manche=2):
    return gj.verifier(data, manche)


def test_example_is_valid_in_both_rounds():
    assert _errors(gj.exemple(2), 2) == []
    assert _errors(gj.exemple(1), 1) == []
    assert "os_m" not in gj.exemple(1)


def test_round_one_forbids_bone_lengths_and_uses_the_reference_body():
    errors = _errors(gj.exemple(2), 1)
    assert len(errors) == 1 and errors[0].startswith("os_m : interdit en manche 1")
    g = gj.depuis_json(gj.exemple(1), 1)
    np.testing.assert_array_equal(g.lengths, cr.reference_lengths())
    assert "génome.os_m : clé manquante" in _errors(gj.exemple(1), 2)


def test_out_of_bounds_angle_names_the_path_the_bounds_and_the_convention():
    data = gj.exemple(2)
    data["poses"][2]["angles_deg"]["gauche"]["hanche"] = -85
    (msg,) = _errors(data)
    assert msg.startswith("poses[2].angles_deg.gauche.hanche = -85 : hors de [-80, 75]")
    assert "α hanche" in msg and "vers la tête" in msg


def test_all_errors_are_reported_at_once():
    data = gj.exemple(2)
    data["periode_s"] = 0.1
    data["forces"]["biceps"] = 2.0
    data["os_m"]["tibia"] = 3.0
    data["poses"][0]["prises"]["main_g"] = "oui"
    data["poses"][1]["angles_deg"]["droite"]["genou"] = "90"
    data["inconnue"] = 1
    del data["forces"]["triceps"]
    errors = _errors(data)
    joined = "\n".join(errors)
    for part in ("periode_s = 0,1 : hors de [0,3, 8]", "forces.biceps = 2 : hors de [0, 1,6]",
                 "os_m.tibia = 3 : hors de [0,84, 1,96]", "poses[0].prises.main_g = \"oui\" : true ou false attendu",
                 "poses[1].angles_deg.droite.genou = \"90\" : un nombre est attendu", "génome.inconnue : clé inconnue",
                 "forces.triceps : clé manquante"):
        assert part in joined, part
    with pytest.raises(gj.GenomeInvalide) as exc:
        gj.depuis_json(data, 2)
    assert exc.value.erreurs == errors


def test_structure_errors():
    assert _errors([1, 2]) == ["le génome doit être un objet JSON {…}"]
    data = gj.exemple(2)
    data["poses"] = data["poses"][:3]
    assert any("exactement 4 poses" in e for e in _errors(data))
    data = gj.exemple(2)
    data["format"] = "autre"
    assert any("« gecko-genome-1 » attendu" in e for e in _errors(data))
    data = gj.exemple(2)
    data["periode_s"] = True                       # un booléen n'est pas un nombre
    assert any("periode_s = true : un nombre est attendu" in e for e in _errors(data))
    with pytest.raises(gj.GenomeInvalide, match="JSON illisible, ligne 1"):
        gj.lire("{\"format\": ", 2)


def test_bounds_accept_decimal_values_on_the_edge():
    """1,89 m (0,45 × 7 × 0,6) n'est pas exactement la borne flottante : il passe grâce à la tolérance d'arrondi."""
    data = gj.exemple(2)
    lo, _, hi = gj.bornes()["os_m"]["colonne"]
    data["os_m"]["colonne"] = 1.89
    data["os_m"]["tibia"] = 1.96
    data["poses"][0]["angles_deg"]["gauche"]["epaule"] = -60
    assert _errors(data) == []
    data["os_m"]["colonne"] = lo - 1e-6
    assert len(_errors(data)) == 1


def test_conversion_to_engine_genome():
    g = gj.depuis_json(gj.exemple(2), 2)
    assert g.period == 1.2 and g.n_poses == 4
    np.testing.assert_array_equal(g.strengths[0], g.strengths[1])           # forces symétriques
    assert g.strengths[0, 0, 0] == 0.8 and g.strengths[0, 0, 1] == 1.4       # deltoïde, grand dorsal
    assert g.strengths[0, 3, 1] == 1.2                                       # quadriceps
    assert g.muscle_mass() == pytest.approx(15.6)
    np.testing.assert_array_equal(g.holds[0], [True, False, False, True])    # main G, main D, pied G, pied D
    # angles anatomiques du JSON = cibles φ + angle de repos (conventions de joint_audit, chantier B1)
    anat = np.degrees(g.targets) + ja.rest_offsets()
    np.testing.assert_allclose(anat[0], [-40, 70, 60, 90, 70, 30, -60, 20], atol=1e-12)
    # le repos anatomique donne une cible φ nulle
    data = gj.exemple(2)
    for pose in data["poses"]:
        for side in gj.COTES:
            pose["angles_deg"][side] = {k: v for k, v in gj.rest_angles().items()}
    assert np.all(gj.depuis_json(data, 2).targets == 0.0)


def test_targets_stay_inside_the_engine_joint_limits():
    data = gj.exemple(2)
    for pose in data["poses"]:
        for side in gj.COTES:
            pose["angles_deg"][side] = {k: lo for k, (lo, hi) in gj.bornes()["angles_deg"].items()}
    g = gj.depuis_json(data, 2)
    low, high = cr.target_bounds()
    assert np.all(g.targets >= low - 1e-12) and np.all(g.targets <= high + 1e-12)


def test_round_trip_through_json():
    g = gj.depuis_json(gj.exemple(2), 2)
    back = gj.depuis_json(json.loads(gj.texte_json(gj.vers_json(g, 2))), 2)
    np.testing.assert_allclose(back.targets, g.targets, rtol=0, atol=1e-12)
    np.testing.assert_array_equal(back.lengths, g.lengths)
    np.testing.assert_array_equal(back.strengths, g.strengths)
    np.testing.assert_array_equal(back.holds, g.holds)
    asym = copy.deepcopy(g)
    asym.strengths[1, 0, 0] = 0.1
    with pytest.raises(ValueError, match="asymétriques"):
        gj.vers_json(asym)


def test_schema_lists_every_key_and_bound():
    text = gj.schema_texte()
    for key in [k for k, _, _ in gj.OS] + list(gj.FORCE_KEYS) + [k for k, _ in gj.PRISES]:
        assert key in text
    for kind, (lo, hi) in config.JOINT_LIMITS_DEG.items():
        assert f"de {lo:g} à {hi:g}" in text
    assert "12,3 m de large" in text and "2 × la somme des 8 valeurs" in text


def test_genome_command(tmp_path, capsys):
    import main
    path = tmp_path / "g.json"
    path.write_text(gj.texte_json(gj.exemple(2)), encoding="utf-8")
    main.main(["genome", "--verifier", str(path), "--manche", "2"])
    assert "génome valide (manche 2)" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        main.main(["genome", "--verifier", str(path), "--manche", "1"])
    assert "interdit en manche 1" in capsys.readouterr().out
    main.main(["genome", "--exemple", "--manche", "1"])
    assert json.loads(capsys.readouterr().out) == gj.exemple(1)


def test_example_json_is_written_with_radians_from_degrees():
    g = gj.depuis_json(gj.exemple(2), 2)
    assert g.targets[0, 0] == math.radians(-40 - 45)       # épaule gauche, pose 1 : α −40°, repos 45°
