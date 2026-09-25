# Chantier C, phase C1 : collisions entre membres, diagnostic et proposition

Le moteur n'a aucune collision entre segments. Les butées d'angle du chantier B règlent les dépassements d'une
articulation seule, pas les effets combinés : un pied peut passer sous la queue, une jambe peut en croiser une autre.
C1 mesure l'ampleur du problème sur les populations réelles et propose une solution. **Le moteur n'est pas touché.**

Reproduire les mesures : `python main.py joints --seed S --gen 200 --top 50 --sample 50 --crossings [--export DIR]`
(`evo/joint_audit.py`). Runs `runs/<graine>` (entraînés avec butées, chantier B), génération 200, 50 meilleures et
50 créatures au hasard par graine, soit 300 grimpes, une mesure par sous-pas (4 800 par grimpe). Hauteurs
rejouées identiques au run.

## 1. Mesures

### Côté de l'axe du corps

Axe bassin–cou, prolongé dans les deux sens ; distance comptée positive du côté du membre. Zone : derrière le bassin
(queue), entre bassin et cou (torse), devant le cou (tête).

| graine, gén. 200 | pieds de l'autre côté (part du temps) | grimpes au-delà de 10 % | profondeur médiane / p95 / max | zone | pied tenu |
|---|---|---|---|---|---|
| 0, meilleures | 0 % | 0 % | — | — | — |
| 0, hasard | < 0,1 % | 0 % | 0,13 / 0,20 / 0,20 m | queue | 77 % |
| 1, meilleures | **84 %** | 100 % | 0,58 / 0,90 / 1,06 m (15 % / 23 % de la jambe) | queue | 19 % |
| 1, hasard | **81 %** | 100 % | 0,56 / 0,90 / 1,19 m | queue | 22 % |
| 2, meilleures | **38 %** | 100 % | 0,05 / 0,10 / 0,12 m (2 % / 4 %) | queue | 68 % |
| 2, hasard | **27 %** | 68 % | 0,06 / 0,11 / 0,13 m | queue | 68 % |

- Coudes et genoux : jamais de l'autre côté. Les genoux restent à 19° au moins de l'axe, vus du bassin.
- Mains : 0,1 % du temps au plus (graine 1, au hasard), devant la tête.
- Tous les passages de pied se font derrière le bassin, dans la zone de la queue. Graine 1 : profonds, pied en
  l'air ; graine 2 : superficiels (quelques centimètres), pied tenu.

### Croisements de segments

Part du temps (moyenne sur 50 grimpes ; part des grimpes au-delà de 5 %). Segments qui partagent un point exclus.

| paire | graine 0 | graine 1 | graine 2 |
|---|---|---|---|
| **jambe / queue**, meilleures | **14,0 %** · 86 % | **72,0 %** · 100 % | **50,1 %** · 100 % |
| ↳ fémur / queue | 9,8 % | 28,4 % | 0,1 % |
| ↳ tibia / queue | 4,9 % | 50,0 % | 50,0 % |
| **jambe / queue**, hasard | 15,6 % | 65,7 % | 51,7 % |
| **jambe G / jambe D** | 0 % | **39,3 %** · 100 % | 0,1 % |
| bras / jambe du même côté (revérifié) | ≤ 0,1 % | ≤ 0,1 % | 0 % |
| bras / queue | ≤ 0,6 % | ≤ 0,1 % | ≤ 0,2 % |
| membres / colonne, ceintures, tête | 0 % | 0 % | 0 % |

**Le problème est entièrement concentré sur les jambes et la queue, derrière le bassin.** Bras, avant-bras, torse
et tête ne sont pas concernés. Les croisements bras/jambe du même côté restent négligeables avec les gaits
d'après B (≤ 0,1 % en moyenne, 5 % pour une seule grimpe au hasard).

### Deux mécanismes

Détail sur les 30 meilleures de chaque graine :

