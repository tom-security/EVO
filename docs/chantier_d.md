# Chantier D : projection propre (étapes 3 et 4)

Diagnostic et choix des correctifs : `docs/chantier_d_diagnostic.md`. Configuration retenue par la règle de décision
de Tom : (b) report dissipatif + (d) courbure de queue β = 2,5°, dans l'ordre actuel des butées, et les butées des
mains (BILAN_V1 §4.3). Branche `claude/chantier-d`, partie de `claude/chantier-d-diagnostic`.

## 1. Étape 3 : le moteur

**Trois drapeaux** dans `config.py`. Absents de la config d'un run, ils valent False (`evolution.LEGACY_DEFAULTS`) :
B2 et C2 se rejouent tels quels.

| Drapeau | Effet | Où |
|---|---|---|
| `CLEAN_PROJECTION` | après la projection, v += α·Δp/h, avec α = min(1, −2B/A) si B < 0, sinon 0 (B = Σ m·v·Δv, A = Σ m·\|Δv\|²) | `physics.projection_velocity` (numba, référence Python), `batch._simulate_block`, étape `report_projection` de l'audit |
| `TAIL_CURVATURE_LIMITS`, `TAIL_CURVATURE_DEG = 2.5` | (NECK, PELVIS, TAIL_0) dans ±β, puis (point précédent, TAIL_k, TAIL_k+1) à ±β de l'alignement ; indices 10 à 21, comme le cône | `creature.body_limits` |
| `HAND_LIMITS`, `HAND_AXIS_MARGIN_DEG = 0` | (NECK, PELVIS, L_HAND / R_HAND), u ∈ [m, 180° − m], comme les pieds ; indices 22 et 23 | `creature.body_limits`, groupe « mains » de `limit_groups` |

Les courbure et mains ne s'appliquent qu'avec `JOINT_LIMITS` et `BODY_LIMITS`. Le report ne s'applique qu'aux
créatures (`World.clean_projection`, posé par `Creature`) : les bancs de la phase 1 gardent la projection seule.

