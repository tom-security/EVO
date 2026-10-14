"""Génome lisible en JSON (v2, docs/SPEC_V2_GECKO.md) : le format qu'écrit le joueur LLM, à la main.

Muscles et os nommés, angles des poses en degrés anatomiques (conventions α/β du chantier B1), bornes vérifiées avec des
messages clairs. Format « gecko-genome-1 » :

    {"format": "gecko-genome-1",
     "periode_s": 1.2,
     "os_m": {"colonne": 3.15, ...},              (manche 2 seulement ; manche 1 : corps imposé, clé interdite)
     "forces": {"deltoide": 0.8, ...},            (8 forces, appliquées aux deux côtés, comme l'évolution)
     "poses": [{"angles_deg": {"gauche": {"epaule": -40, "coude": 70, "hanche": 60, "genou": 90},
                               "droite": {...}},
                "prises": {"main_g": true, "main_d": false, "pied_g": false, "pied_d": true}}, ... ×4]}

Conversion vers le génome du moteur (creature.Genome) : cible φ (rad) = radians(angle anatomique − angle au repos), forces
recopiées à gauche et à droite, longueurs en mètres (échelle BODY_SCALE comprise). Le JSON est la source de vérité d'un
essai : la conversion est déterministe ; l'aller-retour d'un génome de l'évolution vers le JSON n'est exact qu'à
l'arrondi près (sans usage pour le duel).
"""
import json
import math

import numpy as np

import config
from evo import creature as cr

FORMAT = "gecko-genome-1"
# (clé JSON, nom de creature.BONE_NAMES, libellé)
OS = (("colonne", "spine", "colonne vertébrale (bassin → cou)"), ("clavicule", "clavicle", "clavicule (cou → épaule)"),
      ("humerus", "humerus", "humérus (épaule → coude)"), ("avant_bras", "forearm", "avant-bras (coude → main)"),
      ("demi_bassin", "pelvis", "demi-bassin (bassin → hanche)"), ("femur", "femur", "fémur (hanche → genou)"),
      ("tibia", "tibia", "tibia (genou → pied)"))
# (clé JSON, type d'articulation de creature.JOINT_TYPES, angle, signification)
ARTICULATIONS = (
    ("epaule", "épaule", "α", "angle de l'humérus depuis le prolongement de la clavicule ; + = bras avancé vers la tête, "
                              "− = bras ramené vers la queue ; 90 = humérus parallèle à la colonne, vers la tête"),
    ("coude", "coude", "β", "flexion du coude ; 0 = bras tendu ; + = pli naturel (avant-bras tourné vers la tête)"),
    ("hanche", "hanche", "α", "angle du fémur depuis le prolongement du demi-bassin ; + = jambe avancée vers la tête, "
                              "− = jambe ramenée vers la queue"),
    ("genou", "genou", "β", "flexion du genou ; 0 = jambe tendue ; + = pli naturel (tibia tourné vers la queue)"),
)
# (clé JSON, nom, action) : muscle « + » puis muscle « − » de chaque articulation, dans l'ordre d'ARTICULATIONS
FORCES = (
    (("deltoide", "deltoïde", "avance le bras vers la tête (α épaule +)"),
     ("grand_dorsal", "grand dorsal", "ramène le bras vers la queue (α épaule −)")),
    (("biceps", "biceps", "plie le coude (β coude +)"),
     ("triceps", "triceps", "tend le coude (β coude −)")),
    (("flechisseurs_hanche", "fléchisseurs de hanche", "avancent la jambe vers la tête (α hanche +)"),
     ("fessiers", "fessiers", "ramènent la jambe vers la queue (α hanche −)")),
    (("ischios", "ischios", "plient le genou (β genou +)"),
     ("quadriceps", "quadriceps", "tendent le genou (β genou −)")),
)
FORCE_KEYS = tuple(m[0] for pair in FORCES for m in pair)
COTES = ("gauche", "droite")                                   # côté 0 et 1 de creature.JOINTS
PRISES = (("main_g", "main gauche"), ("main_d", "main droite"), ("pied_g", "pied gauche"), ("pied_d", "pied droit"))
N_POSES = 4
TOLERANCE = 1e-9    # arrondi décimal d'une valeur posée sur une borne (ex. 1,89 contre 0,45 × 7 × 0,6)

