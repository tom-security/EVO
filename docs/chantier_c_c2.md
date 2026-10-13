# Chantier C, phase C2 : butées du corps (pieds de leur côté de l'axe, queue dans un cône)

C1 (`docs/chantier_c_diagnostic.md`) avait localisé tous les croisements de membres derrière le bassin : le pied qui
passe sous la queue (graine 1, une partie de la graine 2) et la queue libre qui balaie les jambes (graine 0). Il avait
proposé deux butées « du corps », sur la primitive des butées articulaires de B2 :
- chaque pied reste de son côté de l'axe bassin–cou ;
- la queue reste dans un cône autour du prolongement de la colonne.

C2 les met dans le moteur, réentraîne les trois graines et mesure le résultat. Le plan validé est au §12.2 de
`PASSATION.md`.

**Ce qui a changé par rapport au plan** :
- l'entraînement tourne sur GitHub Actions (`.github/workflows/train.yml`, runner ubuntu-24.04). C'est le seul
  environnement qui rejoue les runs au bit près ; sous Windows, les rejeux divergent ;
- le critère de repli a été complété par une règle de Tom : repli direct à 30° si une troisième mesure échoue à cause
  du mécanisme « queue en butée de cône et au sol ». C'est ce qui s'est produit (§5).

**Runs** (hors git) :
- `runs/butees_corps_30/S` : cône de 30°, **la référence C2** ;
- `runs/butees_corps/S` : cône de 6°, gardé pour le rapport ;
- B2 reste dans `runs/S`.

> **Note : chemins réorganisés au gel de la v1.** Les runs C2 à 30° sont devenus les runs par défaut :
> `runs/butees_corps_30/S` est devenu `runs/S`, et B2 est passé de `runs/S` à `runs/butees_articulaires/S`.
> `runs/butees_corps/S` (6°) ne change pas. Dans ce rapport, lire `runs/butees_corps_30/S` comme `runs/S`, et `runs/S`
> (B2) comme `runs/butees_articulaires/S`. Les trois jeux sont sauvegardés sur la branche `sauvegarde-runs`.

Toutes les mesures sur des runs ont été faites sur le runner, hauteurs rejouées identiques au run.

## 1. Ce qui a changé dans le moteur

**Moteur (commit 1)** :
- les butées portent sur leurs propres triplets, `World.limit_joints` (Q, 3), séparés des muscles (`joints`) ;
- par défaut, ce sont les 8 articulations de B2, sans aucune opération flottante changée ;
- sous Windows, les hauteurs rejouées avant et après ce commit sont identiques au milliardième ;
- sur le runner, B2 se rejoue au bit près.

**Butées du corps (commit 2, drapeau `BODY_LIMITS`)** : 14 butées posées après les 8 articulations, sur des triplets
(NECK, PELVIS, X) :

| Groupe | Triplets | u = signe·θ | Valeur |
|---|---|---|---|
| pieds | (NECK, PELVIS, L_FOOT) signe +1, (…, R_FOOT) signe −1 | [m, 180° − m] | m = `FOOT_AXIS_MARGIN_DEG` = 0 [CHOIX] |
| queue | (NECK, PELVIS, TAIL_k), k = 0..11 | [180° − τ, 180° + τ] | τ = `TAIL_CONE_DEG` = **30 [CHOIX]** (6 [DÉDUIT] au départ) |

- Même schéma que le sol et les butées de B2 : entrée dans le solveur à 2° près, terme spéculatif, `BETA = 0`,
  projection seule. L'ordre des passes reste liens, butées, sol.
- `LEGACY_DEFAULTS["BODY_LIMITS"] = False` : les runs de B2 se rejouent sans les butées du corps.
- Le scalaire et le batché sont identiques au bit près avec pied et queue engagés. Numba et Python sont identiques
  avec les 22 butées.
- Tests : `tests/test_body_limits.py` (15).

**Coût** : `benchmark --pop 1000` sur le PC, en alternance, donne 12,0 s (B2) contre 26,0 s (C2), soit ×2,2. La
queue est en contact presque en permanence. Sur le runner, une graine de 200 générations prend 18 à 56 min.

