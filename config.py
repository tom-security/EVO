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
BETA = 0.0          # [CHOIX] §1.4 — stabilisation de Baumgarte (biais = BETA·C/h) : désactivée, voir ci-dessous
N_POS_ITER = 12     # [CHOIX] §1.4 — passes de projection de position après intégration (la spec suggérait 1–3)
# Choix de la stabilisation (`python main.py debug-physics --calibrate`) :
#   banc 8 = pendu par une main 10 s ; pendule simple = 2 points, 30°, 20 s.
#   « injecté » = somme des hausses d'énergie d'un sous-pas au suivant (la gravité est conservative).
#
#   config               BETA proj  corps %  queue %  E-E0 J  injecté J  dissipé J  pendule simple ΔE/E
#   BETA seul             0.2    0    0.685    9.760  -1.992     0.5320     -2.524        +0.16 %
#   projection seule      0.0    8    0.183    0.804  -2.820     0.0000     -2.820        -3.74 %
#   les deux (phase 1)    0.2    8    0.135    0.502  -2.490     0.0000     -2.490        -3.74 %
#   projection (retenu)   0.0   12    0.129    0.590  -2.820     0.0000     -2.820        -3.74 %
#
#   Phase 1 : « les deux » retenu, car sur ce banc la projection ramène C ≈ 0 avant le sous-pas
#   suivant et Baumgarte ne corrige que le reste : aucune énergie injectée.
#   Audit de la phase 3 (evo/audit.py) : ce n'est plus vrai quand l'écart dépasse ce que les
#   passes de projection résorbent. Créature inerte lâchée à 9 m : la queue, compressée de 5 %
#   à l'impact, reçoit du biais une vitesse qui écarte ses points, pendant que la projection
#   corrige la même erreur → 7.7 J créés en 2 sous-pas (0.4 % de l'énergie de la chute).
#   Énergie créée hors muscles (créature inerte / n°35 de la graine 123 / marche écrite à la main) :
#     BETA 0.2 proj 8  : 7.689 / 0 / 0 J     BETA 0 proj 8  : 0.278 / 0 / 0 J
#     BETA 0   proj 12 : 0.138 / 0 / 0 J     BETA 0 proj 16 : 0.051 / 0 / 0 J
#   Retenu : projection seule, 12 passes. Corps plus précis qu'avant (0.129 % contre 0.135 %),
#   queue < 1 %, et la seule création restante (0.14 J sur 1 800 J) vient de la projection qui
#   décomprime la queue à l'impact. La marche écrite à la main est inchangée (+3.74 m en 10 s).
#   Reste une dissipation d'ordre h, propre à la correction des vitesses (la vitesse
#   tangente d'un sous-pas a une composante radiale au suivant, que Link() retire) :
#   ~3.7 % de l'énergie d'oscillation en 20 s à 30° (1.9 % avec SUBSTEPS 16, 0.96 % avec 32).
DAMPING = 0.0       # [CHOIX] — amortissement global des vitesses (1/s), 0 = aucun
USE_NUMBA = True    # [CHOIX] §4 — solveur de liens compilé ; False = référence Python pure
# [CHOIX] §4 — créatures simulées ensemble par cœur dans l'évaluateur batché (evo/batch.py).
# 1000 créatures × 10 s sur 4 cœurs : bloc 1 → 26.1 s, 8 → 11.6 s, 32 → 7.4 s, 64 → 4.7 s, 125 → 4.7 s.
BATCH_BLOCK = 64

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
# [DÉDUIT] §1.7 — hauteur du point de référence (centre du torse) au-dessus du sol à t = 0.
# Mesuré sur les images 03/05 : 0 m du HUD à 208 px au-dessus du haut de l'herbe, à 20.2 px/m.
# Créature inerte : départ 9 m → −7.42 m à 10 s (assise sur le bassin), départ 10.3 m → −8.71 m
# (vidéo : −7.8 à −9 m pour une créature au sol).
START_HEIGHT = 10.3
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
# ne dépend donc pas de BODY_SCALE.
# Phase 2 (allure diagonale écrite à la main, forces 1.0, période 2 s, départ 8 m) : 0.35 → +3.4 m
# en 10 s, 0.5 → +3.75 m. Phase 3b, étape 1 (génération 0, 1000 créatures, graines 0/1/2, départ 9 m,
# prise 0.5) — grille 1 :
#   TORQUE_SCALE   au sol           meilleure (score)      énergie brute méd / max
#   0.10           767/787/741      −0.0 / +2.0 / +0.1     38 / 74–80
#   0.25           724/737/700      +4.2 / +4.9 / +2.7     31 / 68–72
#   0.50           651/686/652      +6.5 / +10.1 / +5.9    31 / 73–84
#   1.50           593/635/590      +14.5 / +9.8 / +9.8    42 / 87–99
#   → TORQUE_SCALE seul ne donne pas ≈ 45 % au sol : 51 des 70 créatures au sol d'un échantillon
#     tenaient encore le mur quand un pied a touché le sol (descente « en rappel »). La part au sol
#     dépend surtout de HOLD_PROBABILITY (grille 2, ci-dessous).
# Grille 3 (départ 10.3 m, ENERGY_SCALE = 14.5 / médiane brute de la gén. 0, 30 générations, graines 0/1) :
#   couple (TS ; prise)   E_SCALE  au sol g0  pic ~0 g0  champion g30     S_MAX top10% / champion
#   0.10 ; 0.65           0.345    430 / 439  273 / 292  +7.3 / +7.0 m    4.9 / 1.2 %   0 / 0 %
#   0.25 ; 0.62 (retenu)  0.413    428 / 439  228 / 212  +14.1 / +10.9 m  4.0 / 15.6 %  12.5 / 0 %
#   0.25 ; 0.65           0.404    376 / 377  254 / 255  +11.2 / +13.2 m  7.0 / 12.8 %  0 / 0 %
#   Aucun couple ne sature (≤ 16 % des forces à ≥ 0.99·S_MAX), mais à 0.10 la grimpe plafonne
#   deux fois plus bas ; 0.25/0.62 donne ≈ 44 % au sol et le plus petit pic autour de 0 (§9 :
#   « un petit groupe »). Dans tous les runs, la meilleure de la génération 0 grimpe déjà (+1.6 à
#   +5 m), alors que le §9 dit qu'elle ne grimpe pas : à traiter avec la fitness (étape 2).
#   Refaire : python main.py train --generations 30 --seed 0 --run-dir runs/calib/ts0.25_p0.62_s0 \
#             --set TORQUE_SCALE=0.25 --set HOLD_PROBABILITY=0.62 --set ENERGY_SCALE=0.413
TORQUE_SCALE = 0.25
KP = 6.0                      # [CHOIX] §2.4 — gain PD, en force musculaire par radian d'écart
KD = 1.5                      # [CHOIX] §2.4 — amortissement PD, en force musculaire par rad/s
N_POSES = 4                   # [CHOIX] §2.4 — K poses par cycle d'horloge (3 à 8)
PERIOD_INIT = (0.5, 5.0)      # [DÉDUIT] §2.4 — période d'horloge tirée uniformément à la génération 0
PERIOD_BOUNDS = (0.3, 8.0)    # [CHOIX] §2.4 — bornes de la période (mutation, phase 3)
LENGTH_FACTOR_RANGE = (0.6, 1.4)  # [CHOIX] §2.5 — longueurs d'os = référence × BODY_SCALE × U(0.6, 1.4)
TARGET_RANGE_DEG = 90.0       # [CHOIX] §2.5 — angles cibles dans ±90° autour de la posture de repos
# [CHOIX] §2.5 — probabilité qu'une patte tienne dans une pose aléatoire. Grille 2 (génération 0,
# graines 0/1/2, au sol sur 1000) : TS 0.25 → prise 0.5 : 700–737, 0.6 : 530–542, 0.7 : 315–361 ;
# départ 10.3 m : −5 % seulement. Retenu 0.62 (voir TORQUE_SCALE, grille 3).
HOLD_PROBABILITY = 0.62
# [CHOIX] §3.2 — énergie : "torque" = Σ|force musculaire|·dt, "power" = Σ|force·vitesse angulaire|·dt
ENERGY_MODE = "torque"
# [CHOIX] §3.2 — unité de l'énergie du HUD : énergie = ENERGY_SCALE × Σ|force musculaire|·dt.
# Pur changement d'unité (aucun effet sur la dynamique), réglé après TORQUE_SCALE et HOLD_PROBABILITY :
# 14.5 / médiane brute de la génération 0 (35.1 ; graines 0/1/2 : 35.1 / 34.6 / 35.8) = 0.413.
# Génération 0 mise à l'échelle : médiane 14.5, max 29.5 / 30.4 / 29.6 (cible : médiane 13–16, max 30–38).
ENERGY_SCALE = 0.413

