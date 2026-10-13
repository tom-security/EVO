# Chantier D, étapes 1 et 2 : diagnostic et comparaison des candidats (lecture seule)

Le chantier D, « projection propre », est proposé au §4 de `docs/BILAN_V1.md`, dont le plan a été validé.

Ce document couvre les étapes 1 et 2 de ce plan :
- expliquer les deux anomalies de la variante `vitesse_proj` (la n°808 et la n°677) ;
- comparer trois candidats sur chiffres ;
- recommander. **Le choix revient à l'utilisateur.**

**Aucun changement du moteur.** Les variantes sont substituées le temps d'une mesure par `evo/diag_projection.py`
(`diag-projection`, `trace --variante`), du code de mesure accordé par l'utilisateur. Avant toute mesure, le moteur tel
quel est vérifié identique au bit près au run : c'est le cas pour toutes les créatures mesurées (1 571).

**Branche** : `claude/chantier-d-diagnostic`, partie de `main` (`v1.0`). Mesures sur le runner GitHub, sur les runs
de la v1 : `runs/S` (C2 à 30°), et `runs/butees_articulaires/S` (B2) pour les cas 868 et 760.

## 1. Les candidats

| | Variante | Principe |
|---|---|---|
| (a) | `vitesse_proj` | après la projection, toute correction de position est reportée sur la vitesse : v += Δp/h |
| (b) | `dissipatif` | même report, multiplié par un seul facteur α ∈ [0, 1], le plus grand qui n'augmente pas l'énergie cinétique : avec Δv = Δp/h, α = min(1, −2·Σm·v·Δv / Σm·|Δv|²) si ce produit est négatif, sinon 0. Le report ne peut que retirer de l'énergie |
| (c) | `passes120` | résolution en vitesse renforcée : 120 passes de Gauss-Seidel au lieu de 30 (liens, butées, sol) |

## 2. Explications (étape 1)

### Les 17,7 J de la n°808 avec (a)

Rejeu pas à pas sur le runner, run 38369652588 :
- toute l'énergie est créée en **5 sous-pas, entre t = 7,867 et 7,875 s** ;
- la créature est en l'air, une patte tenue, avec **7 butées de queue actives** et les muscles qui freinent fort
  (−4,5 J par sous-pas) ;
- avant la projection, aucune butée n'est franchie (marge de queue +0,00°), mais **les liens restent étirés de 0,4 à
  0,7 %**, soit 10 fois plus que d'habitude : la résolution en vitesse ne converge pas quand tant de butées tirent sur
  la colonne en même temps ;
- la projection recolle les liens (Δp de 1 à 1,7 mm), et (a) transforme ces corrections en vitesse dans le sens du
  mouvement : **+29,6 J** d'énergie cinétique sur ces 5 sous-pas, soit 17,7 J créés une fois les pertes déduites ;
- avec (b), le même report ne garde que la part qui freine : 0 J créé, et 288 J retirés sur la grimpe.

### Le changement de destin de la n°677

Le moteur tel quel la couche au sol à −8,99 m (chute à 9,51 s). Avec (a) ou (b), elle est encore en l'air à 10 s
(+1,85 m ou +1,90 m). Avec (c), elle tombe à 9,47 s (−9,31 m).
- Dans tous les cas, elle lâche le mur vers 7 à 8 s.
- Les trajectoires s'écartent de quelques centimètres dès t ≈ 1,9 s (effet chaotique), et le décrochage arrive plus ou
  moins tard.
- La différence de 10,8 m vient donc **du moment où la simulation s'arrête**, pas d'une meilleure grimpe.

C'est une question sur le score, et non sur le chantier D : voir le §6.

### Les sorties de cône d'un seul sous-pas : un autre mécanisme

- Juste avant la projection, la marge de la butée de queue vaut −117° à −138°, et une correction de 1 à 2,5 mm la
  ramène à 0°. Un angle qui varie de 120° pour un déplacement de quelques millimètres n'est possible que si le point
  mesuré est presque confondu avec le pivot.