_TOP_KEYS = {1: ("format", "periode_s", "forces", "poses"), 2: ("format", "periode_s", "os_m", "forces", "poses")}


class GenomeInvalide(ValueError):
    """Génome JSON refusé ; `erreurs` : la liste de tous les problèmes, chacun avec son chemin."""

    def __init__(self, erreurs):
        self.erreurs = list(erreurs)
        super().__init__("génome invalide :\n" + "\n".join(f"  - {e}" for e in self.erreurs))


def _n(x):
    """Nombre lisible, virgule décimale."""
    return f"{x:.6g}".replace(".", ",")


def rest_angles():
    """Angle anatomique (°) de chaque articulation au repos, par clé JSON (epaule 45, coude 35, hanche −45, genou 35)."""
    rest = cr.anatomical_rest_deg()
    return {key: rest[kind] for key, kind, _, _ in ARTICULATIONS}


def bornes():
    """Bornes de chaque gène, en unités du JSON (°, m, s, force)."""
    ref = cr.reference_lengths()
    lo, hi = config.LENGTH_FACTOR_RANGE
    return {
        "periode_s": tuple(config.PERIOD_BOUNDS),
        "os_m": {key: (float(ref[i] * lo), float(ref[i]), float(ref[i] * hi)) for i, (key, _, _) in enumerate(OS)},
        "forces": (0.0, float(config.S_MAX)),
        "angles_deg": {key: tuple(config.JOINT_LIMITS_DEG[kind]) for key, kind, _, _ in ARTICULATIONS},
    }


# ---------------------------------------------------------------------------
# Vérification
# ---------------------------------------------------------------------------
def _number(value, path, lo, hi, errors, convention=""):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        errors.append(f"{path} = {json.dumps(value, ensure_ascii=False)} : un nombre est attendu")
        return None
    if not math.isfinite(value):
        errors.append(f"{path} = {value} : nombre fini attendu")
        return None
    if value < lo - TOLERANCE or value > hi + TOLERANCE:
        errors.append(f"{path} = {_n(value)} : hors de [{_n(lo)}, {_n(hi)}]" + (f" ({convention})" if convention else ""))
        return None
    return float(value)


def _keys(obj, path, expected, errors):
    """Vérifie qu'`obj` est un objet aux clés exactement `expected` (clés inconnues ou manquantes signalées) ; renvoie
    les clés attendues présentes, dont on vérifie ensuite les valeurs (None si ce n'est pas un objet)."""
    if not isinstance(obj, dict):
        errors.append(f"{path} : un objet {{…}} est attendu")
        return None
    for k in obj:
        if k not in expected:
            errors.append(f"{path}.{k} : clé inconnue (attendues : {', '.join(expected)})")
    for k in expected:
        if k not in obj:
            errors.append(f"{path}.{k} : clé manquante")
    return [k for k in expected if k in obj]