**Outils (commit 3 et suivants)** :
- `joints --tail` : queue et butées du corps, verdict du critère de repli ;
- `joints --fallen` : toutes les créatures tombées d'une génération, avec l'audit d'énergie ;
- `morpho` : facteurs de longueur des os ;
- `planche` : images côte à côte ;
- `trace` : rejeu pas à pas audité ;
- workflow : modes `reproductibilite`, `pytest`, `analyse`.

## 2. Réentraînement : hauteurs et scores

200 générations × 1 000 créatures, `--set AUDIT_EVERY=10`.

| Graine, gén. 200 | B2 | C2 à 6° | **C2 à 30°** | Vidéo (§9) |
|---|---|---|---|---|
| champion | 34,2 / 33,4 / 35,3 m | 38,9 / 33,9 / 48,5 m | **39,5 / 37,1 / 42,8 m** | 36 m |
| moyenne | 26,6 / 25,2 / 27,9 m | 29,3 / 25,9 / 40,1 m | 29,2 / 27,1 / 34,8 m | ≈ 28 m |
| au sol | 61 / 121 / 51 | 120 / 75 / 83 | 119 / 90 / 84 | ≈ 30 |
| entre 30 et 35 m | 720 / 718 / 623 | 40 / 737 / 5 | 16 / 270 / 15 | majorité |
| période moyenne | 1,54 / 0,88 / 0,60 s | 0,78 / 1,43 / 0,81 s | 0,86 / 1,47 / 0,87 s | 0,6 s |
| masse musculaire moyenne | 14,6 / 16,7 / 10,0 | 16,8 / 12,2 / 14,6 | 16,4 / 13,5 / 13,8 | 10,5 |

- **Aucun champion sous 27 m.** Les champions de C2 montent plus haut que ceux de B2, sur toutes les graines.
- Le pied ne peut plus passer sous la queue, et ne s'y accroche donc plus (C1 : le pied de la graine 2 était tenu 68 %
  du temps de l'autre côté). Les démarches trouvées sont plus efficaces.
- Le pic de la graine 2 à 6° (48,5 m) reste sous le plafond de plausibilité de l'audit (50 m). Les audits de ses
  champions ne montrent aucune énergie créée hors muscles (§4).
- La majorité n'est plus « entre 30 et 35 m » : elle est au-dessus (médianes 38,4 / 34,9 / 41,7 m). C'est un écart à
  la vidéo dans l'autre sens que celui de B2.

**Repères de l'évolution (§9)** :

| | B2 | C2 à 30° | Vidéo |
|---|---|---|---|
| gén. 0 : au sol | 392 / 408 / 383 | 378 / 389 / 361 | ≈ 450 |
| gén. 0 : meilleure | +2,2 / −0,3 / +3,0 m | +2,1 / −0,3 / +3,0 m | ne grimpe pas |
| flemme, gén. 1 à 20 : muscle min | 9,1 / 7,6 / 8,2 | 8,6 / 6,9 / 9,2 | 13,2 → 7,3 |
| flemme, gén. 1 à 20 : période max | 3,8 / 3,5 / 4,8 s | 3,4 / 3,7 / 4,2 s | 4,5 s |
| première meilleure au-delà de +5 m | gén. 13 / 5 / 11 | gén. 7 / 7 / 13 | gén. 12 (+1 m) |
| période moyenne sous 1,5 s dès | gén. 102 / 16 / 51 | gén. 31 / 184 / 30 | chutes à 80–85 puis 140–150 |

Courbes : `docs/chantier_c_c2/courbes_comparees_s{0,1,2}.png` (`graphs --compare runs/S`, B2 en pointillés).

## 3. Pieds, queue et croisements, avant et après

`joints --gen 200 --top 50 --sample 50 --crossings --tail`, 50 meilleures, valeurs de C1 (B2) entre parenthèses :