- Confirmé au bit près : au moment de ces sorties, **un point de queue passe à moins d'un millimètre du bassin**
  (n°808 : point 7 à t = 8,84 s ; n°541, à 6° : point 11 à t = 9,98 s).
- La butée de cône porte sur la **direction** de chaque point vu du bassin, pas sur sa distance : la queue peut se
  replier dans le cône jusque sur son sommet, où l'angle n'est plus défini et la butée devient singulière.
- Ni (a), ni (b), ni (c) ne traitent ce mécanisme (§3).

## 3. Comparaison (étape 2)

Runs 38369652588 (cas), 38369666346 à 38369739708 (tombées) et 38369752981 (meilleures). « > 5 cm » : énergie créée
hors muscles au-delà du seuil d'audit, en équivalent hauteur. Δh : hauteur à 10 s moins hauteur stockée.

**Les 4 cas** :

| Cas | tel quel | (a) | (b) | (c) |
|---|---|---|---|---|
| B2 n°868 (couchée) : énergie créée / queue max | 1 292,5 J / 9,1 % | 9,6 J / 0,3 % | **0 J / 0,3 %** | 1 074,6 J / 6,2 % |
| B2 n°760 (couchée) | 825,2 J / 9,8 % | 12,9 J / 0,9 % | **0 J / 0,7 %** | 789,8 J / 10,3 % |
| C2 n°677 (impact) : queue max / sorties de cône | 43,8 % / 10 | 0,2 % / 0 | **0,2 % / 0** | 0,3 % / 1 |
| C2 n°808 (en l'air) : énergie créée / sorties de cône | 0 J / 16 (117°) | **17,7 J** / 0 | **0 J / 0** | 0 J / 3 (5°) |

**Toutes les créatures tombées, génération 0** (1 128 créatures, 3 graines) :

| | énergie créée totale | max | > 5 cm | queue max | queue > 5 % | grimpes avec sortie de cône (sous-pas, max) |
|---|---|---|---|---|---|---|
| tel quel | 606 J | 68,1 cm | 10 | 12,8 % | 40 | 147 (39 687, 150°) |
| (a) | **10 558 J** | **100,8 cm** | **240** | 7,1 % | 2 | 116 (34 082, 150°) |
| (b) | **3,5 J** | **0,5 cm** | **0** | 7,2 % | 6 | 109 (32 717, 150°) |
| (c) | 412 J | 75,6 cm | 5 | 17,7 % | 10 | 130 (26 548, 150°) |

**Toutes les créatures tombées, génération 200** (293 créatures) :

| | énergie créée totale | max | > 5 cm | queue max | queue > 5 % | grimpes avec sortie de cône (sous-pas, max) |
|---|---|---|---|---|---|---|
| tel quel | 0,1 J | 0,05 cm | 0 | 43,8 % | 7 | 162 (6 802, 150°) |
| (a) | **11 046 J** | **1 360 cm** | **116** | 8,4 % | 2 | 86 (1 616, 149°) |
| (b) | **0 J** | **0** | **0** | 6,9 % | 1 | 95 (2 217, 150°) |
| (c) | 0 J | 0 | 0 | 5,0 % | 0 | 155 (5 721, 149°) |

**Les 50 meilleures de la génération 200** (150 grimpes) :

| | énergie créée | queue max | sorties de cône | Δh médiane | Δh min / max | tombées |
|---|---|---|---|---|---|---|
| tel quel | 0 J | 0,6 % | 0 | 0 | 0 | 0 |
| (a) | 0 J | 0,6 % | 0 | −0,03 m | −0,69 / +0,32 m | 0 |
| (b) | 0 J | 0,6 % | 0 | −0,04 m | **−8,81** / +0,40 m | 0 |
| (c) | 0 J | 0,3 % | 0 | −0,04 m | −2,14 / +0,45 m | 0 |

- Le −8,81 m de (b) est une seule grimpeuse de la graine 1, qui finit plus bas sans tomber ; les autres restent à
  quelques centimètres.
- Les créatures tombées changent aussi de destin avec chaque variante, de −2,5 à +43,6 m. Parmi les 293 tombées de
  la génération 200, 22 à 36 ne tombent plus. C'est l'effet chaotique et l'artefact du §6, pas une meilleure grimpe.

**Coût** (relatif au moteur tel quel) :

| | moteur scalaire, runner | moteur scalaire, PC | évaluateur batché (entraînement) |
|---|---|---|---|
| (a) | ×1,09 | ×1,09 | quelques pour cent (estimé : un report de vitesse sur 27 points par sous-pas, contre 30 passes sur ≈ 40 liens et 22 butées) |
| (b) | ×1,14 | ×1,23 | quelques pour cent (estimé, comme (a), plus deux sommes) |
| (c) | ×1,17 | ×1,15 | **×2,4** (mesuré, PC : 18,9 s contre 7,9 s pour 500 créatures) |

- Le surcoût scalaire de (a) et (b) est surtout celui d'une enveloppe Python ; dans le noyau numba, il serait bien
  moindre.
- Le coût batché de (a) et (b) ne se mesure qu'une fois codé dans le noyau, ce qui est l'étape 3.

## 4. Recommandation

**(b) `dissipatif`**, derrière un drapeau, comme prévu à l'étape 3 :
- c'est le seul candidat qui supprime l'énergie créée partout : 3,5 J sur 1 128 créatures tombées en génération 0 (au
  plus 0,5 cm), contre 606 J ; 0 J en génération 200 ; 0 J sur la n°808 ;
- la queue étirée à l'impact passe de 43,8 % au plus à 7,2 % au plus, et de 47 à 7 créatures au-delà de 5 % ;
- les grimpeuses ne changent presque pas (médiane −4 cm), à une exception près, à vérifier en population entière au
  réentraînement ;
- le coût attendu est faible.

**(a) est à écarter** : il crée lui-même de l'énergie à grande échelle (240 créatures au-delà de 5 cm, jusqu'à
13,6 m).