**Tests** (`tests/test_chantier_d.py`, 21 tests) :
- disposition des 24 butées et posture de repos (queue droite, au centre de chaque butée ; mains à 21° de l'axe) ;
- le report retire la vitesse qui entre dans le sol et n'ajoute jamais d'énergie cinétique (200 postures faussées) ;
- numba = Python à 1e-12 près ;
- scalaire = batché **au bit près**, avec pied, main et queue engagés et le report actif ;
- main lancée vers l'axe à 6 et 10 m/s : arrêtée dessus, sans gain d'énergie ;
- queue lancée de côté à 2, 5 et 10 m/s : courbure tenue à 0,6° près, sans gain d'énergie, os de queue < 1 % ;
- départ hors bornes (queue pliée de 40°, pied et main de l'autre côté de l'axe) ;
- aucune énergie créée sur la grimpeuse et la marche ; les 24 butées tenues tout du long (queue à 0,8° près) ;
- les quatre créatures du diagnostic, rejouées avec le moteur D (génomes des runs de la v1) : 0 J créé, queue ≤ 0,74 %
  (moteur de la v1 : 1 292,5 J et 825,2 J pour les couchées, queue à 43,8 %, 16 sorties de cône) ;
- drapeaux : absents = moteur de C2 ; un nouveau run les enregistre.

**Tolérance de la queue** (à garder en tête pour la suite) :
- les 12 butées de courbure forment une chaîne couplée, moins bien résolue que des butées isolées : enfoncement p95
  ≤ 1,05°, max 14,6° (diagnostic), contre 0,5° pour les articulations, les pieds et les mains ;
- une queue pliée au-delà de ses butées revient peu à peu : depuis 40°, sous 1° en 0,55 s et à 0 en 1 s (cône de C2 :
  1/8 s). La résolution en vitesse (BETA = 0) empêche seulement l'aggravation, et c'est la projection qui redresse la
  chaîne.

## 2. Arrêt : la créature inerte

`pytest` local : 178 passent ; 3 échecs connus (rejeu sous Windows) ; **2 échecs** dans `tests/test_creature.py`, sur
la créature inerte (le moteur par défaut est maintenant le moteur D) :
- `test_limp_creature_falls_and_lies_on_ground` : elle finit à **−7,74 m**, hors de la plage de la vidéo
  (−9 à −7,8 m) ;
- `test_no_mechanism_but_muscles_creates_energy[inerte]` : **8,16 J** créés, au-delà du seuil propre à ce cas (6 J).

Ces deux seuils sont une décision validée (PASSATION §10 : « créature inerte avec butées du corps : hauteur dans la
plage de la vidéo, seuils propres à ce cas (énergie < 6 J, queue < 10 %) »). Les changer touche une décision validée :
**arrêt**. Le runner n'a pas été lancé ; rien n'est fusionné.

**Mécanisme** :
- la créature inerte tombe sur la pointe de sa queue, que les butées de courbure tiennent droite, comme une échasse
  sous le corps ;
- la résolution en vitesse (30 passes) ne fait pas converger la chaîne de 12 butées couplées : la queue fléchit d'un
  rien à chaque sous-pas (−0,07°) ;
- la projection la redresse, ce qui soulève le torse d'environ 2 mm par sous-pas, à vitesse nulle. Le report n'a donc
  rien à retirer (α ≈ 0) ;
- en tout, 228 sous-pas « créateurs » (plus de 1 mJ), les plus forts vers 1,03 s ;
- ce n'est pas un défaut de l'implémentation : l'outil du diagnostic, sur le moteur de la v1, donne 8,154 J pour
  « dissipatif:courbure2.5 ».

Le diagnostic ne l'avait pas vu, parce qu'il n'avait pas rejoué la créature inerte avec (d). Sur les vraies créatures
tombées (293, gén. 200), (b) + β = 2,5° créait 2,7 J **en tout**.

**Options mesurées** (créature inerte, PC ; la hauteur et l'énergie se mesurent sans rejeu au bit près) :

| Moteur | Hauteur finale | Énergie créée | Queue max |
|---|---|---|---|
| C2 (v1, cône 30°) | −8,45 m | 0,30 J (0,1 cm) | 7,8 % |
| (b) seul, cône 30° | −8,53 m | 0,09 J (0,0 cm) | 5,4 % |
| (d) seul, β = 2,5° | −8,56 m | 6,56 J (2,9 cm) | 10,0 % |
| **retenu : (b) + β = 2,5°** | **−7,74 m** | **8,16 J (3,7 cm)** | 5,5 % |
| (b) + β = 1° | −7,82 m | 10,54 J (4,7 cm) | 5,5 % |
| (b) + β = 5° | −8,94 m | 6,99 J (3,1 cm) | 5,5 % |
| (b) + β = 2,5°, 60 passes | −7,82 m | 9,29 J (4,2 cm) | 4,4 % |
| (b) + β = 2,5°, 120 passes | −7,82 m | 6,95 J (3,1 cm) | 3,1 % |

Toutes les variantes avec la courbure de queue dépassent 6 J. Seul le cône de C2 reste sous ce seuil, mais il garde la
singularité au sommet du cône.

**Décision attendue** :
1. **Garder la configuration retenue** et fixer, pour le moteur D, des seuils propres au cas inerte :
   - énergie < 10 J (≈ 4,5 cm, sous le seuil d'audit de 5 cm, qui reste le garde-fou de l'étape 4) ;
   - hauteur entre −9 et −7,7 m ;
   - (recommandé) le cas est isolé : 2,7 J en tout sur 293 créatures tombées ; les audits et `--fallen` de l'étape 4
     diront si les populations en souffrent.
2. **β = 5°** : la hauteur revient dans la plage (−8,94 m), mais 6,99 J restent au-delà de 6 J. β = 5° n'était pas
   dans le dernier tour (posture et enfoncement : §5 bis du diagnostic).
3. **Renoncer à (d)** : (b) + cône de 30° + mains passent tous les seuils de la v1, mais gardent les sorties de cône
   d'un sous-pas (singularité au sommet du cône).
