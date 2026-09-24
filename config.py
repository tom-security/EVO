"""Paramètres du projet.

Chaque valeur porte le tag de fiabilité de la spec (docs/CODEBH_GRIMPE_SPEC.md) :
  [VU]     dit ou montré dans la vidéo
  [DÉDUIT] cohérent avec ce qui est montré, à calibrer
  [CHOIX]  choix d'implémentation (non montré)
Unités : mètres, secondes, kilogrammes « internes ». Repère physique : y vers le haut.
"""

# ---------------------------------------------------------------------------
# Moteur physique (§1)
# ---------------------------------------------------------------------------
G = 9.81            # [CHOIX] §1.2 — gravité en m/s² (le HUD affiche des mètres)
DT = 1.0 / 60.0     # [CHOIX] §1.4 — pas d'une frame
SUBSTEPS = 8        # [CHOIX] §1.4 — sous-pas par frame (dt_physique = 1/480 s)
N_ITER = 30         # [CHOIX] §1.4 — passes de Gauss-Seidel sur les vitesses des liens
BETA = 0.2          # [CHOIX] §1.4 — stabilisation de Baumgarte (biais = BETA·C/h), haut de la plage 0.1–0.2
N_POS_ITER = 8      # [CHOIX] §1.4 — passes de projection de position après intégration
# Calibrage phase 1 (banc 8, pendu par une main 10 s, erreur max os du corps / queue) :
#   BETA 0.1, N_POS_ITER 2 -> 0.31 % / 0.99 %   (limite sur la queue : segments courts et légers)
#   BETA 0.2, N_POS_ITER 8 -> 0.12 % / 0.50 %   (retenu ; la spec suggérait 1–3 passes, 8 coûte ~+25 %)
#   SUBSTEPS 16 (BETA 0.1, N_POS_ITER 2) -> 0.11 % / 0.34 %   (2× plus cher)
DAMPING = 0.0       # [CHOIX] — amortissement global des vitesses (1/s), 0 = aucun

# Méthode naïve « ressort » (vidéo aquatique), uniquement pour la comparaison du banc 4.
SPRING_K = 100.0    # [CHOIX] raideur (N/m) : assez souple pour montrer l'élasticité
SPRING_DAMP = 0.5   # [CHOIX] amortissement le long du lien (N·s/m)

# ---------------------------------------------------------------------------
# Squelette (§2.2, §2.5)
# ---------------------------------------------------------------------------
# [CHOIX] §2.5 — longueurs de référence des os (m)
BONE_REF_LENGTHS = {
    "spine": 0.45,
    "clavicle": 0.12,
    "humerus": 0.22,
    "forearm": 0.20,
    "pelvis": 0.10,
    "femur": 0.24,
    "tibia": 0.20,
}
HEAD_LENGTH = 0.10          # [CHOIX] §2.2 — os NECK–HEAD (tête purement visuelle, mais le point a une masse)
TAIL_SEGMENTS = 12          # [CHOIX] §2.2 — 10 à 14 segments
TAIL_LENGTH_FACTOR = 1.2    # [CHOIX] §2.2 — longueur totale de la queue = 1.2 × colonne

# [CHOIX] §2.2 — posture de gecko au repos : direction de chaque segment de membre
# (angle en degrés depuis +x, côté gauche ; le côté droit est le miroir).
REST_POSE_DEG = {
    "humerus": 135.0,   # bras levé vers le haut et l'extérieur
    "forearm": 100.0,
    "femur": 225.0,     # jambe vers le bas et l'extérieur
    "tibia": 260.0,
}

# ---------------------------------------------------------------------------
# Rendu des schémas pédagogiques (§5.2, images 19–23)
# ---------------------------------------------------------------------------
WINDOW_SIZE = (1280, 720)
FPS = 60

SCHEMA_BG = "#F8F8F8"           # [VU] fond des schémas
SCHEMA_POINT = "#D41424"        # [VU] point
SCHEMA_POINT_HELD = "#FC5C6C"   # [VU] point fixé (image 19, mesuré)
SCHEMA_HOLD_CROSS = "#CBCBCB"   # [VU] croix du point fixé (image 19, mesuré)
SCHEMA_BONE = "#3C3A4C"         # [VU] os
SCHEMA_VELOCITY = "#1CC41C"     # [VU] flèches de vitesse / force
SCHEMA_GRAVITY = "#F49C1C"      # [VU] flèches de gravité
SCHEMA_TEXT = "#141414"         # [CHOIX]
SCHEMA_TEXT_DIM = "#8C8C96"     # [CHOIX]
SCHEMA_BRACE = "#C8C8D2"        # [CHOIX] liens invisibles de rigidité (affichés en debug)
SCHEMA_SPRING = "#8C8C9C"       # [CHOIX] lien ressort du banc 4
SCHEMA_TRAIL = "#E4A4AC"        # [CHOIX] traînée des trajectoires

# [VU] image 20 — couleurs du schéma des masses (point, demi-os), mesurées
MASS_SCHEMA_COLORS = [
    ("#CF5155", "#DB7273"),   # rouge
    ("#5B58C8", "#7777D2"),   # bleu
    ("#29C34E", "#59CF6D"),   # vert
    ("#CE52C3", "#DB72D1"),   # magenta
]

# [≈] §5.3 — polices : on prend la première disponible, sinon la police par défaut de pygame
FONT_SANS = ["avenirnext", "nunitosans", "montserrat", "dejavusans", "freesans"]
FONT_MONO = ["dejavusansmono", "liberationmono", "freemono"]
