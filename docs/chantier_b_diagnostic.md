# Chantier B, phase B1 : diagnostic des angles articulaires

Le moteur (points + liens, §1) n'a aucune contrainte d'angle entre deux os qui partagent un point : seules les
cibles du génome sont bornées (±90° autour du repos, §2.5). Les membres peuvent donc se croiser à l'épaule et à la
hanche, et les coudes et genoux plier dans le mauvais sens. Ce document mesure ce que font les créatures déjà
entraînées et fixe les butées que la phase B2 appliquera dans le moteur. **B1 ne touche pas au moteur.**

Reproduire les mesures : `python main.py joints --seed S --gen G [--top N] [--sample N] [--export DIR]`
(`evo/joint_audit.py`). Rejeu au moteur scalaire avec la config du run, hauteurs vérifiées identiques au run
(1e-9 m), un angle par sous-pas (4 800 par grimpe de 10 s), côtés gauche et droit réunis. Mesuré ici, pour
les graines 0, 1 et 2 : `--gen 200 --top 50` et `--gen 0 --sample 50` (303 grimpes, ≈ 5 min).
Depuis B2, ces runs sans butées sont dans `runs/legacy_no_limits/S` (et `runs/S` contient les runs avec butées) :
pour refaire ces mesures, `python main.py joints --run-dir runs/legacy_no_limits/S …`.

## Conventions d'angle

Le plan simulé est celui du mur : c'est une **vue de dessus** du lézard (pas une vue de côté). Gauche et droite
sont mesurés en miroir.

- **Épaule, hanche : α**, angle de l'humérus (du fémur) depuis l'axe latéral du corps, c'est-à-dire le
  prolongement de la clavicule (du demi-bassin). + = protraction (vers la tête), − = rétraction (vers la queue).
  ±90° : os parallèle à la colonne ; au-delà, il passe du côté de l'axe du corps. Repos : épaule +45°, hanche −45°.
- **Coude, genou : β**, flexion ; 0 = membre tendu. + = pli naturel, − = pli à l'envers. Repos : 35°.
  - coude : avant-bras tourné vers la tête (coude pointé vers la queue, main en avant) ;
  - genou : tibia tourné vers la queue (genou pointé vers la tête, pied en arrière).
- Ce sont les φ du contrôleur (`Creature.joint_phi`, mêmes triplets que `Contract()`) à une constante près,
  vérifié à 1e-9° près : α épaule = φ + 45°, β coude = φ + 35°, α hanche = φ − 45°, β genou = φ + 35°.

## 1. Cartographie des 14 points (13 os, §2.2)

| Point | Os qui s'y rejoignent | Classement |
|---|---|---|
| L/R_SHOULDER | clavicule + humérus | **épaule/hanche** (jonction tronc–membre) |
| L/R_HIP | demi-bassin + fémur | **épaule/hanche** |
| L/R_ELBOW | humérus + avant-bras | **coude/genou** (charnière) |
| L/R_KNEE | fémur + tibia | **coude/genou** |
| L/R_HAND, L/R_FOOT | 1 os (extrémité) | pas d'articulation |
| NECK | colonne + 2 clavicules (+ tête) | **plus de 2 os** : hors périmètre |
| PELVIS | colonne + 2 demi-bassins (+ queue) | **plus de 2 os** : hors périmètre |

Les 8 articulations à contraindre sont exactement les 8 articulations musclées (`creature.JOINTS`).

Jonctions à plus de 2 os, documentées plutôt que devinées :
- **NECK, PELVIS** : les angles colonne–clavicule et colonne–demi-bassin sont déjà figés par les liens invisibles
  (`BRACES`) ; écart maximal mesuré sur 303 grimpes : 0,30°. Rien à contraindre.
- **HEAD** : un os et deux liens invisibles, rigide.
- **Queue** : chaîne passive de 12 points (2 os chacun), attachée au PELVIS, sans aucune contrainte ; son attache
  fait jusqu'à ≈ 5 tours autour du bassin en 10 s. Hors périmètre de cette contrainte (pas de muscles, purement
  visuelle, §2.2) : aucune règle devinée ici.

## 2. Comportement actuel

Champions de la génération 200 : min..max (°) · part du temps hors des butées du §3.

| | épaule α | coude β | hanche α | genou β |
|---|---|---|---|---|
| graine 0 (16,7 m) | −85..+135 · **65 %** | −4..+84 · 0 % | −127..−11 · **43 %** | +14..+99 · 0 % |
| graine 1 (37,3 m) | −33..+113 · 4 % | −18..+120 · 14 % | −88..**+3363** (9 tours) · **60 %** | −47..+96 · **47 %** |
| graine 2 (33,8 m, référence) | −29..+75 · 0 % | +10..+94 · 0 % | −125..−44 · **72 %** | +35..+106 · 0 % |
| vidéo (images 11, 12, 16 ; 12 membres lus, ±10°) | −49..+45 | +17..+104 | −26..+70 | +34..+116 |

Les 50 meilleures de la génération 200 font de même (le champion est représentatif) :
graine 0 épaule 70 %, hanche 48 % ; graine 1 hanche 60 % (100 % font des tours complets), genou 45 %, coude 15 % ;
graine 2 hanche 74 %.

Génération 0, 50 créatures au hasard par graine : 22 à 38 % du temps hors butées sur chaque articulation, et 44 à
46 % des créatures font au moins un tour complet d'une articulation (6 à 24 % selon l'articulation). Le dépassement vient du moteur sans butées ;
chaque graine sélectionne ensuite son propre abus :

- **Graine 0, bras passés devant la tête** : épaule jusqu'à +135 à +160° ; coudes et mains de l'autre côté de
  l'axe 27 à 41 % du temps ; bras gauche et droit croisés 84 à 90 % du temps.