# Fitness (§3.2) : score = hauteur finale − FITNESS_ENERGY·énergie − FITNESS_MUSCLE·masse musculaire
# [CHOIX] §3.2 — calibré en phase 3b, étape 2 (runs de 40 générations, 1000 créatures, runs/fit/) :
#   (c_E ; c_M ; graine)  meilleure g0 h   muscle moy. g1/10/20/40   période moy. g1/10/20/40   champion g40
#   grille 1 : 0.1 ; 0.1 ; 0     +3.1 m    12.8 / 13.6 / 13.0 / 16.5  2.6 / 1.8 / 1.2 / 1.3       +13.1 m
#              0.2 ; 0.2 ; 0     +1.7 m    12.6 /  9.6 /  9.4 / 11.1  2.6 / 1.9 / 1.0 / 0.9       +13.2 m
#              0.4 ; 0.4 ; 0     −0.5 m    11.9 /  7.1 /  5.5 /  7.5  2.7 / 2.4 / 2.9 / 0.8        +5.9 m
#   grille 2 : 0.5 ; 0.4 ; 0     −0.4 m    11.6 /  7.6 /  6.1 /  7.7  2.7 / 3.5 / 1.8 / 0.8        +8.0 m
#              0.6 ; 0.4 ; 0     −0.4 m    11.5 /  7.5 /  5.1 /  1.3  2.7 / 3.6 / 2.6 / 4.0        −0.4 m
#              (et 0.8/0.4, 0.5/0.3, 0.6/0.3 : même tendance)
#   grille 3 : 0.5 ; 0.4 ; 1 / 2  la paresse gagne : muscle 1.5 / 0.6 à g40, champion −0.5 / −0.4 m
#   → avec c_M ≥ 0.3, une créature presque sans muscles (M ≈ 0.5, E ≈ 0.2) reste accrochée pour
#     rien et finit par battre les grimpeuses.
#   Re-score des populations sauvegardées + contrainte du §9 (gén. 23 : la grimpeuse h 2.3, E 4.9,
#   M 8.0 doit battre l'immobile h −0.1, E 0.5) : avec nos immobiles (M 0.5 à 3.3), la zone
#   compatible avec la phase flemmarde (c_E ≥ 0.4) se réduit à c_E 0.40–0.45 et c_M ≤ 0.10.
#   grille 4 (3 graines chacun) :
#              0.40 ; 0.05     +1.7/+4.9/+5.1  muscle min g5–15 9.2–9.4, période max 2.7–3.0 : pas de flemme
#              0.40 ; 0.10     +1.7/+4.9/+5.1  muscle min 7.6–8.9, période max 3.0–3.4 ; champion g40
#                   (retenu)                   +7.3 / +16.7 / +13.0 m (période 1.8–2.1 s), muscle 10–14
#              0.45 ; 0.05     −0.1/+4.9/+5.1  flemme sur 2 graines sur 3
#   Écarts restants au §9 : la meilleure de la génération 0 grimpe déjà sur 2 graines sur 3
#   (§9 : première grimpe vers la gén. 12), et la période ne monte qu'à 3–3.4 s (§9 : 4.5 s).
#   Contraintes du §3.2 : immobile > tombée ; champion gén. 200 (36 m, E 32.5, M 13.5) = +21.7.
#   Refaire : python main.py train --generations 40 --seed 0 --run-dir runs/fit/g4_cE0.4_cM0.1_s0 \
#             --set FITNESS_ENERGY=0.4 --set FITNESS_MUSCLE=0.1
FITNESS_ENERGY = 0.4
FITNESS_MUSCLE = 0.1

