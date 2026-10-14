"""Fichiers d'états (v2, docs/SPEC_V2_GECKO.md, « Export des états pour le rendu ») : ce que la vidéo montre d'un lézard
du duel est rendu depuis ce fichier, c'est-à-dire exactement ce qui a été simulé.

- Simulation : moteur scalaire, 10 s, une image toutes les 1/60 s (601 images, t = 0 compris), comme Replay.
- En-tête : source (essai ou run), commit, plateforme, graine, cadence, unités, convention d'axes, points, os et
  longueurs, muscles, prises, génome, résultat.
- Par image : positions des 27 points, état des 4 prises, activation des 16 muscles (force musculaire du muscle,
  0 à sa force maximale), hauteur du torse et énergie cumulée.
- Empreinte : SHA-256 des tableaux par image (float64 et uint8, petit-boutiste, ordre fixe), calculée à la
  simulation ; un rejeu qui donne une autre empreinte a divergé (`verifier_empreinte`).
JSON compact ; les nombres y sont écrits sans perte (repr de Python).
"""
import hashlib
import json
import os
import platform
import subprocess
import sys

import numpy as np

import config
from evo import creature as cr
from evo import skeleton as sk

FORMAT = "gecko-etats-1"
POINT_NOMS = ("cou", "épaule G", "épaule D", "coude G", "coude D", "main G", "main D", "bassin", "hanche G", "hanche D",
              "genou G", "genou D", "pied G", "pied D", "tête")
COTE_LETTRES = ("G", "D")
PRISE_NOMS = ("main G", "main D", "pied G", "pied D")       # ordre de creature.LIMBS
LIBELLES_PLATEFORME = {"runner": "runner GitHub (ubuntu-24.04)", "windows": "Windows (PC)",
                       "wsl": "WSL (Ubuntu sous Windows)", "linux": "Linux", "darwin": "macOS"}
_RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def point_noms(n_points):
    return list(POINT_NOMS) + [f"queue {k + 1}" for k in range(n_points - sk.TAIL_START)]


def muscle_noms():
    """16 muscles, dans l'ordre des activations : pour chaque articulation de creature.JOINTS, muscle « + » puis « − »."""
    return [f"{name} {COTE_LETTRES[side]}" for side in range(2) for pair in cr.MUSCLE_NAMES for name in pair]


# ---------------------------------------------------------------------------
# Plateforme et commit
# ---------------------------------------------------------------------------
def plateforme_id():
    """« runner » (GitHub Actions), « wsl », « windows », sinon le nom du système (« linux », « darwin »)."""
    if os.environ.get("GITHUB_ACTIONS") == "true":
        return "runner"
    if sys.platform == "win32":
        return "windows"
    if sys.platform.startswith("linux"):
        try:
            with open("/proc/version") as fh:
                if "microsoft" in fh.read().lower():
                    return "wsl"
        except OSError:
            pass
        return "linux"
    return platform.system().lower()


def plateforme():
    """Plateforme d'exécution et versions ; « officielle » si c'est config.DUEL_PLATEFORME_OFFICIELLE."""
    import numba
    ident = plateforme_id()
    return {"id": ident, "libelle": LIBELLES_PLATEFORME.get(ident, ident),
            "officielle": ident == config.DUEL_PLATEFORME_OFFICIELLE,
            "plateforme_officielle": config.DUEL_PLATEFORME_OFFICIELLE,
            "systeme": platform.platform(), "python": platform.python_version(),
            "numpy": np.__version__, "numba": numba.__version__}


def commit():
    """Hash du commit du code et arbre modifié ou non (fichiers suivis) ; None hors d'un dépôt git."""
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=_RACINE, capture_output=True, text=True,
                              check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=_RACINE,
                               capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return {"hash": os.environ.get("GITHUB_SHA"), "modifie": None}
    return {"hash": head, "modifie": bool(dirty)}


# ---------------------------------------------------------------------------
# Simulation et images
# ---------------------------------------------------------------------------
def images(t, pos, held_points, activation, hauteur, energie):
    """Tableaux par image (format du fichier) à partir de ce qu'enregistrent Replay ou `simuler` : `held_points` (F, P)
    prises par point, `activation` (F, 8) force signée de chaque articulation (« + » si > 0)."""
    act = np.asarray(activation, dtype=np.float64)
    muscles = np.stack([np.maximum(act, 0.0), np.maximum(-act, 0.0)], axis=2).reshape(len(act), -1)
    return {"t": np.asarray(t, dtype=np.float64),
            "positions": np.asarray(pos, dtype=np.float64),
            "prises": np.asarray(held_points)[:, list(cr.LIMBS)].astype(bool),
            "activations": muscles,
            "hauteur": np.asarray(hauteur, dtype=np.float64),
            "energie": np.asarray(energie, dtype=np.float64)}


def empreinte(imgs):
    """SHA-256 des tableaux par image, dans un ordre et des types fixes (float64 et uint8, petit-boutistes)."""
    h = hashlib.sha256(FORMAT.encode())
    for key in ("t", "positions", "activations", "hauteur", "energie"):
        h.update(np.ascontiguousarray(imgs[key], dtype="<f8").tobytes())
    h.update(np.ascontiguousarray(imgs["prises"], dtype=np.uint8).tobytes())
    return "sha256:" + h.hexdigest()