| Graine | Pied de l'autre côté de l'axe | Jambe / queue | Jambe G / jambe D | Queue hors de ±30° |
|---|---|---|---|---|
| 0 | 0 % (0 %) | 0 % (14,0 %) | 0 % (0 %) | 0 % (78 %) |
| 1 | 0,1 % (84 %) | 6,8 % (72,0 %) | 0 % (39,3 %) | 0 % (57 %) |
| 2 | 0 % (38 %) | 7,5 % (50,1 %) | 0 % (0,1 %) | 0 % (30 %) |

- Les deux mécanismes de C1 sont supprimés : le pied ne passe plus sous la queue, et la queue ne balaie plus les
  jambes.
- **Reste un résidu jambe–queue** de 6,8 % et 7,5 % (graines 1 et 2) : c'est le tibia qui croise la queue. Il est
  permis par un cône de 30°. À 6°, il était de 0,2 % et 0 %. Il est laissé à la décision de Tom (bilan).
- **Nouveau, graine 0 : les bras se croisent** 89,2 % du temps (bras G / bras D) et passent devant la tête 31,1 % du
  temps. Aucune contrainte n'existe entre les bras ; ce n'était pas dans le périmètre de C1 (≈ 0 en B2). Ajouté aux
  écarts connus.
- **Pénétration des 22 butées** chez les meilleures : articulations 0,000°, pieds 0,000°, queue ≤ 0,026°. Erreur des
  os du corps ≤ 0,06 %.

## 4. Énergie

**Champions audités toutes les 10 générations** (`audit.csv`, 21 audits par graine) :
- 0 J créé hors muscles, aucune alerte ;
- erreur des os ≤ 0,74 %, de la queue ≤ 0,93 % ;
- saut d'énergie à l'engagement d'une butée : 0 J.

**10 meilleures aux générations 0, 50, 100, 150 et 200** (`joints --energy`, 150 grimpes) :
- 70 à 177 engagements de butées par grimpe ;
- 0 J créé hors muscles ;
- saut maximal à l'engagement 0 J ;
- saut maximal sans butée 0 J.

**Créatures tombées des vraies populations** (`joints --fallen`, toutes celles des générations 0 et 200 ; règle de
Tom : arrêt seulement si C2 fait plus du double de B2) :

| Graine, gén. | Tombées B2 / C2 30° | > 5 cm B2 / C2 | Maximum B2 / C2 (cm) | Pire cas C2 (n°, rang) | Total B2 / C2 (J) |
|---|---|---|---|---|---|
| 0, 0 | 392 / 378 | 5 / 3 | 85,1 / 50,3 | n°630, 645 | 318 / 216 |
| 0, 200 | 61 / 119 | 0 / 0 | 3,8 / 0,0 | — | 8 / 0 |
| 1, 0 | 408 / 389 | 3 / 4 | 61,3 / 34,9 | n°840, 546 | 255 / 172 |
| 1, 200 | 121 / 90 | 7 / 0 | 424,5 / 0,0 | — | 1 293 / 0 |
| 2, 0 | 383 / 361 | 6 / 3 | 645,3 / 68,1 | n°328, 882 | 1 820 / 218 |
| 2, 200 | 51 / 84 | 0 / 0 | 0,0 / 0,1 | — | 0 / 0 |

- La règle relative ne se déclenche pas : C2 fait nettement **mieux** que B2.
- Ce phénomène existait déjà en B2 sans avoir été mesuré : des créatures couchées créent de l'énergie hors muscles.
  Diagnostic et options au bilan (`docs/BILAN_V1.md`, chantier D proposé).
- n°840 (graine 1, gén. 0) crée 74 J **avant** sa chute, en tenant le mur. C'est le même génome qu'en B2 (82,5 J) :
  le mécanisme est celui de B2.

## 5. Critère de repli et passage de 6° à 30°

**Critère** (`joints --tail`, 50 meilleures de la gén. 200, seuils [CHOIX] de `config.py`) :