def verifier(data, manche):
    """Liste des erreurs d'un génome JSON déjà décodé (vide : génome valide) pour la manche 1 ou 2."""
    if manche not in (1, 2):
        raise ValueError(f"manche {manche} : 1 ou 2 attendu")
    errors = []
    b = bornes()
    if not isinstance(data, dict):
        return ["le génome doit être un objet JSON {…}"]
    if manche == 1 and "os_m" in data:
        errors.append("os_m : interdit en manche 1, le corps est imposé (longueurs de référence) ; retire cette clé")
    _keys({k: v for k, v in data.items() if not (manche == 1 and k == "os_m")}, "génome", _TOP_KEYS[manche], errors)
    if "format" in data and data["format"] != FORMAT:
        errors.append(f"format = {json.dumps(data['format'], ensure_ascii=False)} : « {FORMAT} » attendu")
    if "periode_s" in data:
        _number(data["periode_s"], "periode_s", *b["periode_s"], errors, "période de l'horloge, en secondes")
    if manche == 2 and "os_m" in data:
        labels = {key: label for key, _, label in OS}
        for key in _keys(data["os_m"], "os_m", list(labels), errors) or ():
            lo, ref, hi = b["os_m"][key]
            _number(data["os_m"][key], f"os_m.{key}", lo, hi, errors,
                    f"{labels[key]}, en m ; référence {_n(ref)} m, de 0,6 à 1,4 × la référence")
    if "forces" in data:
        for key in _keys(data["forces"], "forces", FORCE_KEYS, errors) or ():
            _number(data["forces"][key], f"forces.{key}", *b["forces"], errors,
                    f"force maximale du muscle, de 0 à {_n(config.S_MAX)}, appliquée aux deux côtés")
    poses = data.get("poses")
    if "poses" in data:
        if not isinstance(poses, list) or len(poses) != N_POSES:
            n = len(poses) if isinstance(poses, list) else "pas une liste"
            errors.append(f"poses : une liste de exactement {N_POSES} poses est attendue (reçu : {n})")
        else:
            joints = {key: (letter, meaning) for key, _, letter, meaning in ARTICULATIONS}
            limbs = dict(PRISES)
            for i, pose in enumerate(poses):
                p = f"poses[{i}]"
                present = _keys(pose, p, ("angles_deg", "prises"), errors) or ()
                if "angles_deg" in present:
                    for side in _keys(pose["angles_deg"], f"{p}.angles_deg", COTES, errors) or ():
                        q = f"{p}.angles_deg.{side}"
                        for key in _keys(pose["angles_deg"][side], q, list(joints), errors) or ():
                            letter, meaning = joints[key]
                            _number(pose["angles_deg"][side][key], f"{q}.{key}", *b["angles_deg"][key], errors,
                                    f"{letter} {key} en degrés : {meaning}")
                if "prises" in present:
                    for key in _keys(pose["prises"], f"{p}.prises", list(limbs), errors) or ():
                        v = pose["prises"][key]
                        if not isinstance(v, bool):
                            errors.append(f"{p}.prises.{key} = {json.dumps(v, ensure_ascii=False)} : true ou false "
                                          f"attendu ({limbs[key]} tient le tronc dans cette pose, ou non)")
    return errors


def depuis_json(data, manche):
    """Génome du moteur (creature.Genome) à partir d'un génome JSON décodé ; GenomeInvalide s'il n'est pas valide."""
    errors = verifier(data, manche)
    if errors:
        raise GenomeInvalide(errors)
    if manche == 1:
        lengths = cr.reference_lengths()
    else:
        lengths = np.array([float(data["os_m"][key]) for key, _, _ in OS])
    half = np.array([[float(data["forces"][plus[0]]), float(data["forces"][minus[0]])] for plus, minus in FORCES])
    strengths = np.stack([half, half.copy()])                       # (2, 4, 2) : mêmes forces à gauche et à droite
    rest = rest_angles()
    targets = np.array([[math.radians(float(pose["angles_deg"][side][key]) - rest[key])
                         for side in COTES for key, _, _, _ in ARTICULATIONS] for pose in data["poses"]])
    holds = np.array([[pose["prises"][key] for key, _ in PRISES] for pose in data["poses"]], dtype=bool)
    return cr.Genome(lengths, strengths, float(data["periode_s"]), targets, holds)


def lire(texte, manche):
    """(génome du moteur, JSON décodé) depuis le texte d'un fichier ; GenomeInvalide si le JSON est illisible."""
    try:
        data = json.loads(texte)
    except json.JSONDecodeError as exc:
        raise GenomeInvalide([f"JSON illisible, ligne {exc.lineno}, colonne {exc.colno} : {exc.msg}"]) from None
    return depuis_json(data, manche), data


