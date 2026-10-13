# Chantier D : projection propre (étapes 3 et 4)

Diagnostic : `docs/chantier_d_diagnostic.md`. Branche `claude/chantier-d`. Rien n'est fusionné sur `main`.

## 1. Le moteur D

**Décision de Tom** (après l'arrêt sur la créature inerte, §3) :
- (b), le report dissipatif, est gardé ;
- (d), la courbure de queue, est écarté ;
- les mains restent de leur côté de l'axe ;
- l'angle du cône de queue est choisi par la mesure, sans créer de nouveau seuil.

| Drapeau (`config.py`) | Valeur | Effet |
|---|---|---|
| `CLEAN_PROJECTION` | True | après la projection, v += α·Δp/h, avec α = min(1, −2B/A) si B < 0, sinon 0 (B = Σ m·v·Δv, A = Σ m·\|Δv\|²) : le report ne peut que retirer de l'énergie cinétique |
| `HAND_LIMITS`, `HAND_AXIS_MARGIN_DEG` | True, 0° | (NECK, PELVIS, L_HAND / R_HAND), u ∈ [m, 180° − m], comme les pieds ; butées 22 et 23 |
| `TAIL_CONE_DEG` | **15°** (C2 : 30°) | cône de queue de C2, angle choisi au §4 |
| `TAIL_CURVATURE_LIMITS` | False | candidat (d), exploré puis écarté (§3) ; code gardé |

**Compatibilité** :
- les drapeaux absents de la config d'un run valent False (`evolution.LEGACY_DEFAULTS`) ;
- B2 et C2 se rejouent tels quels : leur `config.json` porte `TAIL_CONE_DEG = 30` (C2) ;
- le report est dans les trois implémentations (`physics.projection_velocity` en numba et en référence Python, et
  `batch._simulate_block`) ;
- étape `report_projection` dans l'audit d'énergie.

**Tests** :
- `tests/test_chantier_d.py` (23 tests) :
  - scalaire = batché **au bit près**, avec pied, main et queue engagés et le report actif ; numba = Python à 1e-12 ;
  - le report n'ajoute jamais d'énergie cinétique ;
  - main lancée vers l'axe arrêtée dessus ; queue lancée contre le cône ; départ hors bornes ;
  - aucune énergie créée ; les quatre créatures du diagnostic ;
  - drapeaux ;
  - tests de la courbure gardés ;
- les tests de B2, de C2 et des outils de mesure restent sur le moteur de la v1 ;
- seuils de la créature inerte (`tests/test_creature.py`, PASSATION §10) **inchangés**.

## 2. Vérifications sur le runner

- `pytest` : **185 passent**, 0 échec.
  - Run 38410626549 : moteur D à 15°.
  - Run 38419142447 : avec les runs du chantier D restaurés. Le test des runs locaux rejoue au bit près les champions de C2 à 30°, C2 à 6°, B2 et `runs/chantier_d/S`, chacun avec ses drapeaux.
- Garde-fou de chaque job de mesure : champions de C2 et de B2 rejoués au bit près.
- Moteur de la v1 identique au run pour toutes les créatures mesurées.

## 3. Candidat (d) écarté : la créature inerte

Avec (b) et la courbure de queue (β = 2,5°), la créature inerte tombe sur la pointe de sa queue. La queue, tenue droite,
fait échasse :
- la résolution en vitesse (30 passes) ne fait pas converger la chaîne de 12 butées couplées, et la queue fléchit d'un
  rien à chaque sous-pas ;
- la projection la redresse en soulevant le torse d'environ 2 mm par sous-pas, à vitesse nulle, donc le report n'a
  rien à retirer.

Mesures sur le PC :

| Moteur | Hauteur finale | Énergie créée | Queue max |
|---|---|---|---|
| C2 (v1, cône 30°) | −8,45 m | 0,30 J (0,1 cm) | 7,8 % |
| (b) seul, cône 30° | −8,53 m | 0,09 J (0,0 cm) | 5,4 % |
| (d) seul, β = 2,5° | −8,56 m | 6,56 J (2,9 cm) | 10,0 % |
| (b) + β = 2,5° | **−7,74 m** | **8,16 J (3,7 cm)** | 5,5 % |
| (b) + β = 1° | −7,82 m | 10,54 J (4,7 cm) | 5,5 % |
| (b) + β = 5° | −8,94 m | 6,99 J (3,1 cm) | 5,5 % |
| (b) + β = 2,5°, 60 passes | −7,82 m | 9,29 J (4,2 cm) | 4,4 % |
| (b) + β = 2,5°, 120 passes | −7,82 m | 6,95 J (3,1 cm) | 3,1 % |

Toutes les variantes avec la courbure dépassent le seuil validé de 6 J. Le code reste derrière son drapeau (False).

## 4. Choix du cône : 10°, 15° et 30°

Mesure en lecture seule, avant tout réentraînement, sur les génomes des runs de la v1 rejoués avec le moteur D.
- Outil : `diag-projection --variantes tel_quel D10 D15 D30`.
- Runs 38408822669 à 38408880542.
- « tel_quel » est le moteur de la v1 du run (C2 à 30°, ou B2 pour 868 et 760).

**Créature inerte** (runner), contre ses seuils actuels :

| Moteur | Hauteur finale (−9 à −7,8 m) | Énergie créée (< 6 J) | Queue max (< 10 %) | Glissement au sol, 3 dernières s (< 5 cm, PC) |
|---|---|---|---|---|
| v1 (C2, 30°) | −8,45 m | 0,30 J | 7,85 % | — |
| D, 10° | −8,32 m | 1,03 J | 5,36 % | **5,97 cm** |
| D, **15°** | −8,37 m | 0,39 J | 5,36 % | 0,45 cm |
| D, 30° | −8,53 m | 0,12 J | 5,36 % | 0,15 cm |

**Règle de Tom** : l'angle le plus serré qui respecte, mains comprises, tous les seuils actuels de la créature inerte.
- 10° respecte les trois seuils nommés (hauteur, énergie, queue) ;
- mais un point posé au sol glisse de 5,97 cm pendant les 3 dernières secondes. C'est un autre seuil actuel du même banc
  (`test_limp_creature_falls_and_lies_on_ground` : moins de 5 cm), qui échoue ;
- **15° est retenu.**

**Cas du diagnostic** (énergie créée ; queue max ; sorties du cône) :

| Créature | v1 | D 10° | D 15° | D 30° |
|---|---|---|---|---|
| B2 n°868 (couchée, g2 gén. 0) | 1 292,5 J ; 9,1 % | 0 J ; 0,2 % | 0 J ; 0,3 % | 0 J ; 0,3 % |
| B2 n°760 (couchée, g1 gén. 200) | 825,2 J ; 9,8 % | 0 J ; 0,8 % | 0 J ; 0,7 % | 0 J ; 0,4 % |
| C2 n°677 (queue étirée, g0) | 0 J ; 43,8 % ; 10 | 0 J ; 1,6 % ; 0 | 0 J ; 0,4 % ; 0 | 0 J ; 1,8 % ; 0 |
| C2 n°808 (en l'air, g1) | 0 J ; 1,0 % ; 16 (117°) | 0 J ; 1,0 % ; 0 | 0 J ; 1,0 % ; 0 | 0 J ; 0,8 % ; 25 (134°) |

**Populations** (génomes de la v1, moteur D) :

| Groupe | Moteur | Énergie créée : total ; max ; > 5 cm | Queue étirée max ; > 5 % | Posture de queue (écart médian ; p95) | Jambe/queue | Mains de l'autre côté |
|---|---|---|---|---|---|---|
| 50 meilleures × 3, gén. 200 | v1 | 0 J ; 0 cm ; 0 | 0,6 % ; 0 | 25,4° ; 30,0° | 4,8 % | 30,5 % |
| | D 10° | 0,02 J ; 0,01 cm ; 0 | 17,4 % ; 4 | 10,0° ; 10,0° | 2,6 % | 1,6 % |
| | D 15° | 0 J ; 0 cm ; 0 | 5,0 % ; 1 | 14,9° ; 15,0° | 3,8 % | 1,7 % |
| | D 30° | 0 J ; 0 cm ; 0 | 12,8 % ; 4 | 28,3° ; 30,0° | 4,8 % | 1,8 % |
| tombées, gén. 200 (293) | v1 | 0,13 J ; 0,05 cm ; 0 | 43,8 % ; 7 | 29,5° ; 30,0° | 6,9 % | 35,8 % |
| | D 10° | 0,04 J ; 0,02 cm ; 0 | 23,5 % ; 8 | 10,0° ; 10,0° | 1,8 % | 2,3 % |
| | D 15° | 0 J ; 0 cm ; 0 | 14,8 % ; 5 | 15,0° ; 15,0° | 3,2 % | 2,3 % |
| | D 30° | 0,12 J ; 0,06 cm ; 0 | 9,3 % ; 3 | 29,5° ; 30,0° | 7,0 % | 2,3 % |
| tombées, gén. 0 (1 128) | v1 | **606,0 J ; 68,1 cm ; 10** | 12,8 % ; 40 | 29,6° ; 30,0° | 10,7 % | 5,4 % |
| | D 10° | 10,2 J ; 2,0 cm ; 0 | 8,3 % ; 26 | 10,0° ; 10,0° | 7,1 % | 0,7 % |
| | D 15° | 5,5 J ; 0,9 cm ; 0 | 9,4 % ; 9 | 15,0° ; 15,0° | 7,9 % | 0,6 % |
| | D 30° | 3,5 J ; 0,5 cm ; 0 | 8,2 % ; 7 | 29,5° ; 30,0° | 10,8 % | 0,6 % |

**Enfoncement des butées** :
- p95 ≤ 0,05° partout, pour la queue comme pour les mains ;
- maximum des mains ≤ 0,23° ;
- les maxima de la queue (jusqu'à 169°) sont des sorties de cône par le sommet (§5) ;
- articulations et pieds ≤ 0,5° avec le moteur D (v1, tombées de la gén. 0 : 2,2° et 1,1°).

Les génomes de la v1 grimpent mal avec la butée des mains : sur les 50 meilleures, la Δh médiane est de −35,5 m à 10°
et −15,3 m à 15°. La graine 0 tenait ses mains de l'autre côté de l'axe 91,4 % du temps. C'est le réentraînement qui
juge (§6).

## 5. La singularité du cône

Un point de queue qui revient près du bassin, c'est-à-dire le sommet du cône, rend l'angle « vu du bassin » mal défini.
D'où des sauts d'angle et des sorties de cône d'un sous-pas. Mesure : un sous-pas est « singulier » si un point de queue
est à moins de 5 cm du bassin, si un angle saute de plus de 20°, ou si la queue sort du cône de plus de 0,5°. On compte
l'énergie créée hors muscles pendant ces sous-pas.

| Groupe | Moteur | Grimpes touchées | Durée cumulée | Énergie créée pendant ces sous-pas |
|---|---|---|---|---|
| 50 meilleures × 3 (génomes v1) | v1 / D 15° | 11 / 38 sur 150 | 1,25 / 19,65 s | 0 / 0 J |
| tombées gén. 200 (génomes v1) | v1 / D 15° | 206 / 196 sur 293 | 193,1 / 150,8 s | 0,110 / 0 J |
| tombées gén. 0 (génomes v1) | v1 / D 15° | 187 / 173 sur 1 128 | 239,6 / 203,4 s | **58,4** / 0,031 J |
| créature inerte | v1 / D 15° | — | 8,3 / 7,0 s | 0,190 / 0,036 J |
| **runs D, 50 meilleures × 3, gén. 200** | D 15° | **0 sur 150** | 0 s | 0 J |
| **runs D, tombées gén. 200** (366) | D 15° | 205 sur 366 | 169,5 s | **0 J** |

- La singularité reste : c'est le prix du cône sans (d).
- Elle ne touche plus aucune grimpeuse entraînée avec le moteur D.
- Elle ne crée **aucune énergie** sur les runs D. Ce qu'elle créait en v1 (58,4 J) venait des créatures couchées, que le
  report supprime. Avec le moteur D, il en reste 0,031 J sur 1 128 génomes de la v1, et 0,036 J sur la créature inerte.

## 6. Étape 4 : réentraînement

- Essai : 5 générations (run 38411261724). SHA-256 conformes. `config.json` porte `CLEAN_PROJECTION`, `HAND_LIMITS`,
  `TAIL_CONE_DEG = 15` et `TAIL_CURVATURE_LIMITS = False`. Estimation de 47 à 74 min pour 200 générations (limite :
  150 min).
- Réentraînement : run 38411711297, 200 générations × 1 000 créatures, `AUDIT_EVERY=10`. Durée 30 / 15 / 49 min.
  Archives `runs_chantier_d_S.tar.gz`, SHA-256 :
  - `77159428…a1be` ;
  - `30cb9014…2118` ;
  - `12cfa917…a7fa`.

  Extraites dans `runs/chantier_d/S` (hors git). Les artefacts expirent le 12 novembre 2026.

**Hauteurs et population** (gén. 200, graines 0 / 1 / 2 ; même script pour les deux colonnes) :

| | C2 à 30° (v1) | **D à 15°** | Vidéo (§9) |
|---|---|---|---|
| champion (meilleur score, audit) | 39,5 / 37,1 / 42,8 m | **30,9 / 40,9 / 43,6 m** | 36 m |
| plus haute | 40,0 / 37,1 / 42,8 m | 30,9 / 40,9 / 43,8 m | |
| moyenne | 29,2 / 27,1 / 34,8 m | 19,7 / 31,5 / 34,3 m | ≈ 28 m |
| médiane des 500 meilleures | 38,9 / 35,3 / 42,0 m | 29,0 / 39,8 / 43,0 m | |
| au sol | 119 / 90 / 84 | 158 / 87 / 121 | ≈ 30 |
| entre 30 et 35 m | 16 / 270 / 15 | 13 / 31 / 21 | majorité |
| période moyenne | 0,86 / 1,47 / 0,87 s | 0,81 / 1,05 / 1,33 s | 0,6 s |
| masse musculaire moyenne | 16,4 / 13,5 / 13,8 | 14,1 / 16,1 / 15,7 | 10,5 |
| gén. 0 : au sol | 378 / 389 / 361 | 364 / 384 / 348 | ≈ 450 |
| première meilleure au-delà de +5 m | gén. 3 / 6 / 3 | gén. 4 / 3 / 4 | gén. 12 (+1 m) |
| période moyenne sous 1,5 s dès | gén. 31 / 184 / 30 | gén. 35 / 24 / 29 | |
| flemme, gén. 1 à 20 : muscle moyen min ; période moyenne max | 8,6 / 6,9 / 9,2 ; 3,4 / 3,7 / 4,2 s | 8,6 / 8,1 / 9,4 ; 3,9 / 2,9 / 4,4 s | 13,2 → 7,3 ; 4,5 s |

- **Aucun champion sous 27 m.**
- La graine 0 perd 8,6 m, de 39,5 à 30,9 m. Sa démarche de la v1 passait les mains de l'autre côté de l'axe, et ce n'est
  plus possible. Ses champions sont aussi moins variés : les rangs 1 à 50 vont de 28,9 à 30,9 m.
- Les graines 1 et 2 montent un peu plus haut qu'en C2.

**Énergie** :
- **champions audités** toutes les 10 générations (`audit.csv`, 21 × 3) : 0 J créé hors muscles, aucune alerte, rejeu
  identique ; os ≤ 0,21 %, queue ≤ 0,43 % ;
- **50 meilleures et 50 au hasard de la gén. 200** (`joints --energy`) : 0 J créé hors muscles, saut à l'engagement
  d'une butée 0 J ;
- **créatures tombées des vraies populations** (`joints --fallen`, toutes) :

| Graine, gén. | Tombées C2 / D | > 5 cm C2 / D | Maximum C2 / D (cm) | Total C2 / D (J) | Queue > 5 % D (max) |
|---|---|---|---|---|---|
| 0, 0 | 378 / 364 | 3 / 0 | 50,3 / 0,29 | 216 / 1,27 | 1 (7,9 %) |
| 0, 200 | 119 / 158 | 0 / 0 | 0,0 / 0,10 | 0 / 0,16 | 2 (12,3 %) |
| 1, 0 | 389 / 384 | 4 / 0 | 34,9 / 0,20 | 172 / 0,57 | 3 (8,9 %) |
| 1, 200 | 90 / 87 | 0 / 0 | 0,0 / 0,00 | 0 / 0,00 | 0 (4,9 %) |
| 2, 0 | 361 / 348 | 3 / 0 | 68,1 / 0,87 | 218 / 3,70 | 5 (9,4 %) |
| 2, 200 | 84 / 121 | 0 / 0 | 0,1 / 0,00 | 0 / 0,00 | 1 (6,0 %) |

L'énergie créée par les créatures couchées, le défaut principal visé par le chantier D, disparaît : 606 J et 10
créatures au-delà de 5 cm en v1, contre 5,5 J et 0 créature. La queue étirée au-delà de 5 % de quelques créatures
tombées reste, et c'est une limite connue (PASSATION §10).

**Queue, pieds, mains et croisements** (`joints --tail --crossings`, 50 meilleures de la gén. 200, v1 entre
parenthèses) :

| Graine | Mains de l'autre côté de l'axe | Bras G / bras D | Jambe / queue | Pied de l'autre côté | Posture de queue (écart médian) |
|---|---|---|---|---|---|
| 0 | **0 %** (91,4 %) | **0 %** (89,2 %) | 0 % (0 %) | 0 % (0 %) | 14,8° (25,2°) |
| 1 | 0 % (0 %) | 0 % (0 %) | 0 % (6,8 %) | 0 % (0,1 %) | 14,8° (28,4°) |
| 2 | 0 % (0 %) | 0 % (0 %) | **23,4 %** (7,5 %) | 0,5 % (0 %) | 14,9° (24,2°) |

- **Les mains et les bras de la graine 0 sont réglés** : les mains ne passent plus devant la tête, et les bras ne se
  croisent plus.
- **La queue est plus droite** : 15° d'écart à l'axe au lieu de 25 à 28°. La vidéo donne 1,7 à 5,7°.
- **Critère de repli** du cône : longueur 0 %, oscillation 0 % → « garder 15° » sur les 3 graines (os de queue
  ≤ 0,28 %, oscillation ≤ 1,1 %).
- **Pénétration des 24 butées** chez les meilleures : ≤ 0,001°. Os du corps ≤ 0,08 %.
- **Le résidu jambe–queue de la graine 2 augmente** : 23,4 % du temps, sur 100 % de ses 50 meilleures. C'est le tibia
  qui croise la queue, que le cône de 15° garde plus près des jambes. B2 était à 50,1 %, C2 à 6° à 0 %.

## 7. Points ouverts pour Tom

1. **Graine 0 plus basse** : 30,9 m au lieu de 39,5 m, sous la vidéo (36 m). C'est l'effet direct de la butée des mains.
2. **Résidu jambe–queue de la graine 2** : 23,4 % à 15°. Décision du bilan v1 (n°1) toujours ouverte : collision ciblée
   tibia–queue, ou rien.
3. **Sauvegarde des runs D** : les artefacts expirent le 12 novembre 2026. Les runs ne sont ni sur `sauvegarde-runs` ni
   sur `main` (pas sans décision).
4. **Fusion sur `main`** et runs D comme runs par défaut : à décider.
5. Le score « hauteur à 10 s » (créature n°677), consigné pour la v2 (`docs/chantier_d_diagnostic.md` §6).