| | graine 0 | graine 1 | graine 2 |
|---|---|---|---|
| croisements jambe–queue avec le pied de l'autre côté | 0 % | 91 % | 38 % |
| attache de la queue : écart à l'axe (médiane / p95 / max) | 38° / 146° / 180° | 21° / 62° / 116° | 13° / 40° / 118° |
| hanche au moment du croisement (butée à −80°) | −13°, jamais en butée | −74°, en butée dans 46 % des cas | −80°, en butée dans 81 % des cas |
| segments de queue touchés | surtout le bout (10 à 12) | 8 à 12 | 6 à 12 |
| queue hors d'un cône de ±30° (tous points, 50 meilleures) | 78 % | 57 % | 30 % |

1. **Le pied passe sous la queue** (hanche en butée + genou fléchi) : toute la graine 1, une partie de la graine 2.
   C'est l'effet combiné hanche–genou attendu.
2. **La queue, libre, balaie les jambes.** Elle n'a aucune butée (hors périmètre de B1) et se replie jusqu'à 180°
   (graine 0, où aucun pied ne passe l'axe). Ce mécanisme ne relève pas du tout de la hanche et du genou.

## 2. Pistes évaluées

Estimation statique sur les trajectoires enregistrées (30 meilleures par graine) : part des croisements actuels qui
**resteraient permis** si la contrainte était respectée, et part du temps où elle devrait agir. Les gaits changeront
avec la contrainte : ordre de grandeur seulement.

| contrainte | graine 0 | graine 1 | graine 2 |
|---|---|---|---|
| (a) pied de son côté de l'axe : croisements restants | 100 % (n'agit jamais) | **0 %** (jambe G/D : 0 %) | 23 % |
| ↳ temps où elle agit | 0 % | 84 % | 38 % |
| (a) + queue dans un cône de ±30° : croisements restants | 0 % | 0 % | 18 % |
| (a) + queue dans un cône de ±10° | 0 % | 0 % | 1 % |
| (a) + queue dans un cône de **±6°** (valeur mesurée, §3) | **0 %** | **0 %** | **0 %** |
| ↳ queue hors du cône de ±6° (temps où il agit) | 99 % | 100 % | 99 % |
| séparation complète (pied hors du cône de ±20° de la queue) : temps où elle agit | 1 % | 97 % | 96 % |

**Verdict.**
- Le problème **dépasse le seul pied/hanche/genou** : la moitié vient de la queue, sans contrainte. Mais il ne
  justifie **pas une collision générale (b)** : aucune autre paire de segments ne se croise de façon mesurable, et
  une collision segment contre segment (≈ 200 paires, contacts non lisses) ajouterait du risque pour rien de mesuré.
- **Piste retenue : (a), étendue à la queue** : le pied reste de son côté de l'axe du corps, et la queue reste dans
  un cône derrière le bassin.
- La **séparation complète** (pied hors du cône de la queue) est écartée : elle agirait 96 à 97 % du temps pour les
  graines 1 et 2, dont les pieds sont posés juste derrière le bassin, et changerait tout le gait.