def charger(path, manche):
    """(génome du moteur, JSON décodé, octets du fichier) d'un fichier génome."""
    with open(path, "rb") as fh:
        raw = fh.read()
    try:
        texte = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise GenomeInvalide(["le fichier doit être encodé en UTF-8"]) from None
    genome, data = lire(texte, manche)
    return genome, data, raw


def vers_json(genome, manche=2):
    """Génome du moteur → génome JSON (forces symétriques exigées ; angles à l'arrondi près)."""
    if not np.array_equal(genome.strengths[0], genome.strengths[1]):
        raise ValueError("forces asymétriques : le format JSON n'a qu'une force par muscle")
    if genome.n_poses != N_POSES:
        raise ValueError(f"{genome.n_poses} poses : le format JSON en a {N_POSES}")
    rest = rest_angles()
    data = {"format": FORMAT, "periode_s": float(genome.period)}
    if manche == 2:
        data["os_m"] = {key: float(genome.lengths[i]) for i, (key, _, _) in enumerate(OS)}
    data["forces"] = {m[0]: float(genome.strengths[0, t, s]) for t, pair in enumerate(FORCES) for s, m in enumerate(pair)}
    data["poses"] = [{"angles_deg": {side: {key: math.degrees(float(genome.targets[i, c * 4 + t])) + rest[key]
                                            for t, (key, _, _, _) in enumerate(ARTICULATIONS)}
                                     for c, side in enumerate(COTES)},
                      "prises": {key: bool(genome.holds[i, l]) for l, (key, _) in enumerate(PRISES)}}
                     for i in range(genome.n_poses)]
    return data


def exemple(manche=2):
    """Génome d'exemple (allure diagonale prudente), valide dans la manche demandée."""
    a = {"epaule": -40, "coude": 70, "hanche": 60, "genou": 90}        # bras qui tire, jambe qui remonte
    b = {"epaule": 70, "coude": 30, "hanche": -60, "genou": 20}        # bras qui remonte, jambe qui pousse
    diag_1 = {"main_g": True, "main_d": False, "pied_g": False, "pied_d": True}
    diag_2 = {"main_g": False, "main_d": True, "pied_g": True, "pied_d": False}
    tout = {"main_g": True, "main_d": True, "pied_g": True, "pied_d": True}
    data = {"format": FORMAT, "periode_s": 1.2}
    if manche == 2:
        data["os_m"] = {"colonne": 3.15, "clavicule": 0.84, "humerus": 1.54, "avant_bras": 1.40, "demi_bassin": 0.70,
                        "femur": 1.68, "tibia": 1.40}
    data["forces"] = {"deltoide": 0.8, "grand_dorsal": 1.4, "biceps": 1.0, "triceps": 0.6, "flechisseurs_hanche": 0.8,
                      "fessiers": 1.4, "ischios": 0.6, "quadriceps": 1.2}
    data["poses"] = [{"angles_deg": {"gauche": dict(a), "droite": dict(b)}, "prises": dict(diag_1)},
                     {"angles_deg": {"gauche": dict(a), "droite": dict(b)}, "prises": dict(tout)},
                     {"angles_deg": {"gauche": dict(b), "droite": dict(a)}, "prises": dict(diag_2)},
                     {"angles_deg": {"gauche": dict(b), "droite": dict(a)}, "prises": dict(tout)}]
    return data