# ---------------------------------------------------------------------------
# Évolution (§3)
# ---------------------------------------------------------------------------
POP_SIZE = 1000               # [VU] §3.1 — 1000 créatures
SURVIVOR_FRACTION = 0.5       # [VU] §3.1 — les 500 meilleures survivent et ont 1 enfant chacune
SIM_DURATION = 10.0           # [VU] §3.1 — secondes simulées par créature
GENERATIONS = 200             # [VU] §3.4
P_MUT = 0.1                   # [CHOIX] §3.3 — probabilité qu'un gène continu soit muté
MUT_SIGMA_FRAC = 0.05         # [CHOIX] §3.3 — σ = 5 % de la plage d'init du gène
P_BIG = 0.05                  # [CHOIX] §3.3 — probabilité qu'une mutation soit « grosse »
BIG_FACTOR = 10.0             # [CHOIX] §3.3 — amplitude ×10 pour une grosse mutation
P_FLIP = 0.03                 # [CHOIX] §3.3 — probabilité d'inverser un booléen « tenir »
PERIOD_MUTATION = "linear"    # [CHOIX] §3.3 — "linear" (σ = 5 % de la plage) ou "log" (ratio multiplicatif)
PERIOD_LOG_SIGMA = 0.1        # [CHOIX] — mode "log" : période × exp(N(0, σ)), σ ×BIG_FACTOR si grosse
RUNS_DIR = "runs"             # [CHOIX] §8 — runs/<seed>/gen_XXXX.npz, stats.csv
HIST_RANGE = (-10, 40)        # [VU] §7.2 — histogramme 1 m de −10 à 40 m

# Audit du champion toutes les AUDIT_EVERY générations (evo/audit.py).
AUDIT_EVERY = 25              # [CHOIX]
# [CHOIX] énergie créée hors muscles tolérée, en équivalent hauteur : énergie créée / poids (m·g).
# (Avant : 1e-4 × énergie de chute ≈ 0.18 J, soit 0.7 mm ; alerte à 0.77 J = 3 mm, sans intérêt pour grimper.)
AUDIT_MAX_CREATED_HEIGHT = 0.05
AUDIT_MAX_SPEED = 80.0        # [CHOIX] m/s — point du corps (bout d'un membre de 3 m qui tourne vite)
AUDIT_MAX_TORSO_SPEED = 20.0  # [CHOIX] m/s — torse (chute libre de 9 m : 13 m/s)
AUDIT_MAX_HEIGHT = 50.0       # [CHOIX] m — hauteur plausible en 10 s (champion de la vidéo : 36 m)
AUDIT_MAX_TAIL_ERROR = 0.05   # [CHOIX] erreur de longueur de la queue tolérée (os du corps : < 1 %, §1.4)

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

# §5.3 — polices libres (OFL) versionnées dans assets/fonts/ (voir assets/fonts/README.md) ; repli sur
# FONT_SANS puis sur la police par défaut de pygame si un fichier manque (evo/fonts.py).
FONT_FILES = {
    "questrial": "assets/fonts/Questrial-Regular.ttf",       # HUD, cartons, repères (≈ Century Gothic)
    "nunito_semibold": "assets/fonts/NunitoSans-SemiBold.ttf",  # titres des slides (≈ Avenir Next Demi Bold)
}
# [≈] §5.3 — polices du système (graphes, schémas, repli) : la première disponible, sinon celle de pygame
FONT_SANS = ["avenirnext", "nunitosans", "montserrat", "dejavusans", "freesans"]
FONT_MONO = ["dejavusansmono", "liberationmono", "freemono"]

# ---------------------------------------------------------------------------
# Rendu jungle (§5, phase 4), fenêtre WINDOW_SIZE = 1280×720
# ---------------------------------------------------------------------------
# Caméra [DÉDUIT] images 03 à 06 : 20.2 px/m (cf. BODY_SCALE), tronc centré, haut de l'herbe
# (y = GROUND_Y) à 548 px. Le départ (point de référence à START_HEIGHT) est donc à
# 548 − 10.3 × 20.2 ≈ 340 px ; c'est la hauteur écran que la caméra garde quand elle suit
# (image 06 : lézard à +10 m sur la ligne « 10 m », y 336 px, sol hors champ). Elle ne descend
# jamais sous le cadrage de départ (image 04 : créature au sol, cadrage inchangé).
SCENE_SCALE = 20.2
SCENE_GROUND_PX = 548
CAMERA_LERP = 0.12            # [CHOIX] §5.6 « lerp doux » : part de l'écart rattrapée par frame (0.08 : ≈ 14 px de retard à +10 m)
# Parallaxe de chaque couche (0 = fixe à l'écran, 1 = plan de la créature). §5.6 [CHOIX] : 0 / 0.1 /
# 0.25 / 0.5 / 1.0 / 1.2. [DÉDUIT] par corrélation verticale entre les images 03→05, 03→06 et 09→08
# (décalage de caméra lu sur le grand palmier et l'agave au sol, qui suivent le sol) : silhouettes
# kaki 0.28, arbre latéral et palmiers mi-proches 0.56, canopées du premier plan et leurs branches
# 1.0 (elles restent accrochées au tronc tout en passant devant le lézard). Très lointain : non
# mesurable, valeur du §5.6.
PARALLAX = {"ciel": 0.0, "tres_lointain": 0.1, "lointain": 0.28, "mi_proche": 0.56,
            "plan": 1.0, "premier_plan": 1.0}
SCENE_LAYERS = ("ciel", "tres_lointain", "lointain", "mi_proche", "plan", "premier_plan")   # [CHOIX]
SCENE_SEED = 5                # [CHOIX] graine du décor procédural
DECOR_TOP_HUD = 50.0          # [CHOIX] ≥ 45 m (§5.6) : haut du décor en hauteur HUD ; la caméra s'y arrête
SCENE_SUPERSAMPLE = 2         # [CHOIX] décor dessiné ×2 puis réduit (anticrénelage sans jointures ; puissance de 2)
SCENE_CACHE_DIR = "cache/scene"   # [CHOIX] couches pré-rendues (non versionné)

# Ciel (§5.2) : dégradé fixe à l'écran [DÉDUIT] images 03 et 09 (même haut d'écran #7BBA77 malgré
# 23 m d'écart de caméra). Arrêts (ligne en px du cadrage standard, couleur) : les couleurs du §5.2
# (#9CC484, #C4CC8C, #DCD494, #E4D49C) placées aux lignes où les images les montrent ; le haut de
# l'écran (#7BBA77, mesuré) est plus vert que le « haut du ciel » du §5.2.
SKY_STOPS = ((0, "#7BBA77"), (95, "#9CC484"), (230, "#C4CC8C"), (310, "#DCD494"), (360, "#E4D49C"))
CLOUD_COLOR = "#FCF4D4"       # [VU] §5.2
# [DÉDUIT] images 03 et 05 : traits plats (x gauche, x droit, y haut, épaisseur) en px du cadrage standard
CLOUDS = ((228, 400, 266, 18), (846, 1040, 222, 16))

