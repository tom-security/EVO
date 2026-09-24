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
N_POS_ITER = 8      # [CHOIX] §1.4 — passes de projection de position après intégration (la spec suggérait 1–3)
# Choix de la stabilisation (`python main.py debug-physics --calibrate`) :
#   banc 8 = pendu par une main 10 s ; pendule simple = 2 points, 30°, 20 s.
#   « injecté » = somme des hausses d'énergie d'un sous-pas au suivant (la gravité est conservative).
#
#   config             BETA proj  corps %  queue %  E-E0 J  injecté J  dissipé J  pendule simple ΔE/E
#   BETA seul           0.2    0    0.685    9.760  -1.992     0.5320     -2.524        +0.16 %
#   projection seule    0.0    8    0.183    0.804  -2.820     0.0000     -2.820        -3.74 %
#   les deux (retenu)   0.2    8    0.135    0.502  -2.490     0.0000     -2.490        -3.74 %
#
#   BETA seul injecte de l'énergie (le biais ajoute une vitesse artificielle pour rattraper l'écart) et laisse
#   la queue s'étirer de ~10 %. Les deux ensemble ne corrigent pas deux fois la même erreur :
#   la projection a lieu en fin de sous-pas, donc au sous-pas suivant C ≈ 0 et Baumgarte ne
#   traite que ce que les 8 passes n'ont pas résorbé. Aucune énergie injectée, erreur la plus
#   faible, et moins de dissipation que la projection seule.
#   Reste une dissipation d'ordre h, propre à la correction des vitesses (la vitesse
#   tangente d'un sous-pas a une composante radiale au suivant, que Link() retire) :
#   ~3.7 % de l'énergie d'oscillation en 20 s à 30° (1.9 % avec SUBSTEPS 16, 0.96 % avec 32).
DAMPING = 0.0       # [CHOIX] — amortissement global des vitesses (1/s), 0 = aucun
USE_NUMBA = True    # [CHOIX] §4 — solveur de liens compilé ; False = référence Python pure

# Sol (§1.7) : ligne horizontale y = GROUND_Y, collision inélastique + frottement de Coulomb.
GROUND_Y = 0.0            # [DÉDUIT] §1.7
GROUND_FRICTION = 1.0     # [DÉDUIT] §1.7 « friction forte » : coefficient de Coulomb μ
CONTACT_MARGIN = 0.05     # [CHOIX] m — un point à moins de ça du sol entre dans le solveur de contact

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
# Échelle et monde de la créature (§1.7, §5.6)
# ---------------------------------------------------------------------------
# [DÉDUIT] Les longueurs du §2.5 ([CHOIX]) donnent un lézard de 1.1 m (tête → bout de queue).
# Les images montrent autre chose ([VU]) : les étiquettes de hauteur des images 03/04/05
# donnent 20.2 px/m (−4.9 m → y 436, −7.8 m → y 494.5, +2.3 m → y 290.5 une fois la caméra
# recalée), et le lézard y mesure ~155–170 px, soit 7.6–8.4 m ; le tronc 248 px, soit 12.3 m.
# Le champion monte aussi de 36 m en 10 s avec une horloge de 0.6 s : ~2.2 m par cycle, ce
# qui est impossible avec des pattes de 0.4 m. On garde les proportions du §2.5 et on met
# tout le corps à l'échelle ×BODY_SCALE. BODY_SCALE = 1 redonne exactement les longueurs du §2.5.
BODY_SCALE = 7.0          # [DÉDUIT] images 03–05 : lézard ≈ 7.7 m de la tête au bout de la queue
START_HEIGHT = 8.0        # [DÉDUIT] §1.7 — hauteur du point de référence au-dessus du sol à t = 0
TRUNK_X = 0.0             # [CHOIX] axe du tronc
TRUNK_WIDTH = 12.3        # [DÉDUIT] image 05 : 248 px à 20.2 px/m
FALL_CONTACT_EPS = 1e-3   # [CHOIX] m — un point du corps (hors queue) à moins de ça du sol le touche
FALL_DISABLES_HOLD = True # [DÉDUIT] §1.7 « au sol, une créature tombée reste au sol » : plus de prise

