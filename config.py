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

# [≈] §5.3 — polices : on prend la première disponible, sinon la police par défaut de pygame
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
# [CHOIX] §5.6 — parallaxe de chaque couche (0 = fixe à l'écran, 1 = plan de la créature)
PARALLAX = {"ciel": 0.0, "tres_lointain": 0.1, "lointain": 0.25, "mi_proche": 0.5,
            "plan": 1.0, "premier_plan": 1.2}
SCENE_LAYERS = ("ciel", "plan")   # [CHOIX] couches construites (phase 4a-1 : ciel + plan)
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
BRANCHES = ((12.0, 1, 4.9, 5.4, 6.0, 1.7), (31.0, -1, 4.6, 5.0, 6.0, 1.6), (43.0, 1, 4.9, 5.4, 6.0, 1.7))

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

# Repères de hauteur (§5.6) : ligne blanche fine sur la largeur du tronc, libellé à gauche.
# [DÉDUIT] images 06, 08, 09 : un repère n'apparaît qu'une fois atteint par le lézard (jamais au-dessus de lui)
MARKER_STEP = 10.0            # [VU] §5.6 — en hauteur HUD (depuis le départ) [DÉDUIT] image 03 sans ligne à 10 m du sol
MARKER_COLOR = "#FCFCFC"      # [VU]
MARKER_FONT_PX = 46           # [DÉDUIT] image 06 : chiffres de 34 px de haut
MARKER_LABEL_GAP_PX = 24      # [DÉDUIT] image 06 : libellé aligné à droite, 24 px à gauche du tronc
MARKER_LINE_PX = 1            # [DÉDUIT] image 06

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
# scène (image 01 : rayons ≈ 2×, disques ≈ 1.3×) et un peu réduits (gros plan 02 : 0.9× et 0.65× ;
# §5.4 : disque ≈ 30 %)
LIZARD_FINGERS = ((-100.0, -50.0, 0.0, 50.0, 100.0), 1.6, 0.4, 1.15, 0.9)