# Tronc (§5.2, §5.6) : facettes low-poly, les plus claires à gauche (lumière de la gauche).
TRUNK_COLORS = ("#9C5434", "#945434", "#944C2C", "#8C4C2C",
                "#844C2C", "#7C442C", "#74442C", "#6C3C2C")   # [VU] §5.2, de gauche (clair) à droite
TRUNK_FACET = (4.1, 5.2)      # [DÉDUIT] images 01 et 03 : 3 facettes en largeur, ~100 px de haut (largeur, hauteur en m)
TRUNK_JITTER = 0.38           # [CHOIX] décalage aléatoire des sommets (fraction de facette)
TRUNK_SHADE_JITTER = 0.7      # [CHOIX] ± crans de teinte au hasard autour de l'éclairage de gauche
TRUNK_FLARE = (3.8, 0.95)     # [DÉDUIT] image 03 : base évasée sur 3.8 m, +0.95 m de chaque côté au sol
BRANCH_COLOR = "#74442C"      # [VU] §5.2
BRANCH_FACET = "#844C2C"      # [VU] §5.2
# [DÉDUIT] images 03, 06, 09 et 40 : branches en L du tronc, qui porteront les canopées du premier
# plan (phase 4a-2) : (départ en hauteur HUD m, côté ±1, avancée m, montée m, poteau m, épaisseur m)
# [DÉDUIT] image 08 (chantier A) : au repère de 30 m, aucune autre branche ni canopée sur le tronc ou à ses
# côtés jusqu'au haut de l'écran (45.4 m) ; les deux branches suivantes (31 et 43 m jusque-là) partent donc
# au-dessus, à 46 et 58 m [CHOIX au-delà de 45 m, sans référence : côtés alternés, 12 m d'écart].
BRANCHES = ((12.0, 1, 4.9, 5.4, 6.0, 1.7), (46.0, -1, 4.6, 5.0, 6.0, 1.6), (58.0, 1, 4.9, 5.4, 6.0, 1.7))

# Sol (§5.2) : herbe dentelée, terre low-poly, rochers, touffes.
GRASS_COLORS = ("#8C9C04", "#748404")   # [VU] bande claire du haut, bande sombre du dessous
GRASS_BANDS = (1.0, 2.1, 0.45)          # [DÉDUIT] image 03 : bande claire 1.0 m, bord dentelé à 2.1 m (dents ±0.45 m)
GRASS_TEETH = (3.0, 7.0)                # [CHOIX] m entre deux pointes du bord dentelé
DIRT_COLORS = ("#74442C", "#6C3C24")    # [VU] terre, facettes et liseré sombre sous l'herbe
DIRT_FACETS = (3.0, 9.0)                # [CHOIX] largeur (m) des facettes verticales de la terre
TRUNK_SHADOW = (9.5, 0.9)               # [DÉDUIT] image 03 : ombre du tronc sur l'herbe, à droite (longueur, épaisseur m)
ROCK_COLORS = ("#C47C4C", "#9C5434", "#744424")  # [VU] facettes : claire (haut gauche), moyenne, ombre
ROCKS = ((-25.2, 2.2), (12.6, 2.0), (21.8, 0.8))   # [DÉDUIT] images 01 et 03 : (x m, largeur m ; 45 et 40 px)
TUFT_COLORS = ("#748404", "#A4B41C", "#34442C")   # [VU] touffes d'herbe
TUFTS = ((-2.9, 1.3), (5.9, 1.6), (-7.1, 0.9), (-12.4, 1.1), (19.2, 1.2), (27.5, 0.9))  # [DÉDUIT] image 03 : (x m, hauteur m)