def exemple_neutre(manche=2):
    """Génome d'exemple neutre, montrable au joueur LLM : valide, mais il ne grimpe pas et ne révèle aucune allure.
    Toutes les articulations visent leur angle de repos dans les 4 poses, toutes les prises sont relâchées (le lézard
    tombe), forces moyennes égales, horloge de 1 s, corps de référence. (`exemple()` grimpe : ne jamais le montrer.)"""
    rest = rest_angles()
    pose = {"angles_deg": {side: {key: rest[key] for key, _, _, _ in ARTICULATIONS} for side in COTES},
            "prises": {key: False for key, _ in PRISES}}
    data = {"format": FORMAT, "periode_s": 1.0}
    if manche == 2:
        data["os_m"] = {key: b[1] for key, b in bornes()["os_m"].items()}
    data["forces"] = {key: 0.8 for key in FORCE_KEYS}
    data["poses"] = [json.loads(json.dumps(pose)) for _ in range(N_POSES)]
    return data


def texte_json(data):
    """Génome JSON mis en page : une pose par bloc, lisible par un humain."""
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def schema_texte():
    """Format, bornes et conventions du génome JSON (commande `genome --schema`)."""
    b = bornes()
    rest = rest_angles()
    p_lo, p_hi = b["periode_s"]
    lines = [
        f"Génome Gecko, format « {FORMAT} » (JSON, UTF-8). Toutes les clés sont obligatoires, aucune autre n'est admise.",
        "",
        "Le lézard est vu de dessus, à plat sur un tronc vertical ; la tête est en haut au départ. Il a 4 pattes, 8",
        "articulations musclées (épaule, coude, hanche, genou, à gauche et à droite) et 16 muscles, deux par articulation.",
        "",
        "Contrôleur : une horloge de période T rejoue en boucle 4 poses, chacune pendant T/4 (pose 1 de 0 à T/4, etc.).",
        "Une pose donne l'angle visé pour chaque articulation et, pour chaque patte, si elle tient le tronc. Au début de",
        "chaque pose, une patte demandée s'accroche là où elle est, à condition d'être sur le tronc (bande verticale de",
        f"{_n(config.TRUNK_WIDTH)} m de large) et que le lézard ne soit pas tombé ; une patte non demandée lâche.",
        "Les angles visés sont suivis par un asservissement dont la force est bornée par la force maximale de chaque",
        "muscle.",
        "",
        f"periode_s : période T de l'horloge, en secondes, de {_n(p_lo)} à {_n(p_hi)}.",
        "",
        "os_m (manche 2 seulement ; en manche 1 le corps est imposé et la clé est interdite) : longueur de chaque os, en",
        "mètres, de 0,6 à 1,4 × la référence ; les deux côtés ont les mêmes longueurs.",
    ]
    for key, _, label in OS:
        lo, ref, hi = b["os_m"][key]
        lines.append(f"  {key:<12} {label} : référence {_n(ref)} m, de {_n(lo)} à {_n(hi)} m")
    lines += ["",
              f"forces : force maximale de chaque muscle, de 0 à {_n(b['forces'][1])} ; chaque valeur vaut pour le muscle "
              "gauche et le droit.",
              "La masse musculaire est la somme des 16 forces (2 × la somme des 8 valeurs)."]
    for pair in FORCES:
        for key, name, action in pair:
            lines.append(f"  {key:<20} {name} : {action}")
    lines += ["",
              f"poses : liste de {N_POSES} poses. Chaque pose : angles_deg (gauche, droite) et prises.",
              "  angles_deg.<côté>.<articulation> : angle visé en degrés anatomiques, gauche et droite en miroir :"]
    for key, _, letter, meaning in ARTICULATIONS:
        lo, hi = b["angles_deg"][key]
        lines.append(f"    {key:<7} {letter} de {_n(lo)} à {_n(hi)} (au repos : {_n(rest[key])}) : {meaning}")
    lines += ["  prises.<patte> : true si la patte tient le tronc dans cette pose, false si elle est libre ;",
              "    pattes : " + ", ".join(f"{k} ({label})" for k, label in PRISES) + ".",
              "",
              "Exemple complet, valide mais qui ne grimpe pas (articulations au repos, toutes les prises relâchées) :",
              "python main.py genome --exemple-neutre [--manche 1|2]"]
    return "\n".join(lines)
