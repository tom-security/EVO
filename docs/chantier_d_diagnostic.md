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