# Arrière-plans et premier plan (§5.2, §5.6). Positions en m depuis l'axe du tronc ; hauteurs en m
# au-dessus du sol telles que vues au cadrage de départ (espace de la couche).
FAR_COLORS = ("#B4C888", "#A4BC8C")       # [DÉDUIT] images 03/09 : brume la plus lointaine ; [VU] silhouettes pâles
DISTANT_COLORS = ("#848C5C", "#7C8C5C")   # [VU] silhouettes kaki (mesuré #808C58)
MID_HILL_COLOR = "#5C6C24"                # [VU] (mesuré #586C24, images 03 et 06) : collines mi-proches
MID_PALM_COLORS = ("#3C4828", "#546428", "#6C5030")   # [DÉDUIT] image 03 : feuille sombre, éclairée, stipe (plus ternes qu'au sol)
SIDE_TREE_COLORS = ("#705430", "#54482C")            # [DÉDUIT] image 03 : tronc de l'arbre latéral, face éclairée / ombre
SIDE_CANOPY_COLORS = ("#808C24", "#98A030", "#5C6820")   # [DÉDUIT] image 03 : base, facette éclairée, dessous
PALM_COLORS = ("#34442C", "#8C9C2C", "#647C24", "#803C24")   # [VU] feuilles sombre / éclairées ; [DÉDUIT] stipe #803C24 (§5.2 : #74442C)
COCONUT_COLORS = ("#A87848", "#542C2C")    # [DÉDUIT] image 03 : noix éclairées / ombre (§5.2 : #9C5434 / #8C4C2C)
FERN_COLORS = ("#38481C", "#546020", "#98A030")   # [DÉDUIT] image 03 : feuilles d'agave sombre, moyenne, éclairée
CANOPY_COLORS = ("#A4B41C", "#C4D41C", "#6C7C14", "#4C5424")   # [VU] base, facettes éclairées, dessous, ombre
VINE_COLOR = "#6C7C14"                     # [VU] lianes (rectangles fins)
# [CHOIX] nombres d'éléments procéduraux : (arbres, palmiers) très lointains, (arbres, palmiers) lointains ;
# images 06 et 09 : beaucoup de palmiers en silhouette, peu de gros arbres
FAR_COUNTS = (6, 16)
DISTANT_COUNTS = (3, 12)
# [DÉDUIT] images 03, 05, 06, 09 : gros arbres kaki (x m, hauteur m, largeur de canopée m)
DISTANT_TREES = ((-11.5, 17.5, 10.0), (26.0, 31.0, 16.0), (-25.0, 24.0, 11.0), (9.0, 13.0, 8.0))
SIDE_TREE = (-28.6, 4.2, 9.0)             # [DÉDUIT] image 03 : arbre latéral (x m, largeur m, écart entre canopées m)
SIDE_CANOPY_SIZE = ((11.0, 20.0), (4.0, 6.5))   # [DÉDUIT] images 03 et 09 : largeur, hauteur des canopées de l'arbre latéral (m)
MID_PALMS = ((-13.0, 9.5, -6.0), (-7.8, 8.3, 9.0), (16.5, 8.6, 22.0), (-19.5, 7.0, -12.0))   # [DÉDUIT] image 03 : (x, hauteur, inclinaison °)
MID_FERNS = ((9.5, 4.9), (15.2, 3.6), (28.0, 5.9), (-22.5, 4.2), (4.0, 3.1))    # [DÉDUIT] images 03 et 06 : (x, hauteur)
PLANE_PALMS = ((24.6, 16.2, 3.0, 15.5),)  # [DÉDUIT] image 03 : grand palmier au sol (x, hauteur, inclinaison °, envergure m)
PLANE_FERNS = ((-17.2, 8.6, 11.5), (-10.5, 3.8, 4.8), (28.8, 6.2, 7.2))   # [DÉDUIT] images 03 et 06 : agaves au sol (x, hauteur, largeur)
# [DÉDUIT] images 06, 08, 09 : canopée du premier plan portée par chaque branche de BRANCHES
# (centre à cette distance de l'axe du tronc, du côté de la branche ; largeur ; hauteur, en m).
# Image 09 : x 570–1110 px, soit de −3.5 à +23.5 m : elle couvre la moitié droite du tronc.
FG_CANOPIES = ((10.0, 27.0, 12.0), (8.0, 22.0, 10.0), (10.0, 25.0, 11.0))
# [DÉDUIT] images 06, 08 et 09 (chantier A) : la canopée de la branche de 12 m va de 23.1–23.3 m à 32.3–32.6 m
# de hauteur HUD, au-dessus d'un poteau visible sur ≈ 5 m (image 06 : de 17.8 à 22.6 m) ; la phase 4 la posait
# 2.6 m au-dessus du pied du poteau, soit 2.7 m trop bas (lecture de l'image 09 corrigée).
FG_CANOPY_LIFT = 5.3

# Repères de hauteur (§5.6) : ligne blanche fine sur la largeur du tronc, libellé à gauche.
MARKER_STEP = 10.0            # [VU] §5.6 — en hauteur HUD (depuis le départ) [DÉDUIT] image 03 sans ligne à 10 m du sol
MARKER_COLOR = "#FCFCFC"      # [VU]
MARKER_FONT_PX = 50           # [DÉDUIT] image 06 : « 10 m » de 34 × 98 px d'encre → Questrial 50 (34 × 100)
MARKER_LABEL_GAP_PX = 24      # [DÉDUIT] image 06 : libellé aligné à droite, 24 px à gauche du tronc
MARKER_LINE_PX = 1            # [DÉDUIT] image 06
# [DÉDUIT] images 06, 08, 09 : un repère n'est visible qu'au franchissement (image 09 : plus de ligne 20 m
# 3.1 m ≈ 0.9 s après). Affiché au premier franchissement vers le haut de la hauteur HUD (point de
# référence), jamais redéclenché, puis estompé. [DÉDUIT] seulement quand le HUD est masqué : repères dans
# les vues sans HUD (images 06, 08), étiquette de hauteur seule dans les vues avec HUD (images 03, 05, 09).
MARKER_SHOW_S = 0.5           # [CHOIX] durée à pleine opacité (s)
MARKER_FADE_S = 0.3           # [CHOIX] durée du fondu (s)

# Cadrage de l'image 01 (t = 8:02), plus serré : pour la comparaison côte à côte uniquement.
COMPARE_T8M02_FRAMING = (28.4, 570)   # [DÉDUIT] image 01 : tronc de 349 px (px/m), haut de l'herbe à 570 px

# Lézard (§5.4), recalculé à chaque frame depuis les points.
LIZARD_LIGHT = "#5CAC24"      # [VU] §5.2 — moitié gauche (côté des points L_*, [CHOIX] côté anatomique)
LIZARD_DARK = "#4CA40C"       # [VU] §5.2 — moitié droite
# [DÉDUIT] image 02 : membres un cran plus sombres que la moitié de torse du même côté, ce qui garde la
# jonction épaule / torse lisible (§5.4 écrit #5CAC24 à gauche, #4CA40C à droite).
LIZARD_LIMB_COLORS = ("#4CA40C", "#489C0C")
LIZARD_FINGER = "#D4FC7C"     # [VU] rayons des doigts
LIZARD_PAD = "#5C9C3C"        # [VU ≈] disques au bout des doigts
LIZARD_EYE_COLOR = "#040404"  # [VU]
LIZARD_SUPERSAMPLE = 2        # [CHOIX] lézard dessiné ×2 puis réduit (puissance de 2 : smoothscale exact ; ×3 perd 2 niveaux de couleur et d'alpha)
LIZARD_LIMB_WIDTH = 0.154     # [DÉDUIT] image 01 : humérus / fémur ≈ 1/3 de la largeur des hanches (0.11), ×1.4 pour l'allure compacte de la vidéo (× colonne de référence)
LIZARD_DISTAL_RATIO = 0.7     # [VU] §5.4 — avant-bras et tibia ≈ 70 % de l'humérus et du fémur
# [DÉDUIT] image 02 : demi-largeur du torse aux épaules (× clavicule), aux hanches (× bassin) et à la
# taille (× la plus grande des deux) ; torse ovoïde lissé entre ces largeurs, le long de la colonne
LIZARD_TORSO = (1.26, 1.4, 0.82)    # ×1.4 aux épaules et aux hanches (4a-1 : 0.9, 1.0) : lézard compact
LIZARD_TAIL_BASE = 0.5        # [DÉDUIT] image 01 : demi-largeur de la queue au bassin (× demi-largeur des hanches)
LIZARD_TAIL_TAPER = 1.15      # [CHOIX] exposant de l'effilage de la queue (1 = linéaire)
# [CHOIX] dessin seulement : la queue est prolongée au-delà du dernier point jusqu'à TAIL_VISUAL_FACTOR ×
# la colonne (images 01 et 06 : queue ≈ 1.9 × le torse ; queue physique : TAIL_LENGTH_FACTOR = 1.2), avec
# une courbure amortie (×TAIL_VISUAL_DAMPING par segment) et sans passer sous le sol.
TAIL_VISUAL_FACTOR = 1.9
TAIL_VISUAL_DAMPING = 0.6
LIZARD_HEAD = (0.85, 1.55)    # [DÉDUIT] image 02 : demi-largeur (× celle des épaules), longueur / largeur
# [DÉDUIT] image 02 : œil = ellipse noire centrée à 55 % de la tête depuis le cou, demi-axes 0.11 × longueur
# de tête (le long) et 0.14 × demi-largeur de tête (en travers), centre à 0.97 × la demi-largeur locale (il dépasse)
LIZARD_EYE = (0.55, 0.11, 0.14, 0.97)
# [DÉDUIT] 5 rayons à −100, −50, 0, 50, 100° de l'axe de l'avant-bras (image 02) ; longueur jusqu'au centre
# du disque, épaisseur, diamètre du disque et de la paume, en × largeur de l'avant-bras, mesurés sur la
# scène (image 01 : rayons ≈ 2×) ; disques 1.15 → 0.8 (−30 %, vers le §5.4 : disque ≈ 30 % ; gros plan 02 : 0.65×)
LIZARD_FINGERS = ((-100.0, -50.0, 0.0, 50.0, 100.0), 1.6, 0.4, 0.8, 0.9)