**(c) est à écarter** : il ne règle qu'une partie du problème (412 J et 17,7 % de queue en génération 0), pour un coût
×2,4 qui s'ajouterait au ×2,2 de C2.

**À ajouter au chantier D** : (b) ne traite pas les sorties de cône, qui viennent du repli de la queue jusqu'au sommet du
cône (§2). Je propose un candidat (d), à mesurer de la même façon avant de coder :
- remplacer les 12 butées « point de queue vu du bassin » par des butées de **courbure** : à chaque jonction de queue,
  l'angle (TAIL_{k−1}, TAIL_k, TAIL_{k+1}) reste à moins de β de l'alignement ;
- garder une seule butée de cône sur le premier segment, (NECK, PELVIS, TAIL_0), bien définie puisque ce point est à
  distance fixe du bassin ;
- c'est la même primitive, sur des triplets dont le pivot est toujours à distance fixe des deux autres points : il n'y
  a plus de singularité ;
- le cône de 30° de la v1 deviendrait une courbure par jonction, avec β à choisir pour retrouver une posture comparable
  (une queue moins courbée que les 24 à 28° actuels irait d'ailleurs dans le sens de la vidéo).

La butée « mains de leur côté de l'axe » reste prévue à l'étape 3 ; elle ne dépend pas de ce choix.

## 5. Suite proposée

Choisir parmi (a), (b) et (c), et dire si (d) doit être mesuré avant l'étape 3, avec la même méthode (substitution des
butées de queue à la création de la créature, lecture seule). Ensuite, l'étape 3 du plan (drapeaux, trois
implémentations, tests au bit près), sans changement.

*(Fait : (b) retenu, (d) mesuré, voir le §5 bis.)*

## 5 bis. Candidat (d) : butées de courbure de queue, avec (b) (mesuré après le choix de (b))

**Décision de l'utilisateur** : (b) `dissipatif` est retenu ; (a) et (c) sont écartés. (d) est mesuré avant l'étape 3,
avec la même méthode et sans toucher au moteur : les butées de queue sont substituées à la création de la créature
(`diag-projection --variantes dissipatif:courbure5`, commit `cbad6f0`).