| | B2 (référence, pas de cône) | C2 à 6° | C2 à 30° |
|---|---|---|---|
| os de queue, max | 0,49 / 1,09 / 0,70 % | 0,16 / 0,68 / 0,18 % | 0,64 / 0,37 / 0,26 % |
| grimpes étirées (> 1 % plus de 0,1 s) | 0 / 0 / 0 % | 0 / 0 / 0 % | 0 / 0 / 0 % |
| oscillation contre le cône, max par grimpe | 0,4 / 0,5 / 0,4 % | 0,3 / 0,4 / 0,2 % | 1,2 / 0,6 / 0,9 % |
| verdict | — | **garder 6°** | **garder 30°** |

Sur les grimpeuses, le critère n'a jamais demandé le repli.

**Le repli est venu d'une autre règle de Tom** : repli direct à 30° si une troisième mesure tombe à cause du mécanisme
« queue en butée de cône et posée au sol ». Les trois mesures :
1. créature inerte : 4,39 J créés hors muscles (B2 : 0,13 J) ;
2. créature inerte : queue étirée de plus de 5 % pendant 662 ms (B2 : 10 ms) ;
3. créatures tombées des vraies populations, gén. 0 : 77 à 82 par graine avec un os de queue au-delà de 5 % (B2 : 1
   à 6), jusqu'à 26 %. Sur les 12 pires, **100 % des 4 318 sous-pas** au-delà de 5 % ont la queue en butée ET au
   sol.

**À 30°** :
- créature inerte : 0,30 J créés, queue au-delà de 5 % pendant 58 ms ;
- tests propres au cas inerte avec `BODY_LIMITS` (décision de Tom) : énergie < 6 J, queue < 10 %.

## 6. Limites connues (acceptées par Tom, documentées)

**Queue des créatures tombées étirée à l'impact.** Os de queue au-delà de 5 % (`AUDIT_MAX_TAIL_ERROR`), toutes les
créatures tombées :

| Graine, gén. | B2 | C2 à 30° | Maximum B2 / C2 | Plus longue durée au-delà de 5 %, B2 / C2 |
|---|---|---|---|---|
| 0, 0 | 6 | 9 | 12,2 / 8,0 % | 779 / 354 ms |
| 0, 200 | 0 | 6 | 3,0 / 43,8 % | 0 / 77 ms |
| 1, 0 | 1 | 19 | 6,3 / 12,8 % | 627 / 1 010 ms |
| 1, 200 | 9 | 1 | 9,8 / 5,0 % | 1 929 / 21 ms |
| 2, 0 | 6 | 12 | 11,4 / 11,0 % | 1 171 / 1 165 ms |
| 2, 200 | 0 | 0 | 2,7 / 2,6 % | 0 / 0 ms |

- **Mécanisme** : la queue est tenue dans son cône et posée au sol ; la projection (liens, butées, sol) l'étire en la
  ramenant dans le cône puis sur le sol.
- Le pire cas, n°677 (graine 0, gén. 200), atteint 43,8 % à t = 9,53 s, 0,02 s après sa chute, avec 8 points de
  queue au sol. Cela ne crée aucune énergie.
- Les grimpeuses ne sont pas touchées : elles restent jugées par le critère de repli.