# ---------------------------------------------------------------------------
# Créature : muscles, contrôleur, génome (§2.3–2.5)
# ---------------------------------------------------------------------------
SYMMETRIC_MORPHOLOGY = True   # [DÉDUIT] §2.3 — mêmes longueurs et forces à gauche et à droite
S_MAX = 1.6                   # [CHOIX] §2.3 — force max autorisée d'un muscle (unités internes)
# [CHOIX] §2.3 — couple produit par une force musculaire de 1, en « poids × colonne » de la
# créature de référence (masse totale × G × longueur de colonne, à BODY_SCALE) : le calibrage
# ne dépend donc pas de BODY_SCALE. Réglé en phase 2 sur l'allure diagonale écrite à la main
# (forces 1.0, période 2 s) : 0.35 → +3.4 m en 10 s, 0.5 → +3.75 m, 0.75 → +3.7 m ; sous
# ~0.2 elle ne décolle pas. À recalibrer en phase 3 (§3.2).
TORQUE_SCALE = 0.5
KP = 6.0                      # [CHOIX] §2.4 — gain PD, en force musculaire par radian d'écart
KD = 1.5                      # [CHOIX] §2.4 — amortissement PD, en force musculaire par rad/s
N_POSES = 4                   # [CHOIX] §2.4 — K poses par cycle d'horloge (3 à 8)
PERIOD_INIT = (0.5, 5.0)      # [DÉDUIT] §2.4 — période d'horloge tirée uniformément à la génération 0
PERIOD_BOUNDS = (0.3, 8.0)    # [CHOIX] §2.4 — bornes de la période (mutation, phase 3)
LENGTH_FACTOR_RANGE = (0.6, 1.4)  # [CHOIX] §2.5 — longueurs d'os = référence × BODY_SCALE × U(0.6, 1.4)
TARGET_RANGE_DEG = 90.0       # [CHOIX] §2.5 — angles cibles dans ±90° autour de la posture de repos
HOLD_PROBABILITY = 0.5        # [CHOIX] §2.5 — probabilité qu'une patte tienne dans une pose aléatoire
# [CHOIX] §3.2 — énergie : "torque" = Σ|force musculaire|·dt, "power" = Σ|force·vitesse angulaire|·dt
ENERGY_MODE = "torque"

# Fitness (§3.2) : score = hauteur finale − FITNESS_ENERGY·énergie − FITNESS_MUSCLE·masse musculaire
FITNESS_ENERGY = 0.02         # [CHOIX] §3.2 — à calibrer en phase 3
FITNESS_MUSCLE = 0.05         # [CHOIX] §3.2 — à calibrer en phase 3

# ---------------------------------------------------------------------------
# Vue debug de la créature (§7.6, images 15–17)
# ---------------------------------------------------------------------------
DEBUG_BG = "#040414"          # [VU] fond bleu nuit
DEBUG_GRID = "#5C5C6C"        # [VU] grille fine
DEBUG_GRID_STEP = 1.0         # [VU ≈] m par carreau
DEBUG_TRUNK = "#0E0E2A"       # [CHOIX] bande du tronc (là où une patte peut tenir)
DEBUG_GROUND = "#3C3C4C"      # [CHOIX] sol
DEBUG_BONE = "#FCECD4"        # [VU] os et articulations (crème)
DEBUG_MUSCLE_REST = "#FC5464" # [VU] muscle au repos
DEBUG_MUSCLE_ACTIVE = "#FC0434"  # [VU] muscle contracté
DEBUG_HELD = "#54E4DC"        # [CHOIX] patte fixée au mur
DEBUG_TEXT = "#FCFCFC"        # [VU]
DEBUG_TEXT_DIM = "#8C8C9C"    # [CHOIX]
DEBUG_SCALE = 32.0            # [CHOIX] px par mètre dans la vue debug

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