**(d)** :
- un cône de ±β sur le premier segment, (NECK, PELVIS, TAIL_0) ;
- puis une butée de courbure ±β à chaque jonction, (TAIL_{k−1}, TAIL_k, TAIL_{k+1}) ;
- toujours 12 butées de queue ; chaque pivot est à distance fixe de ses deux voisins, donc sans singularité.

**Deux réglages** :
- **β = 5°**, « équivalent au cône de 30° » : pour une courbure uniforme, le bout de la queue peut s'écarter de 30°
  de l'axe, comme avec le cône, soit 60° de virage cumulé. L'autre lecture possible, 30° de virage cumulé
  (β = 2,5°), tombe entre les deux réglages mesurés ;
- **β = 1°** : le bout s'écarte d'environ 6° au plus, comme sur les images 11, 12 et 40 (1,7 à 5,7°).

Les quatre variantes sont mesurées sur les mêmes créatures. Le moteur tel quel est identique au run dans tous les cas
(runs 38379927441 à 38380021401 ; `pytest` sur le runner : 161 passent, run 38379914393).

**Toutes les créatures tombées, génération 0** (1 128) :

| | énergie créée totale ; max ; > 5 cm | queue étirée : max ; > 5 % | pénétration des butées de queue > 0,5° : grimpes ; sous-pas ; max | sauts d'angle de la queue > 20° en un sous-pas : grimpes ; sous-pas | point de queue à moins de 5 cm du bassin : grimpes | liens étirés avant projection : max ; temps moyen > 0,2 % | posture : écart à l'axe médian ; p95 ; courbure |
|---|---|---|---|---|---|---|---|
| tel quel | 606 J ; 68,1 cm ; 10 | 12,8 % ; 40 | 147 ; 39 687 ; 150° | 160 ; 39 762 | 182 | 12,8 % ; 535 ms | 29,6° ; 30,0° ; 10,9° |
| (b) | 3,5 J ; 0,5 cm ; 0 | 7,2 % ; 6 | 109 ; 32 717 ; 150° | 160 ; 21 318 | 188 | 7,3 % ; 263 ms | 29,6° ; 30,0° ; 10,8° |
| (b) + (d) β = 5° | 21,0 J ; 3,2 cm ; 0 | 6,2 % ; 2 | **1 089 ; 809 206 ; 10°** | **0 ; 0** | **0** | 6,7 % ; 290 ms | 22,1° ; 35,1° ; 20,0° |
| (b) + (d) β = 1° | 22,3 J ; 0,7 cm ; 0 | 7,3 % ; 9 | **1 123 ; 1 219 332 ; 8°** | **0 ; 0** | **0** | 7,8 % ; 483 ms | **6,8° ; 10,2° ; 5,8°** |

**Toutes les créatures tombées, génération 200** (293) :

| | énergie créée ; > 5 cm | queue étirée : max ; > 5 % | pénétration > 0,5° : grimpes ; max | sauts d'angle : grimpes | sommet du cône : grimpes | posture : écart médian ; p95 |
|---|---|---|---|---|---|---|
| tel quel | 0,1 J ; 0 | 43,8 % ; 7 | 162 ; 150° | 196 | 206 | 29,5° ; 30,0° |
| (b) | 0 J ; 0 | 6,9 % ; 1 | 95 ; 150° | 200 | 211 | 29,5° ; 30,0° |
| (b) + (d) β = 5° | 1,2 J ; 0 | 11,3 % ; 3 | 292 ; 24° | **0** | **0** | 21,0° ; 36,7° |
| (b) + (d) β = 1° | 0,1 J ; 0 | 9,8 % ; 2 | 293 ; 19° | **0** | **0** | **7,0° ; 11,5°** |

**Les 50 meilleures de la génération 200** (150 grimpes) :