# ---------------------------------------------------------------------------
# HUD de simulation (§6, phase 5a) — positions en px d'une fenêtre 1280×720
# ---------------------------------------------------------------------------
# Tailles de police Questrial calées sur la hauteur et la largeur d'encre mesurées (images 03, 09, 39).
HUD_FONT = "questrial"
HUD_BADGE_FONT_PX = 22        # [DÉDUIT] images 03/09 : « 1.3 s » 15 × 41 px d'encre (Questrial 22 : 14 × 40)
HUD_TEXT_FONT_PX = 28         # [DÉDUIT] image 03 : « Génération: 0 » 19 × 173 px (Questrial 28 : 19 × 166)
HUD_LABEL_FONT_PX = 29        # [DÉDUIT] image 09 : « 23.1 m » 20 × 82 px (Questrial 29 : 20 × 82)
HUD_BG = ("#2C242C", 217)     # [VU] §5.2 — badges : fond à ~85 % d'opacité
HUD_TEXT = "#FCFCFC"          # [VU]
# [DÉDUIT] images 03, 05, 09 : badges empilés x 14–107, hauteur 34, pas de 40 (y 14, 54, 94), coins ≈ 5 px,
# centres des icônes à x 30.5 (horloge 17–44), 31.5 (éclair 23–40), 34.5 (muscle 18–51), texte à x 54
HUD_BADGES = {"x": 14, "y": 14, "pitch": 40, "w": 94, "h": 34, "radius": 5, "icon_x": (30.5, 31.5, 34.5), "text_x": 54}
HUD_ICON_COLORS = {"horloge": "#54E4DC", "energie": "#F4D41C", "muscle": "#FC5464"}   # [VU] §5.2
# [DÉDUIT] images 03 et 09 : 3 lignes alignées à droite sur x 1264–1265, haut de l'encre à y 20, 60 et 101
HUD_TEXT_RIGHT = 1265
HUD_TEXT_TOPS = (20, 60, 101)
# [DÉDUIT] images 03, 05, 09 : étiquette de hauteur x 406–540 (h 40, coins ≈ 6), pointe de 540 à 553
# (base 26 px), soit 36 px sur le bord gauche du tronc ; centrée 4 px au-dessus du point de référence ;
# chevrons de 18 × 34 px à x 418, valeur à x 448
HUD_LABEL = {"w": 134, "h": 40, "radius": 6, "tip": 13, "tip_base": 26, "tip_on_trunk": 36, "dy": -4,
             "icon_x": 12, "text_x": 42}
HUD_LABEL_ICON = "#80D989"    # [DÉDUIT] images 03/05/09 : chevrons verts (médiane #80D989)
# Carton de génération (§6). [DÉDUIT] image 39 : la scène est délavée vers le clair (et non assombrie
# comme l'écrit le §6) : tronc #8F4E2E → #C4AEA9, ciel #CCCD8F → #E3E1C4, soit ≈ #F0ECE0 à ~60 %.
TITLE_CARD_VEIL = ("#F0ECE0", 150)
TITLE_CARD_FONT_PX = (104, 32)    # [DÉDUIT] image 39 : « Génération 0 » 73 × 587 px, sous-titre 21 × 286 px
TITLE_CARD_TOPS = (105, 202)      # [DÉDUIT] image 39 : haut de l'encre du titre et du sous-titre (centrés en x)
TITLE_CARD_HOLD_S = 1.5           # [CHOIX] durée à pleine opacité en début de replay (image 39 : entier à 0.5 s)
TITLE_CARD_FADE_S = 0.5           # [CHOIX] fondu de sortie
# Replay accéléré (§6) : icône ⏩ (deux triangles blancs) en bas à gauche
FAST_SPEED = 4                    # [CHOIX] vitesse de la touche F
FAST_ICON = (20, 686, 34, 20)     # [CHOIX] x, y, largeur, hauteur de l'icône (aucune image de référence)