**Sortie de cône d'un seul sous-pas, en l'air.**
- Dans le groupe tiré au hasard, la queue sort parfois du cône pendant un sous-pas, puis revient au suivant :
  - jusqu'à 144° au-delà (graine 1), 115° (graine 0), 20° (graine 2) ;
  - n°808 (graine 1) : 16 sous-pas en 0,12 s, jamais tombée, une patte tenue, 4 à 6 butées de queue actives ;
  - même motif à 6° (n°541, graine 2 : 116 sous-pas, jusqu'à 161°).
- **C'est un saut de position de la projection** quand plusieurs butées de queue agissent ensemble : il ne crée pas
  d'énergie (0 J sur ces grimpes), et la queue revient dans le cône dès le sous-pas suivant.
- Les 50 meilleures ne sont pas touchées (pénétration ≤ 0,026°).

**Bras croisés de la graine 0** : voir le §3. Ajoutés aux écarts connus (§11 de `PASSATION.md`).

## 7. Morphologie

`morpho` donne le facteur moyen de longueur (longueur ÷ référence, bornes 0,6 – 1,4) à la génération 200 (CSV et
courbes : `docs/chantier_c_c2/morphologie_s{0,1,2}`) :

| Graine | Run | Colonne | Clavicule | Humérus | Avant-bras | Demi-bassin | Fémur | Tibia |
|---|---|---|---|---|---|---|---|---|
| 0 | B2 | 1,24 | 0,74 | 0,96 | 0,86 | 0,62 | 0,89 | 0,72 |
| 0 | C2 30° | 0,66 | 0,66 | 0,61 | 1,08 | 0,82 | 1,01 | 0,63 |
| 1 | B2 | 0,90 | 0,65 | 0,90 | 0,63 | 0,69 | 1,29 | 1,27 |
| 1 | C2 30° | 0,76 | 0,64 | 1,00 | 0,82 | 0,63 | 0,63 | 0,78 |
| 2 | B2 | 0,62 | 0,62 | 0,64 | 0,70 | 1,36 | 0,73 | 0,87 |
| 2 | C2 30° | **1,08** | 0,61 | 1,30 | 0,67 | 1,37 | 0,76 | 0,72 |

- Le « lézard trapu » de B2 (graine 2 : colonne à la borne basse, demi-bassin presque à la borne haute) n'est plus
  vrai pour la colonne en C2 (1,08), mais le demi-bassin reste large (1,37).
- À 6°, la graine 2 avait la colonne à 1,04 et le demi-bassin à 0,76.
- Les autres graines changent de morphologie sans tendance commune. La pression de sélection sur les longueurs
  dépend de la démarche trouvée, pas des butées elles-mêmes.

## 8. Écrans refaits sur `runs/butees_corps_30/2`

Écrans produits sur le runner (mode `analyse`), sorties dans `out/chantierC/ecrans/` et `out/chantierC/videos/`,
hors git :
- `replay --gen 200 --export` ;
- `population --gen 200 --export` ;
- `population --gen 0 --cycle --export` ;
- `histogram --gen 0 / 1 / 200 --style video` ;
- `analyze --gen 200 --export` ;
- `compare --gens 0 23 100 200 --export` ;
- les 6 vidéos (replay, créature 1 de la génération 0 ×4 avec carton, analyse au ralenti, comparaison, population,
  cycle).

Dans les artefacts publics, les captures de la vidéo ont été remplacées par des aplats. Les planches avec la vidéo
sont refaites sur le PC.

**Contrôle visuel de la queue (non tranché, pour le bilan)** :
- Planche `docs/chantier_c_c2/queue_pieds_avant_apres.png` : B2 | C2 6° | C2 30°, à l'instant de l'image 11. La
  version avec l'image 11 est dans `out/chantierC/planches/` (hors git).
- B2 : queue repliée sous le corps.
- C2 à 6° : queue droite dans l'axe, comme sur les images 11, 12 et 40.
- C2 à 30° : queue dessinée nettement courbée sur le côté, contre la jambe.
- Chiffres de posture (50 meilleures) :

  | | Écart max à l'axe (médiane / p95) | Collée au bord | Courbure médiane |
  |---|---|---|---|
  | C2 à 30° | 24 à 28° / 30° | 11 à 30 % du temps | 13 à 16° |
  | C2 à 6° | 6° / 6° | 66 à 73 % du temps | 2 à 4° |

  Sur les images de la vidéo, la queue est à 1,7 à 5,7° de l'axe.
- La queue dessinée prolonge la queue physique avec une courbure amortie : la courbure physique de 13 à 16° se voit
  donc sur toute la longueur dessinée.

## 9. Pour la suite

À trancher par Tom (repris dans `docs/BILAN_V1.md`) :
- le résidu jambe–queue des graines 1 et 2 à 30° (6,8 % et 7,5 %) ;
- le jugement visuel de la queue à 30° : tenue ou trop courbée ;
- le chantier D proposé (projection propre), qui traiterait aussi l'énergie des créatures couchées ;
- faire de `runs/butees_corps_30` les runs par défaut, puis fusionner sur `main` ;
- le coût ×2,2 de l'évaluation.