| | pénétration > 0,5° : grimpes ; max | sauts d'angle : grimpes | sommet du cône : grimpes | liens étirés avant projection : temps moyen > 0,2 % | posture : écart médian ; p95 ; courbure | Δh médiane ; min | tombées |
|---|---|---|---|---|---|---|---|
| tel quel | 0 ; 0° | 6 | 11 | 1 372 ms | 25,4° ; 30,0° ; 14,1° | 0 ; 0 | 0 |
| (b) | 0 ; 0° | 9 | 12 | 1 350 ms | 25,6° ; 30,0° ; 14,4° | −0,04 m ; −8,81 m | 0 |
| (b) + (d) β = 5° | 67 ; 19° | 0 | 0 | 45 ms | 12,6° ; 27,3° ; 9,0° | −0,42 m ; −45,6 m | 3 |
| (b) + (d) β = 1° | 150 ; 12° | 0 | 0 | 51 ms | 6,9° ; 10,2° ; 5,9° | −2,62 m ; −45,6 m | 33 |

Par graine, avec β = 1° : écart de hauteur médian −0,71 / **−43,76** / −1,82 m. Toute l'élite de la graine 1 tombe :
sa démarche repose sur une queue courbée de 28° (médiane).

**Les cas** :
- n°808 : 0 J avec les trois variantes. Sorties de cône (tel quel) : 16 sous-pas, jusqu'à 117°. Avec (d), plus aucun
  saut ni approche du sommet, mais des butées de courbure enfoncées de 4° (β = 5°) ou 3° (β = 1°).
- n°541 (6°) : 116 sous-pas hors du cône, jusqu'à 161° tel quel ; avec (d), 1° au plus.
- n°677 : queue étirée à l'impact de 43,8 % tel quel, 0,2 % avec (b), 2,8 % (β = 5°) ou 6,0 % (β = 1°).
- n°868 et n°760 sont des runs B2, sans butées du corps : (d) n'y change rien (0 J avec (b)).

**Coût**, en alternance, sur le runner :

| | moteur scalaire | évaluateur batché (entraînement), 500 créatures |
|---|---|---|
| butées actuelles (cône) | ×1,00 (tel quel) ; ×1,15 avec (b) | 12,45 s, ×1,00 |
| (d) β = 5° | ×1,20 avec (b) | 18,57 s, **×1,49** |
| (d) β = 1° | ×1,22 avec (b) | 19,79 s, **×1,59** |

Le coût de (b) dans le noyau batché reste estimé (quelques pour cent). Avec β = 1°, la chaîne de 11 butées couplées
est presque toujours active.

**La grimpeuse n°21 de la graine 1** (−8,81 m avec (b)) :
- les trajectoires s'écartent de quelques centimètres dès t = 0,59 s (effet chaotique) et restent proches jusqu'à 6 s
  (20,73 contre 20,66 m) ;
- entre 6 et 8 s, la version (b) perd 1,7 m puis stagne (27,58 contre 23,02 m à 8 s) : elle finit à 26,77 m au lieu
  de 35,58 m, sans tomber ;
- avec (b) seulement, un point de queue passe à 1 mm du bassin entre 4,24 et 4,28 s (20 sous-pas). C'est la
  singularité du cône, que (d) supprime ;
- 0 J créé. C'est un cas isolé (les 149 autres sont à quelques centimètres) ; aucune perte d'énergie anormale.

**Lecture** :
- (d) supprime complètement la singularité : 0 saut d'angle, 0 approche du sommet, sur toutes les populations.
- La posture avec β = 1° est celle de la vidéo (écart à l'axe de 6,8 à 7,0° en médiane).
- Mais les butées de courbure, une chaîne de 11 contraintes couplées, ne sont **jamais tout à fait tenues**. Elles
  sont enfoncées de quelques degrés presque tout le temps (β = 1° : 12° au plus chez les meilleures, 19° chez les
  tombées). La résolution en vitesse converge mal le long de la chaîne. Il n'y a pas d'énergie créée, mais la limite
  est « molle ».
- Les grimpes de la v1 se sont faites avec une queue libre dans un cône de 30° : changer la queue sans réentraîner
  casse une partie des démarches (graine 1). Les écarts de hauteur des meilleures ne jugent donc pas (d) lui-même ;
  il faudra réentraîner.
- (d) coûte +49 à +59 % en entraînement, en plus du ×2,2 de C2.

## 5 ter. Dernier tour : β = 1° et 2,5°, ordre actuel ou alterné (avec (b)), et décision

**Décisions de l'utilisateur** :
- (b) est retenu définitivement ;
- des butées enfoncées jusqu'à 12° ne respectent pas la règle du projet (0,5° depuis B2), d'où un dernier tour de
  mesure ;
- il porte sur quatre configurations, toutes avec (b) : β = 1° et β = 2,5° (le second correspond à 30° de virage
  cumulé), chacun avec l'ordre actuel des butées de queue, puis avec un sens de parcours alterné à chaque passe (racine
  → bout, puis bout → racine) ;