# ---------------------------------------------------------------------------
# Écrans d'analyse (§7) : vue population et histogramme (phase 5b), px d'une fenêtre 1280×720
# ---------------------------------------------------------------------------
# [DÉDUIT] images 24, 26 et 28 (même fond) : gris (0–255) selon la distance au centre, normalisée par la
# demi-largeur et la demi-hauteur de l'image : 35 au centre, 24 au milieu des bords, 19 dans les coins
# (§5.2 : #1C1C1C avec vignette).
ANALYSIS_BG_STOPS = ((0.0, 35), (0.4, 34), (0.6, 31), (0.8, 28.5), (1.0, 24), (1.2, 21), (1.42, 19))
# [DÉDUIT] image 24 (génération 0) : 50 colonnes × 20 lignes, et non 40 × 25 comme l'écrit le §7.1.
POPULATION_GRID = (50, 20)
POP_ORIGIN = (67.5, 64.5)     # [DÉDUIT] image 24 : centre de la première case (en haut à gauche)
POP_PITCH = (23.43, 30.68)    # [DÉDUIT] image 24 : pas de la grille (x 67.5 → 1215.6, y 64.5 → 647.4)
# [DÉDUIT] image 24 : miniature ≈ 24 px de la tête au bout de la queue (−10.7 / +13.7 px autour du centre
# de la case) et 11 px de large ; notre lézard dessiné fait ≈ 11.4 × 5.6 m, soit 2.2 px/m. Le point de
# référence (centre du torse) est au centre de la case.
POP_MINI_SCALE = 2.2
POP_MINI_COLOR = "#7AA842"    # [DÉDUIT] image 24 : médiane du vert des miniatures (#7AA842)
# [DÉDUIT] image 24 : un point clair par main et par pied (les doigts ne se distinguent pas à cette
# taille) ; couleur et rayon (px) calés sur les pixels clairs (médiane #9FB480, 90e centile #AFC095)
POP_MINI_DOT = ("#A8BC8C", 1.1)
# [DÉDUIT] images 24 et 25 : toutes les miniatures sont tête en haut, queue vers le bas, y compris les
# ≈ 450 créatures tombées de la génération 0 ; la pose finale est donc redressée (axe PELVIS → NECK
# vertical, rotation autour du centre du torse), dans la grille seulement (ni replay ni physique).
POP_MINI_UPRIGHT = True
POP_MINI_LIFT = 100.0         # [CHOIX] pose redressée placée à 100 m du sol : la queue n'y est jamais couchée
POP_SORT_DELAY_S = 0.5        # [CHOIX] attente avant le tri animé
POP_SORT_S = 2.0              # [CHOIX] durée du tri (ease-in-out, toutes les miniatures ensemble)
# [DÉDUIT] images 26, 27 et 28 : histogramme (§7.2) dans le style de la vidéo. Zone du graphe : x de −10 m
# et de 40 m, y de 500 et de 0 (19.48 px/m, 0.96 px par créature) ; grille de 1 px tous les 5 m et tous
# les 100 ; axes (décalage en px, couleur) : bas sur y 599–600, gauche sur x 153 (lissé sur x 152) ;
# libellés blancs en Questrial : « -10.0 » centrés sous les lignes (haut de l'encre à y 610), « 500 »
# alignés à droite sur x 145, haut de l'encre 3 px au-dessus de la ligne.
HIST_VIDEO = {
    "plot": (153, 120, 1127, 600),
    "y_max": 500,                 # [VU] §7.2 — axe Y de 0 à 500
    "x_step": 5, "y_step": 100,   # [VU] §7.2
    "grid": "#5D5D5D",
    "axis_bottom": ((-1, "#C0C0C0"), (0, "#C0C0C0")),
    "axis_left": ((0, "#FFFFFF"), (-1, "#6A6A6A")),
    "label": "#FFFFFF",
    "font": "questrial",
    "font_px": 15,                # Questrial 15 : « 15.0 » 25 × 10 px d'encre (image 28 : 24 × 10)
    "x_label_top": 610,
    "y_label_right": 145,
    "y_label_dy": -3,
}

# ---------------------------------------------------------------------------
# Mode analyse biomécanique (§7.4, surcouche §5.5) et comparaison de générations (§7.5), phase 5c
# ---------------------------------------------------------------------------
# [DÉDUIT] image 11 : colonne NECK–PELVIS de 177 px à l'écran, centre du torse à y 389. Pour la colonne du
# champion de la graine 2 (2.89 m) : 61.3 px/m, 3 × la vue normale ; tronc de 754 px (x 263–1017), décor visible
# sur les bords (image 11 : tronc de x 147 à 1143, notre lézard est plus grand par rapport au tronc).
ANALYSIS_SCALE = 61.3
ANALYSIS_TORSO_PX = 389
ANALYSIS_FRONT_LAYER = False  # [CHOIX] sans premier plan : à ce zoom, une canopée cacherait toute la surcouche (images 11, 12 : aucune)
ANALYSIS_BONE = "#FCECD4"     # [VU] §5.5 — os et articulations crème (images 11, 12 : #FAECD4)
# [DÉDUIT] image 11 : largeur des os, rayon des articulations et rayon de NECK / PELVIS, × diamètre de
# l'humérus dessiné (30 px) : os de 6 px, articulations de 12 px, NECK et PELVIS de 25 px de diamètre
ANALYSIS_BONE_SIZES = (0.2, 0.2, 0.42)
ANALYSIS_MUSCLE_REST = "#FC5464"     # [VU] §5.5 — muscle relâché (image 11 : #FF5465)
ANALYSIS_MUSCLE_ACTIVE = "#FC0434"   # [VU] §5.5 — contraction à 100 % de la force max (image 11 : #FF0E3E)
ANALYSIS_FIBER = (0.22, 0.06)        # [CHOIX] fibres plus claires (images 11, 14) : part de blanc, largeur (× diamètre de l'humérus)
# [DÉDUIT] images 11, 12, 14 : formes des muscles.
# - Triangles (grand dorsal NECK–épaule–colonne, fléchisseurs de hanche PELVIS–hanche–colonne) : pointe sur la
#   colonne à depth × colonne depuis NECK / PELVIS pour une force de S_MAX, min × depth pour une force nulle
#   (image 11 : 0.51 pour un dorsal à 76 % ; image 12 : 0.34 pour des fléchisseurs à 31 %) ; bord extérieur
#   bombé (dorsal) ou creusé (fléchisseurs) de bulge × sa longueur.
# - Ovales (deltoïde sur l'épaule, fessiers sur la hanche) et fuseaux de part et d'autre de l'os (biceps /
#   triceps sur l'humérus, ischios / quadriceps sur le fémur) : début et fin (× longueur de l'os), demi-largeur
#   à S_MAX (× diamètre de l'humérus dessiné), proportionnelle à la force max évoluée (§5.5).
ANALYSIS_TRIANGLE = {"depth": 0.55, "min": 0.5, "bulge": (0.08, -0.1)}
ANALYSIS_OVAL = (-0.05, 0.5, 0.55)
ANALYSIS_SPINDLE = (0.35, 1.0, 0.45)
# [DÉDUIT] image 12 : « 31% » blanc de 82 × 29 px d'encre, traits de ≈ 5 px ; Nunito Sans SemiBold 40 (83 × 32,
# traits de 3–4 px) est plus proche de cette graisse que Questrial 44 (81 × 29, traits de 3 px). Trait de rappel
# blanc de 3 px qui s'arrête 13 px avant le texte et 6 px sous le milieu de l'encre. Texte à 280 px de l'axe du
# lézard [CHOIX] (image 12 : 200 px, mais les membres de notre champion vont jusqu'à ±230 px).
ANALYSIS_LABEL_FONT = ("nunito_semibold", 40)
ANALYSIS_LABEL_LINE = 3
ANALYSIS_LABEL_GAP = (13, 6)
ANALYSIS_LABEL_DX = 280
# [CHOIX] un libellé par muscle (valeur commune aux deux côtés, SYMMETRIC_MORPHOLOGY) : (articulation 0–3,
# sens 0 = « + » / 1 = « − », côté de l'écran +1 droite / −1 gauche, milieu de l'encre en px par rapport au centre
# du torse), dans l'ordre d'apparition (§9 : deltoïde, grand dorsal, biceps, puis la hanche ; image 12 :
# fléchisseurs à droite, 34 px au-dessus du centre du torse). Le trait va au muscle du même côté de l'écran.
ANALYSIS_LABELS = ((0, 0, 1, -190), (0, 1, -1, -150), (1, 0, 1, -112), (1, 1, -1, -72),
                   (2, 0, 1, -34), (2, 1, -1, 30), (3, 0, 1, 90), (3, 1, -1, 130))