- Avec le cône mesuré (±6°, §3), l'estimation statique ne laisse **aucun** croisement jambe–queue, y compris pour la
  graine 2. Avec ±30°, il en resterait 18 % pour la graine 2 (tibia contre une queue un peu déviée, pied replié juste
  à côté de l'axe). La décision sur ce résidu est reportée après le réentraînement de C2, au vu du résidu réel.

## 3. Angle de la queue dans la vidéo (images 11, 12, 40)

Mesure sur les images : centre de la silhouette ligne par ligne ; axe du torse ajusté sur les lignes du cou et du
torse (hors membres), direction de la queue ajustée sur toutes ses lignes visibles sous les pieds.

| image | lignes de queue | écart queue / axe | écart latéral max au prolongement de l'axe | résidu de l'ajustement |
|---|---|---|---|---|
| 11 (t = 16:15) | 160 (queue coupée par le bas de l'image) | 1,7° | 5,5 px, 1,0° vu du bas du torse | 0,5 px |
| 12 (t = 16:35) | 172 (coupée) | 5,7° | 27 px, 5,4° | 0,3 px |
| 40 (t = 16:42) | 173 (queue entière) | 3,3° | 8 px, 2,3° | 0,5 px |

**La mesure est nette** : la queue est droite (résidu < 1 px) et reste à 6° au plus de l'axe du corps. D'où
`TAIL_CONE_DEG = 6` **[DÉDUIT] images 11, 12, 40 (écart queue/axe 1,7°, 5,7°, 3,3°)** au lieu des 30° en [CHOIX]
du plan. Limites de cette déduction :
- trois images du même champion de la génération 200, sur une trentaine de secondes de vidéo ;
- c'est la queue **dessinée** : le rendu de la vidéo peut la lisser, comme le nôtre la prolonge et amortit sa
  courbure (`TAIL_VISUAL_DAMPING`) ;
- la grimpe est verticale : la gravité aligne une queue passive sur l'axe.

Conséquence : avec ±6°, la queue devient presque rigide dans le prolongement de la colonne ; la contrainte agirait
99 à 100 % du temps sur les gaits actuels. C'est la valeur mesurée ; si elle s'avère trop contraignante en C2
(dynamique de la queue, coût de calcul), 30° reste le repli [CHOIX].

## 4. Esquisse de mise en œuvre (C2, rien n'est codé ici)

- **Même primitive que B2, pas de nouveau solveur.**
  - « Pied de son côté de l'axe » = butée sur l'angle au bassin du triplet (cou, bassin, pied), dans [0°, 180°] pour
    le pied gauche (miroir à droite) : exactement la contrainte d'angle de B2 sur un autre triplet.
  - « Queue dans le cône » = pour chaque point de queue k, butée sur l'angle du triplet (cou, bassin, queue_k), dans
    [180° − τ, 180° + τ].
  - Même impulsion (forme de `Contract()`), même schéma que le contact au sol (terme spéculatif, `BETA = 0`,
    projection seule), borne la plus proche sur le cercle ; 2 + 12 = 14 butées de plus (22 en tout).
- **Code** : séparer les triplets des butées (`world.limit_joints`, (Q, 3)) de ceux des muscles (`world.joints`),
  dans `physics.py`, sa référence Python et `batch.py` ; `Creature` pose les nouveaux triplets et leurs bornes ;
  identité au bit près scalaire/batché toujours testée.
- **Config** : `FOOT_AXIS_MARGIN_DEG = 0` [CHOIX] (le pied peut aller jusqu'à l'axe, pas au-delà),
  `TAIL_CONE_DEG = 6` [DÉDUIT, §3] ; drapeau `BODY_LIMITS = True`, absent = False (`LEGACY_DEFAULTS`) : les runs de
  B (`runs/<graine>`) et `runs/legacy_no_limits/` se rejouent à l'identique.
- **Mesures** : `joints --crossings` (ce C1) sert d'avant/après ; l'audit d'énergie couvre les nouvelles butées sans
  rien ajouter (`limit_active` les inclut).
- **Tests** (modèle de B2) : pied poussé contre l'axe qui s'y arrête ; queue lancée contre le bord du cône, sans
  rebond ni gain d'énergie ; scalaire/batché au bit près avec les nouvelles butées engagées ; départ hors cône ;
  drapeau désactivé et anciens runs.
- **Coût** : 22 butées au lieu de 8, dont celles de la queue presque toujours actives avec ±6° ; à mesurer
  (ordre de grandeur +40 à +60 % de temps d'évaluation).
- **Ensuite** : réentraînement des 3 graines, vérification des hauteurs, du §9 et de l'énergie comme en B2, et mesure
  du résidu jambe–queue avant de décider d'une collision ciblée.