- règle de décision, appliquée par moi : voir plus bas.

**Méthode** :
- même méthode, en lecture seule ;
- l'alternance utilise des copies des deux noyaux du solveur (`evo/diag_alterne.py` : mêmes signatures, mêmes
  opérations, seul le sens de parcours du bloc des butées de queue change aux passes impaires), substituées le temps de
  la mesure. Sans butées du corps, elles redonnent le moteur au bit près (test) ;
- **enfoncement** : la pénétration de la butée de queue la plus enfoncée, en degrés, à chaque sous-pas après la
  projection. Son p95 porte sur tous les sous-pas des 150 grimpes (histogrammes à pas de 0,05° jusqu'à 2°, la valeur
  donnée est la borne haute de la classe).

Runs : 38396961009 à 38397039239 ; `pytest` sur le runner : 162 passent (38396947215). Le moteur tel quel est
identique au run pour toutes les créatures.

**Les 50 meilleures de la génération 200** (150 grimpes) :

| configuration | posture : écart à l'axe médian ; p95 | enfoncement des butées de queue : p95 ; max | grimpes avec > 0,5° | sauts d'angle ; sommet du cône | énergie créée | queue étirée max | liens > 0,2 % avant projection (ms moyennes) | Δh médiane ; min | tombées |
|---|---|---|---|---|---|---|---|---|---|
| tel quel (cône) | 25,4° ; 30,0° | ≤ 0,05° ; 0,0° | 0 | 6 ; 11 | 0 J | 0,6 % | 1 372 | 0 ; 0 | 0 |
| (b) (cône) | 25,6° ; 30,0° | ≤ 0,05° ; 0,0° | 0 | 9 ; 12 | 0 J | 0,6 % | 1 350 | −0,04 ; −8,81 m | 0 |
| (b) + β = 1° | 6,9° ; 10,2° | ≤ 1,20° ; 11,7° | 150 | 0 ; 0 | 0 J | 3,9 % | 51 | −2,62 ; −45,61 m | 33 |
| (b) + β = 1°, alterné | 7,0° ; 10,5° | ≤ 1,90° ; 11,1° | 150 | 0 ; 0 | 0 J | 3,7 % | 58 | −2,59 ; −45,58 m | 35 |
| **(b) + β = 2,5°** | **8,9° ; 17,5°** | **≤ 1,05° ; 14,6°** | 117 | 0 ; 0 | 0 J | 4,0 % | 26 | −0,39 ; −45,59 m | 17 |
| (b) + β = 2,5°, alterné | 8,9° ; 17,5° | ≤ 1,60° ; 27,0° | 141 | 0 ; 0 | 0 J | 3,2 % | 32 | −0,35 ; −45,49 m | 15 |

Par graine (écart médian ; enfoncement p95) :

| | graine 0 | graine 1 | graine 2 |
|---|---|---|---|
| β = 1° | 5,1° ; 0,70° | 8,1° ; 1,60° | 6,9° ; 1,00° |
| β = 1° alterné | 5,1° ; 1,10° | 8,2° ; 3,00° | 7,0° ; 1,60° |
| β = 2,5° | 6,9° ; 0,30° | 14,3° ; 1,65° | 8,7° ; 0,35° |
| β = 2,5° alterné | 6,9° ; 0,50° | 14,4° ; 3,00° | 8,7° ; 0,55° |