- **Graine 1, fémur en hélice** : ≈ 9 tours complets en 10 s (≈ 1,9 tour par cycle d'horloge de 2,0 s) ; genou
  plié à l'envers 45 % du temps, jusqu'à −47°.
- **Graine 2, fémurs rabattus derrière le bassin** : hanche jusqu'à −125° ; genoux au-delà de l'axe 35 % du temps,
  pieds 77 % ; jambes gauche et droite croisées 62 % du temps (export d'analyse de la phase 5c à t = 7,35 s :
  les deux fémurs se croisent sous le bassin). Bras et genoux restent dans les butées. Dans la vidéo, les fémurs
  sont au contraire portés vers l'avant (−26 à +70°).

Deux causes structurelles :
- Le contrôleur calcule l'erreur `wrap_angle(cible − φ)` (`Creature.control`) : une articulation à plus de 180° de
  sa cible est poussée par l'autre côté et continue de tourner. C'est ce qui fabrique les hélices. Avec des
  butées, l'écart reste sous 180° et le repli d'angle n'a plus d'effet.
- La plage des cibles du génome contient déjà des angles impossibles : épaule jusqu'à +135°, hanche jusqu'à
  −135°, coude et genou jusqu'à −55° (pli inversé). Selon la graine et l'articulation, 3 à 52 % des cibles de la
  génération 200 sont hors butées (coude : 42 à 50 %).

**Verdict : dépassement large, pas en marge.** Contraindre changera la démarche des trois graines (les jambes
pour la graine 2, toute la propulsion pour la graine 1). Les runs 0, 1 et 2 ne se rejoueront plus à l'identique
avec les butées : réentraînement (≈ 8,5 min d'évaluation par graine) et nouvelles références pour les écrans
validés sur runs/2. Les croisements bras contre jambe d'un même côté sont négligeables (0 à 2 %) ; les
croisements gauche/droite viennent des épaules et des hanches, que les butées bornent. Le modèle n'a pas de
collision entre segments.

## 3. Butées (validées)

Valeurs dans `config.JOINT_LIMITS_DEG`.

| Articulation | Plage anatomique | En φ (repos = 0) | Sens « en avant » | Tag |
|---|---|---|---|---|
| Coude | β ∈ [0°, 140°] | [−35°, +105°] | pli naturel : avant-bras tourné vers la tête | 0 [DÉDUIT] ; 140 [CHOIX] |
| Genou | β ∈ [0°, 140°] | [−35°, +105°] | pli naturel : tibia tourné vers la queue | 0 [DÉDUIT] ; 140 [CHOIX] |
| Épaule | α ∈ [−60°, +90°] | [−105°, +45°] | + = protraction (humérus vers la tête) | −60 [CHOIX] ; +90 [CHOIX] |
| Hanche | α ∈ [−80°, +75°] | [−35°, +120°] | + = protraction (fémur vers la tête) | −80 [CHOIX] ; +75 [DÉDUIT] |

Justifications :
- **Coude, genou** : charnières qui plient toujours du même côté ; chez un gecko vu de dessus, coudes pointés
  vers l'arrière et genoux vers l'avant. C'est le sens de la posture de repos et celui des 12 membres lus dans la
  vidéo, sans exception. Borne 0 : aucune hyperextension, même de 1° (critère B2 : pénétration ≤ 0,5°). Borne
  140° : au-delà, l'os se replie sur son voisin (angle intérieur < 40°), ce que la masse musculaire empêche ;
  la vidéo va jusqu'à 116° et aucun champion n'atteint 140°.
- **Épaule** : balayage avant–arrière de l'humérus dans le plan du mur (posture étalée). +90° : humérus parallèle
  à la colonne, coude à côté de la tête ; au-delà, le bras passe devant la tête et le coude traverse l'axe vers
  +123° (abus de la graine 0). −60° : fin de poussée, humérus ≈ 60° derrière la perpendiculaire (vidéo : −49°).
- **Hanche** : +75° : au poser, le fémur vient loin vers l'avant (image 11 : ≈ +70°). −80° : fin de poussée, le
  fémur revient vers la queue sans lui devenir parallèle ; à −90°, le genou commencerait à passer derrière le
  bassin (abus de la graine 2).
- Plages un peu plus larges que chez un vrai gecko : notre 2D n'a pas les mouvements hors du mur (lever ou
  abaisser la patte).

## Pour B2

- **Solveur** : une contrainte angulaire unilatérale par articulation, résolue dans les mêmes passes de
  Gauss-Seidel que les liens (même noyau numba, et son jumeau dans `evo/batch.py` pour garder l'identité au bit
  près). À la butée, impulsion de même forme que `Contract()` sur (A, P, B) (perpendiculaire sur A et B, opposée
  sur P, forces et moments de somme nulle) qui annule la vitesse angulaire sortante ; impulsion cumulée ≥ 0 comme
  le contact au sol, biais de Baumgarte et passe dans `project_links` pour la pénétration.
- **Décisions validées** : butées du §3 telles quelles ; plage des cibles du génome ramenée à la plage
  articulaire (§2.5 : « dans la plage articulaire ») ; les 3 graines réentraînées avec un drapeau `JOINT_LIMITS`,
  les runs existants restant rejouables sans lui (drapeau absent de leur config = désactivé).
- **Vérification après réentraînement** : comparer hauteurs et scores obtenus avec butées aux champions actuels
  (16,7 / 37,3 / 33,8 m pour les graines 0 / 1 / 2) ; si l'écart est important, discuter d'une recalibration
  ciblée plutôt que de supposer que les constantes de la phase 3 se transfèrent sans changement.