def simuler(genome, creature=None, rappel=None):
    """Simule `genome` SIM_DURATION s au moteur scalaire (comme Replay) ; renvoie (créature finale, images).
    `creature` : créature déjà construite (sous-classe qui observe les prises, par ex.) ; `rappel(c)` : appelé après
    chaque sous-pas (mesures du rapport d'essai)."""
    c = cr.Creature(genome) if creature is None else creature
    h = config.DT / config.SUBSTEPS
    n_frames = int(round(config.SIM_DURATION / config.DT))
    n_points = len(c.world.pos)
    t = np.empty(n_frames + 1)
    pos = np.empty((n_frames + 1, n_points, 2))
    held = np.empty((n_frames + 1, n_points), bool)
    act = np.empty((n_frames + 1, len(c.activation)))
    hauteur = np.empty(n_frames + 1)
    energie = np.empty(n_frames + 1)

    def record(f):
        t[f] = c.t
        pos[f] = c.world.pos
        held[f] = c.world.held
        act[f] = c.activation
        hauteur[f] = c.height()
        energie[f] = c.energy

    record(0)
    for f in range(1, n_frames + 1):
        for _ in range(config.SUBSTEPS):
            c.substep(h)
            if rappel is not None:
                rappel(c)
        record(f)
    return c, images(t, pos, held, act, hauteur, energie)


# ---------------------------------------------------------------------------
# En-tête, écriture, lecture
# ---------------------------------------------------------------------------
def os_et_longueurs(creature):
    """Os (liens rigides visibles) et liens invisibles des ceintures, avec leurs longueurs au repos (m)."""
    names = point_noms(len(creature.world.pos))
    skel = creature.skel
    bones, braces = [], []
    for (a, b), rest, is_bone, name in zip(skel.links, skel.rest, skel.is_bone, skel.link_names):
        item = {"nom": name, "points": [int(a), int(b)], "de": names[a], "a": names[b], "longueur_m": float(rest)}
        (bones if is_bone else braces).append(item)
    return bones, braces


def resultat_creature(c):
    """Résultat d'une simulation : hauteurs, énergie, masse musculaire, chute (unités du HUD)."""
    return {"hauteur_accrochee": c.hang_height(), "jamais_accrochee": not c.hung,
            "instant_derniere_prise": c.hang_time, "hauteur_10s": c.height(), "energie": c.energy,
            "masse_musculaire": c.muscle_mass(), "tombee": bool(c.fallen)}


def entete(source, creature, genome_json=None, graine=None, resultat=None):
    """En-tête d'un fichier d'états. `source` : {"type": "essai", …} ou {"type": "evolution", …}."""
    bones, braces = os_et_longueurs(creature)
    return {
        "format": FORMAT,
        "source": source,
        "commit": commit(),
        "plateforme": plateforme(),
        "graine": graine,
        "images_par_seconde": int(round(1.0 / config.DT)),
        "duree_s": float(config.SIM_DURATION),
        "sous_pas_par_image": int(config.SUBSTEPS),
        "unites": {"longueur": "m", "temps": "s",
                   "activation": f"force musculaire du muscle, de 0 à sa force maximale (au plus {config.S_MAX:g})",
                   "energie": "unité du HUD (ENERGY_SCALE × Σ|force musculaire|·dt)"},
        "axes": {"origine": "pied du tronc, au niveau du sol : x = 0 (axe du tronc), y = 0 (sol)",
                 "x": "horizontal, vers la droite de l'écran ; le côté gauche du lézard est à x < 0",
                 "y": "vertical, vers le haut",
                 "plan": "le mur : vue de face du tronc, lézard vu de dessus ; pas de profondeur",
                 "blender": "(x, y) → (X = x, Y = 0, Z = y) : Z vertical"},
        "points": point_noms(len(creature.world.pos)),
        "os": bones,
        "liens_invisibles": braces,
        "muscles": muscle_noms(),
        "prises": list(PRISE_NOMS),
        "tronc": {"x_m": float(config.TRUNK_X), "largeur_m": float(config.TRUNK_WIDTH)},
        "hauteur_depart_m": float(config.START_HEIGHT),
        "moteur": {k: getattr(config, k) for k in ("JOINT_LIMITS", "BODY_LIMITS", "CLEAN_PROJECTION", "HAND_LIMITS",
                                                   "TAIL_CURVATURE_LIMITS", "TAIL_CONE_DEG", "SUBSTEPS")},
        "genome": genome_json,
        "resultat": resultat,
    }


def _jsonable(imgs):
    return {"t": imgs["t"].tolist(), "positions": imgs["positions"].tolist(), "prises": imgs["prises"].tolist(),
            "activations": imgs["activations"].tolist(), "hauteur": imgs["hauteur"].tolist(),
            "energie": imgs["energie"].tolist()}


def ecrire(path, head, imgs):
    """Écrit le fichier d'états ; renvoie l'empreinte."""
    fp = empreinte(imgs)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    doc = {"format": FORMAT, "entete": head, "empreinte": fp, "images": _jsonable(imgs)}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, separators=(",", ":"))
    return fp


def lire(path):
    """(en-tête, images en tableaux numpy, empreinte enregistrée)."""
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    raw = doc["images"]
    imgs = {k: np.array(raw[k], dtype=np.float64) for k in ("t", "positions", "activations", "hauteur", "energie")}
    imgs["prises"] = np.array(raw["prises"], dtype=bool)
    return doc["entete"], imgs, doc["empreinte"]


def verifier_empreinte(path):
    """True si l'empreinte recalculée depuis le fichier est celle qu'il porte (fichier intact)."""
    _, imgs, fp = lire(path)
    return empreinte(imgs) == fp