**Les créatures tombées de la génération 200** (293) :

| configuration | posture : écart médian ; p95 | enfoncement p95 ; max | sauts ; sommet | énergie créée | queue étirée max ; > 5 % |
|---|---|---|---|---|---|
| tel quel | 29,5° ; 30,0° | ≤ 0,05° ; 150° | 196 ; 206 | 0,1 J | 43,8 % ; 7 |
| (b) | 29,5° ; 30,0° | ≤ 0,05° ; 150° | 200 ; 211 | 0 J | 6,9 % ; 1 |
| (b) + β = 1° | 7,0° ; 11,5° | ≤ 1,55° ; 19,3° | 0 ; 0 | 0,1 J | 9,8 % ; 2 |
| (b) + β = 1°, alterné | 7,1° ; 12,0° | ≤ 3,00° ; 24,1° | 0 ; 0 | 0 J | 9,2 % ; 2 |
| (b) + β = 2,5° | 13,2° ; 21,7° | ≤ 1,60° ; 22,1° | 0 ; 0 | 2,7 J | 11,2 % ; 10 |
| (b) + β = 2,5°, alterné | 13,0° ; 22,0° | ≤ 3,00° ; 33,1° | 0 ; 0 | 0,3 J | 9,3 % ; 8 |

**Coût** (runner, en alternance) :
- moteur scalaire avec (b) : ×1,20 à ×1,21 pour les quatre configurations, ×1,15 pour (b) avec le cône ;
- évaluateur batché : cône 12,36 s, β = 2,5° 19,35 s (**×1,57**), β = 1° 19,72 s (×1,60) ;
- l'alternance ne change pas le nombre d'opérations.

**Décision, par la règle de l'utilisateur** :
1. **Posture des 50 meilleures, écart médian ≤ 10°** : les quatre configurations passent (6,9 / 7,0 / 8,9 / 8,9°).
2. **Enfoncement le plus faible (p95, puis max), à coût comparable** : **β = 2,5° dans l'ordre actuel** (p95 ≤ 1,05°,
   max 14,6°), devant β = 1° (≤ 1,20°). L'alternance aggrave l'enfoncement dans les deux cas (≤ 1,60° et ≤ 1,90°),
   pour le même coût ; elle est écartée.
3. **p95 ≤ 1,05° : entre 0,5° et 2°**, c'est le cas 4 de la règle. On enchaîne sur l'étape 3 (code derrière drapeaux,
   tests, `pytest` sur le runner) puis sur l'étape 4 (essai de 5 générations, réentraînement des 3 graines), en
   documentant la tolérance de la queue dans le rapport.

**Tolérance de la queue, à documenter** :
- les butées de courbure de la queue tiennent à 1,05° près au p95, mais peuvent s'enfoncer ponctuellement jusqu'à
  14,6° (les meilleures, ici avec des génomes entraînés sous le cône) ;
- la chaîne des 11 butées couplées converge moins bien que des butées isolées ;
- la règle de 0,5° de B2 reste celle des butées articulaires et des pieds.

## 6. Question pour la v2 (hors chantier D) : le score « hauteur à 10 s »

Le score lit la hauteur à t = 10 s pile. Une créature qui a lâché le mur et tombe est notée **à l'endroit où elle se
trouve à cet instant** : en l'air, elle peut valoir 10 m de plus que si elle avait touché le sol un peu plus tôt (n°677 :
−8,99 m tel quel, +1,85 m avec une variante qui ne change que le moment du décrochage).
- Dans les mesures ci-dessus, 22 à 36 créatures tombées de la génération 200 changent ainsi de destin, de −2,5 à
  +43,6 m, selon la variante.
- C'est un artefact de mesure, présent dans toutes les versions, B2 comme C2.
- À traiter dans la conception de la v2. Pistes, sans en retenir aucune : noter une créature qui chute à la hauteur où
  elle touchera le sol, la noter au sol dès qu'elle a lâché toutes ses prises, ou prendre le minimum sur la dernière
  seconde.