# [CHOIX] §7.4 « un par un » : premier libellé à 1 s de replay, un de plus toutes les 1.1 s (le dernier à 8.7 s) ;
# chacun reste affiché ; son trait se déroule du muscle vers le texte pendant que le texte apparaît en fondu
ANALYSIS_LABEL_TIMES = (1.0, 1.1, 0.3)
SLOW_SPEED = 0.25             # [VU] §7.4 — ralenti ×0.25 (touche S du replay et du mode analyse, ou --slow)

COMPARE_GENS = (0, 23, 100, 200)   # [CHOIX] générations repères du §9
# [CHOIX] fantômes semi-transparents (image 37 : le tronc se voit à travers les doigts), de plus en plus opaques
# avec la génération : la plus ancienne à 0.45, la plus récente à 0.9, les autres réparties entre les deux
COMPARE_GHOST_ALPHA = (0.45, 0.9)
# [CHOIX] §7.5 (détail non montré) : tous les champions partent ensemble et sont montrés au même instant t,
# chacun à sa propre hauteur. Cadrage fixe (COMPARE_FIT) : l'échelle est calculée une fois pour que le plus grand
# écart entre les torses sur les 10 s tienne dans l'écran avec des marges (m) en haut (tête et libellé) et en bas
# (queue) ; jamais plus grande que SCENE_SCALE, arrondie à 0.1 px/m (décor mis en cache). La caméra (lerp du
# replay) vise le milieu entre le plus haut et le plus bas, bornée par ces marges ; si l'écart ne tient pas
# (COMPARE_FIT = False), le plus haut reste prioritaire.
COMPARE_FIT = True
COMPARE_MARGINS = (7.0, 7.5)
COMPARE_FRONT_LAYER = False   # [CHOIX] sans premier plan : ses canopées cacheraient les fantômes (image 37 : aucune)
# [DÉDUIT] image 37 : « Génération 200 » en Questrial 22 (146 px d'encre ; Questrial 22 : 149), souligné de 2 px
# 3 px sous l'encre, de 8 px avant à 7 px après le texte ; trait de rappel de 2 px du NECK au début du souligné,
# décalé de (87, −49) px. Un libellé par fantôme (image 37 : plusieurs libellés et traits superposés) ;
# [CHOIX] écart vertical minimal entre deux libellés : hauteur d'encre + spacing px (les plus bas descendent).
COMPARE_LABEL = {"font": ("questrial", 22), "offset": (87, -49), "underline": (2, 3, 8, 7), "line": 2, "spacing": 8}
COMPARE_LABEL_SHADOW = ("#000000", 0.35)   # [CHOIX] ombre de 1 px sous le texte et le souligné (lisibles sur un nuage blanc)
COMPARE_EXPORT_TIMES = (0.5, 2.0, 4.0, 6.4, 8.0, 10.0)   # [CHOIX] instants exportés (planche de 3 × 2, t = 0.5 s : image 37)

# ---------------------------------------------------------------------------
# Export vidéo MP4 (§10, phase 6) : images pygame → ffmpeg (libx264, yuv420p), cadence FPS
# ---------------------------------------------------------------------------
VIDEO_CRF = 18                # [CHOIX] qualité x264 (18 : pertes à peine visibles)
VIDEO_PRESET = "medium"       # [CHOIX] compromis vitesse d'encodage / taille
VIDEO_HOLD_S = 1.0            # [CHOIX] dernière image tenue en fin de vidéo
VIDEO_HIST_S = 2.0            # [CHOIX] vidéo de la vue population : histogramme après le tri

# ---------------------------------------------------------------------------
# Vue population, cycle complet (§7.1, chantier A) : apparition, tri, histogramme, élimination, enfants
# ---------------------------------------------------------------------------
# [CHOIX] Animation 1 : les colonnes de la place de calcul (indice du npz rangé en colonnes, l'ordre dans lequel
# les génomes sont passés à l'évaluateur batché) apparaissent de gauche à droite à cadence fixe, chacune en fondu.
# L'évaluateur calcule tout d'un bloc : cette cadence est une présentation, sans lien avec le temps de calcul.
POP_APPEAR_S = 2.5
POP_FADE_S = 0.15
POP_PAUSE_S = 0.6             # [CHOIX] pause entre deux phases
POP_CYCLE_HIST_S = 2.0        # [CHOIX] histogramme entre le tri et l'élimination (vidéo : t = 11:12 puis 11:20)
# [CHOIX] Animation 3 : les perdantes (cases 500 à 999) disparaissent colonne par colonne, de gauche à droite, d'un
# bloc (image 25 : colonnes 0 à 5 du bas déjà vides, les autres intactes) ; puis l'enfant de la survivante de rang j
# apparaît de même dans la case 500 + j, juste sous son parent, dans sa posture de repos (pas encore évalué).
POP_ELIM_S = 1.5
POP_CHILD_S = 1.5
