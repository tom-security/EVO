"""Topologie du lézard (§2.2) : points, os, liens de rigidité, tête et queue.

Structure statique, réutilisée en phase 2. Muscles et contrôleur viendront en phase 2.
Repère : y vers le haut, PELVIS à l'origine dans la posture de repos.
"""
import math
from dataclasses import dataclass

import numpy as np

import config
from evo.physics import World

# Les 14 points du squelette, puis la tête et la queue.
BODY_POINTS = [
    "NECK", "L_SHOULDER", "R_SHOULDER", "L_ELBOW", "R_ELBOW", "L_HAND", "R_HAND",
    "PELVIS", "L_HIP", "R_HIP", "L_KNEE", "R_KNEE", "L_FOOT", "R_FOOT",
]
(NECK, L_SHOULDER, R_SHOULDER, L_ELBOW, R_ELBOW, L_HAND, R_HAND,
 PELVIS, L_HIP, R_HIP, L_KNEE, R_KNEE, L_FOOT, R_FOOT) = range(14)
HEAD = 14
TAIL_START = 15

# Seules les 4 extrémités des pattes peuvent être fixées (§1.3).
LIMB_ENDS = (L_HAND, R_HAND, L_FOOT, R_FOOT)

# Les 13 os du §2.2 : (nom de longueur, point a, point b).
BODY_BONES = [
    ("spine", NECK, PELVIS),
    ("clavicle", NECK, L_SHOULDER), ("clavicle", NECK, R_SHOULDER),
    ("humerus", L_SHOULDER, L_ELBOW), ("humerus", R_SHOULDER, R_ELBOW),
    ("forearm", L_ELBOW, L_HAND), ("forearm", R_ELBOW, R_HAND),
    ("pelvis", PELVIS, L_HIP), ("pelvis", PELVIS, R_HIP),
    ("femur", L_HIP, L_KNEE), ("femur", R_HIP, R_KNEE),
    ("tibia", L_KNEE, L_FOOT), ("tibia", R_KNEE, R_FOOT),
]

# [CHOIX] §2.2 — liens invisibles qui rendent les ceintures rigides. Les liens
# L_SHOULDER–R_SHOULDER et L_HIP–R_HIP seraient alignés avec les clavicules / le
# bassin et ne bloqueraient aucune rotation : on triangule vers l'autre bout de la colonne.
BRACES = [
    (L_SHOULDER, PELVIS), (R_SHOULDER, PELVIS),
    (L_HIP, NECK), (R_HIP, NECK),
    (HEAD, L_SHOULDER), (HEAD, R_SHOULDER),
]


@dataclass
class Skeleton:
    names: list
    pos: np.ndarray       # (P, 2) posture de repos
    links: np.ndarray     # (L, 2)
    rest: np.ndarray      # (L,)
    is_bone: np.ndarray   # (L,)
    link_names: list      # nom de chaque lien ("spine", ..., "head", "tail", "brace")

    def make_world(self, origin=(0.0, 0.0)):
        return World(self.pos + np.asarray(origin, dtype=np.float64),
                     self.links, self.rest, self.is_bone)


def _direction(deg):
    rad = math.radians(deg)
    return np.array([math.cos(rad), math.sin(rad)])


def _mirror(deg):
    return 180.0 - deg


def build_skeleton(lengths=None, tail_segments=None, tail_length_factor=None, head_length=None):
    """Construit le squelette dans la posture de gecko du repos.

    `lengths` : dict des 7 longueurs d'os (défaut : config.BONE_REF_LENGTHS, sans BODY_SCALE).
    Les longueurs des liens de rigidité sont celles de la posture de repos.
    """
    L = dict(config.BONE_REF_LENGTHS)
    if lengths:
        L.update(lengths)
    head_length = config.HEAD_LENGTH if head_length is None else head_length
    n_tail = config.TAIL_SEGMENTS if tail_segments is None else tail_segments
    tail_factor = config.TAIL_LENGTH_FACTOR if tail_length_factor is None else tail_length_factor
    pose = config.REST_POSE_DEG

    pos = np.zeros((TAIL_START + n_tail, 2))
    pos[PELVIS] = (0.0, 0.0)
    pos[NECK] = (0.0, L["spine"])
    pos[HEAD] = pos[NECK] + (0.0, head_length)
    for side, shoulder, elbow, hand, hip, knee, foot in (
            (+1, L_SHOULDER, L_ELBOW, L_HAND, L_HIP, L_KNEE, L_FOOT),
            (-1, R_SHOULDER, R_ELBOW, R_HAND, R_HIP, R_KNEE, R_FOOT)):
        angle = (lambda d: d) if side > 0 else _mirror
        pos[shoulder] = pos[NECK] + (-side * L["clavicle"], 0.0)
        pos[elbow] = pos[shoulder] + L["humerus"] * _direction(angle(pose["humerus"]))
        pos[hand] = pos[elbow] + L["forearm"] * _direction(angle(pose["forearm"]))
        pos[hip] = pos[PELVIS] + (-side * L["pelvis"], 0.0)
        pos[knee] = pos[hip] + L["femur"] * _direction(angle(pose["femur"]))
        pos[foot] = pos[knee] + L["tibia"] * _direction(angle(pose["tibia"]))
    tail_seg = tail_factor * L["spine"] / n_tail
    for k in range(n_tail):
        pos[TAIL_START + k] = (0.0, -(k + 1) * tail_seg)

    links, is_bone, link_names = [], [], []
    for name, a, b in BODY_BONES:
        links.append((a, b)); is_bone.append(True); link_names.append(name)
    links.append((NECK, HEAD)); is_bone.append(True); link_names.append("head")
    prev = PELVIS
    for k in range(n_tail):
        links.append((prev, TAIL_START + k)); is_bone.append(True); link_names.append("tail")
        prev = TAIL_START + k
    for a, b in BRACES:
        links.append((a, b)); is_bone.append(False); link_names.append("brace")

    links = np.array(links, dtype=np.int64)
    d = pos[links[:, 1]] - pos[links[:, 0]]
    rest = np.hypot(d[:, 0], d[:, 1])
    names = BODY_POINTS + ["HEAD"] + [f"TAIL_{k + 1}" for k in range(n_tail)]
    return Skeleton(names, pos, links, rest, np.array(is_bone), link_names)
