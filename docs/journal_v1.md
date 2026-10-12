# Journal de la v1 : C2, nettoyage, gel

Mission en autonomie du 12 octobre 2026 (consigne de Tom : finir C2, nettoyer sans changer le comportement,
préparer le gel). Chaque étape est notée ici et commitée, pour reprendre si la session s'interrompt.

**Règles de la mission** :
- le runner GitHub (ubuntu-24.04) fait foi pour les rejeux, les tests et les mesures de runs ;
- arrêt immédiat si :
  - un test échoue ou un rejeu n'est plus identique ;
  - de l'énergie est créée hors muscles ;
  - un champion de la génération 200 passe sous 27 m ;
  - il faudrait toucher à une décision validée (§10), supprimer ou forcer quoi que ce soit ;
  - l'essai prévoit plus de 150 min par graine ;
  - le repli se déclenche aussi à 30°.

**Branches** :
- `claude/chantier-c2-butees-corps`, partie de `main` (`d9317eb`) ;
- `claude/nettoyage-v1`, partie de la branche C2.

Rien n'est fusionné sur `main`.

## Avant la mission (rappel)

- **Environnement local** : Python 3.11.9, numpy 2.4.6, numba 0.67.0, pygame 2.6.1, dans `code/.venv`.
- **pytest sous Windows** : 130 passent, 3 échouent. Les 3 échecs sont les rejeux de
  `test_local_runs_replay_with_their_own_flag`.
- **Rejeu sous Windows**, contre les hauteurs stockées :
  - graine 0 : −0,7 mm ;
  - graine 1 : −24,0 cm ;
  - graine 2 : −3,05 cm.
- **Runner** : rejoue les champions B2 au bit près (run 38255551159).
- **Mode `analyse`** (run 38256166464) : il redonne les chiffres de C1 à l'identique. Exemples :
  - pied de l'autre côté de l'axe : 0 / 84,2 / 38,5 % ;
  - croisements jambe/queue : 14,0 / 72,0 / 50,1 %.

## Étape 1 : refactor `limit_joints` (commit 1 de C2)

**Fait** :
- `World.limit_joints` (Q, 3) : les butées portent sur leurs propres triplets, séparés des muscles.
- `set_joint_limits(..., triplets=None)` donne par défaut les 8 articulations, comme en B2.
- Les noyaux numba et Python, et l'évaluateur batché (`pack()` → `lim_joints`), lisent ces triplets. Aucune
  opération flottante ne change.

**Chiffres** :
- pytest local (Windows) : 130 passent ; les 3 échecs connus du rejeu Windows restent les mêmes ; 179 s.
- Hauteurs rejouées sous Windows **identiques à celles d'avant le refactor** (+34,240889724 / +33,207706444 /
  +35,293234546 m) : même suite d'opérations.

**Runner** : `mode=pytest`, 133 passent, dont le rejeu au bit près des champions B2 (run 38260091485). Commit 1
validé.

## Étape 2 : butées du corps (commit 2 de C2), ARRÊT

**Écrit, pas commité** (reste dans l'arbre de travail) :
- `config.py` : `BODY_LIMITS`, `FOOT_AXIS_MARGIN_DEG`, `TAIL_CONE_DEG = 6.0` et les seuils du critère de repli ;
- `creature.body_limits()` et `limit_groups()`, et les 14 butées posées après les 8 articulations ;
- `LEGACY_DEFAULTS["BODY_LIMITS"] = False`.

**Contrôle à vide (marche écrite à la main)** :
- 22 butées ;
- au repos, pieds à ±140,3° et queue à −180°, au centre du cône (6° de marge) ;
- 10 s sans pénétration (0,000°) ;
- queue en butée ≈ 3 000 sous-pas sur 4 800 ;
- hauteur +2,44 m (+3,75 m avant C2).

**Arrêt : 3 tests existants échouent** (pytest local, hors les 3 rejeux Windows connus).

1. **`test_creature.py::test_no_mechanism_but_muscles_creates_energy[inerte]`**. C'est le point de fond.

   | Créature inerte, 10 s | B2 | C2 à 6° | C2 à 30° |
   |---|---|---|---|
   | énergie créée hors muscles | 0,13 J | **4,39 J** (1,97 cm) | 0,30 J (0,13 cm) |
   | maximum par sous-pas | — | 0,186 J (0,83 mm) | 0,106 J (0,48 mm) |
   | seuil du test (1e-4 × énergie de chute) | 0,23 J | 0,23 J | 0,23 J |

   - Seuils d'audit **non dépassés** : `AUDIT_MAX_CREATED_HEIGHT` = 5 cm, saut d'engagement max 0,28 mm pour 5 mm.
   - Mécanisme :
     - l'énergie apparaît seulement **après la chute** (tombée à 1,15 s), à 84 % entre 2 et 4 s ;
     - elle apparaît dans des sous-pas où la queue est **à la fois en butée de cône et posée au sol**, en
       moyenne 9,9 butées de queue actives et 4,4 points de queue au sol ; c'est le cas de 100 % de l'énergie
       créée ;
     - la projection (ordre validé : liens, butées, sol) pousse la queue dans le cône puis la remonte au sol, et
       chaque passe y gagne un peu d'énergie potentielle ;
     - c'est la famille du cas « posture sur-contrainte » de B2.
   - Les deux grimpeuses du même test (aléatoire et marche écrite à la main) passent.
2. **`test_creature.py::test_limp_creature_falls_and_lies_on_ground`** :
   - la créature couchée finit à −7,95 m (C2) au lieu de −8,73 m (B2), parce que la queue tenue droite cale le
     corps ;
   - à 30°, elle finit à −8,45 m ;
   - le test exige (−10,3 ; −8,3), une borne de l'ère B2 ;
   - −7,95 m reste dans la plage de la vidéo (−9 à −7,8 m), que le même test vérifie aussi et qui passe.
3. **`test_joint_limits.py::test_batch_matches_scalar_bit_for_bit_with_limits_engaged`** : artefact du test, qui
   suppose 8 butées (`broadcast (8,) (22,)`). La correction consiste à ne compter que les 8 articulations (ou à
   poser `BODY_LIMITS=False` dans ce test B2). Elle est sans enjeu.

**Décision attendue de Tom** :
- pour l'énergie de la créature inerte, trois options :
  - accepter (seuil du test ramené au seuil d'audit, avec ce constat en commentaire) ;
  - faire ne pas agir le cône sur les points de queue posés au sol (nouveau comportement, à valider) ;
  - passer directement à 30°, qui dépasse encore le seuil du test (0,30 J pour 0,23 J) ;
- pour le test de la créature couchée : adapter la borne à la plage de la vidéo ?

**Prochaine étape** : selon la décision. Le code du commit 2 est prêt dans l'arbre de travail ; il reste
`tests/test_body_limits.py` à écrire.

## Étape 2 bis : décisions de Tom appliquées, nouvel ARRÊT

**Décisions de Tom (appliquées, non commitées)** :
1. créature couchée : borne de hauteur alignée sur la plage de la vidéo (−9 à −7,8 m), avec le constat en
   commentaire ;
2. test batché : seules les 8 butées articulaires sont comptées ;
3. énergie de la créature inerte : seuil propre à ce cas avec `BODY_LIMITS`, de 6 J, mécanisme en commentaire ;
   0,23 J partout ailleurs ;
4. à ajouter au rapport C2 : l'énergie créée sur les créatures tombées des vraies populations ; arrêt si l'une
   d'elles dépasse 5 cm.

**Fait** :
- `tests/test_body_limits.py` : 15 tests, tous verts en local, en 16 s. Ils couvrent :
  - la disposition des 22 butées et le repos ;
  - le pied libre et le pied tenu lancés vers l'axe ;
  - la queue lancée contre le cône à 2, 5 et 10 m/s ;
  - le départ hors bornes, avec retour par le côté court ;
  - scalaire = batché au bit près, avec le pied et la queue engagés ;
  - numba = Python avec les 22 butées ;
  - l'énergie sur deux grimpes ;
  - le drapeau et `config.json`.
- `test_local_runs_replay_with_their_own_flag` est étendu à `runs/butees_corps/S`.
- Mesures de mise au point (sans gravité ni sol, sans muscles) :

  | Cas | Engagée | Pénétration | Énergie |
  |---|---|---|---|
  | pied libre à 6 m/s | 213 sous-pas | 0,000° | strictement décroissante |
  | pied tenu, corps à 4 m/s | 246 sous-pas | 0,000° | strictement décroissante |
  | queue à 10 m/s | 2 978 sous-pas | 0,000° | strictement décroissante |

  Erreur des os de queue sur la queue lancée à 10 m/s : 1,7e-5.
- pytest local : 144 passent, 4 échouent : les 3 rejeux Windows connus, et le cas ci-dessous.

**Arrêt : `test_creature.py::test_limp_creature_falls_and_lies_on_ground`, assertion `bench.max_tail < 0.08`.** Elle
ne s'était pas montrée au premier passage, parce que le test s'arrêtait à l'assertion de hauteur, corrigée depuis.

| Créature inerte (banc du sol), erreur de longueur de la queue | B2 | C2 à 6° | C2 à 30° |
|---|---|---|---|
| maximum | 7,05 % (t = 1,02 s, impact) | **9,37 %** (t = 1,69 s) | 7,85 % (t = 1,69 s) |
| temps au-delà de 1 % | 25 ms | **1 310 ms** | 90 ms |
| temps au-delà de 5 % | 10 ms | **662 ms** | 58 ms |
| erreur des os du corps | 0,13 % | 0,13 % | 0,18 % |

- Le mécanisme est le même que pour l'énergie : après la chute, la queue est à la fois en butée de cône et au sol.
- Ce n'est plus un pic d'impact : la queue reste étirée de plus de 5 % pendant 0,66 s.
- C'est la grandeur même du critère de repli (erreur de longueur de la queue au-delà de 1 %). Ce critère est
  défini sur les 50 meilleures grimpeuses de la génération 200, pas sur les créatures tombées.

**Décision attendue de Tom** :
- accepter avec un seuil propre au cas inerte avec `BODY_LIMITS` (par exemple 10 %), comme pour l'énergie ;
- ou considérer que le repli à 30° est déjà justifié par ce cas ;
- ou autre chose.

**Prochaine étape** : selon la décision, puis commit 2, `pytest` sur le runner et la suite de C2.

## Étape 2 ter : commit 2

**Décision de Tom** :
- erreur de longueur de la queue du cas inerte avec `BODY_LIMITS` : seuil propre de 10 % ;
- le critère de repli reste le seul juge entre 6° et 30° ;
- si un troisième test ou une troisième mesure tombe pour ce même mécanisme, repli direct à 30° ;
- si une créature tombée d'une vraie population dépasse les seuils d'audit (énergie 5 cm, queue 5 %), arrêt.

**pytest local** : 145 passent ; les 3 échecs sont les rejeux Windows connus ; 211 s.

**Prochaine étape** : `mode=pytest` sur le runner, puis commit 3 (mesures `--tail`, `morpho`, `planche`).

**Runner** : `mode=pytest`, 148 passent (run 38264932068). Commit 2 validé ; les runs B2 se rejouent au bit près
sans les butées du corps.

## Étape 3 : commit 3 (outils de mesure)

**Fait** :
- `joints --tail` et `joints --fallen` (`evo/tail_audit.py`) ;
- `morpho` (`evo/morphology.py`) ;
- `planche` (`evo/planches.py`) ;
- `graphs --labels` ;
- le workflow de la branche accepte deux runs sources pour `pytest` et `analyse` ;
- 8 tests dans `tests/test_tail_audit.py`.

**Chiffres** :
- pytest local : 153 passent ; les 3 échecs sont les rejeux Windows connus.
- Benchmark `--pop 1000` sur le PC, en alternance :

  | Code | Mesures | Médiane |
  |---|---|---|
  | `main` (B2) | 13,75 / 12,01 / 11,71 s | 12,0 s |
  | branche (C2) | 25,99 / 25,68 / 27,80 s | 26,0 s |

  Soit **×2,2** avec les 14 butées du corps. L'estimation du plan était de +40 à +60 % : la queue est presque
  toujours en contact.

**Prochaine étape** : `pytest` sur le runner, puis l'essai de 5 générations (lancé en parallèle).

**Runner** : `mode=pytest`, 156 passent (run 38266405208). Commit 3 validé.

## Étape 4 : essai de 5 générations (run 38266417518)

**Durée des jobs** : 100 / 197 / 77 s pour les graines 0 / 1 / 2.

**SHA-256** : les 3 archives sont OK. Les runs sont extraits dans `runs/essai/S`.

**`config.json`** : `JOINT_LIMITS: true`, `BODY_LIMITS: true`, `TAIL_CONE_DEG: 6.0`.

| Graine | Éval. gén. 0 (compilation numba comprise) | Éval. des gén. suivantes (médiane) | Gén. 5 : meilleure | Gén. 5 : au sol |
|---|---|---|---|---|
| 0 | 41 s | 8,1 s | +3,21 m | 28 |
| 1 | 85 s | 18,1 s | +2,68 m | 27 |
| 2 | 31 s | 5,8 s | +3,17 m | 18 |

Pour comparaison, B2 prenait 4,2 à 5,1 s par génération dans l'ancien conteneur.

**Estimation pour 200 générations** : ≈ 27 / 60 / 19 min, sous les 150 min par graine.

**Audits de la génération 0** : 0 J créé hors muscles, sauts max 0 J, 191 à 217 engagements de butées.

## Étape 5 : run complet lancé, mesures de référence B2

Lancés à 15:00 UTC :
- run complet `butees_corps`, 200 générations : 38266975229 ;
- `joints --tail` sur B2 (gén. 200, 50 meilleures et 50 au hasard) : 38266985028 ;
- `joints --fallen` sur B2, gén. 0 et 200 : graine 0 → 38266995055, graine 1 → 38267006193, graine 2 → 38267016651.

**Prochaine étape** :
- rapatrier et vérifier les runs C2 ;
- `pytest` avec `source_run_id` (rejeu C2) ;
- `--tail`, `--crossings`, `--energy` et `--fallen` sur C2 ;
- critère de repli.

## Étape 5 bis : mesures de référence B2, ARRÊT

Les 4 analyses sont vertes et rapatriées. Toutes les hauteurs rejouées sont identiques au run.

**`joints --tail` sur B2** (aucun cône dans le moteur, mesure faite contre 6°), 50 meilleures de la génération 200 :

| Graine | Os de queue, max | Grimpes étirées | Oscillation | Écart max à l'axe (médiane / p95) | Verdict |
|---|---|---|---|---|---|
| 0 | 0,70 % | 0 % | médiane 0,3 %, max 0,4 % | 71,8° / 164,3° | garder 6° |
| 1 | 1,09 % | 0 % | médiane 0,3 %, max 0,5 % | 32,8° / 64,3° | garder 6° |
| 2 | 0,49 % | 0 % | médiane 0,3 %, max 0,4 % | 22,0° / 42,5° | garder 6° |

Le verdict « garder 6° » est attendu en B2, puisque le cône n'existe pas encore dans le moteur. Ce sont les chiffres
de référence du critère.

**`joints --fallen` sur B2 : seuil d'audit d'énergie dépassé (5 cm), condition d'arrêt.**

| Run B2 | Tombées | > 5 cm | Max (J / équivalent hauteur) | Queue > 5 % | Os du corps, max |
|---|---|---|---|---|---|
| graine 0, gén. 0 | 392 | 5 | 200 J / 85 cm | 6 | 5,1 % |
| graine 0, gén. 200 | 61 | 0 | — | 0 | 1,8 % |
| graine 1, gén. 0 | 408 | 3 | 151 J / 61 cm | 1 | 3,7 % |
| graine 1, gén. 200 | 121 | 7 | **825 J / 4,25 m** | 9 | 4,7 % |
| graine 2, gén. 0 | 383 | 6 | **1 292 J / 6,45 m** | 6 | 6,4 % |
| graine 2, gén. 200 | 51 | 0 | 0,003 J | 0 | 2,7 % |

- Ce sont des runs **B2**, sans butées du corps : c'est un phénomène du moteur déjà validé, jamais mesuré, parce que
  les audits ne portaient que sur les champions et sur des échantillons.
- Les créatures en cause finissent couchées à une hauteur normale (−7,86 à −9,67 m) : l'énergie créée ne les fait pas
  remonter. Leurs rangs vont de 499 à 1 000 ; une seule est au rang 499, juste sous la limite des 500 survivantes
  (graine 2, gén. 0).
- Ce sont des créatures dont les muscles continuent d'agir au sol (masse musculaire 6 à 18). Le mécanisme précis
  reste à établir ; ce sera un rejeu étape par étape, sur le runner.

**Pendant ce temps** : le run complet C2 `butees_corps` (38266975229) continue. La graine 1 est terminée, les graines
0 et 2 tournent. Ses artefacts seront conservés 30 jours.

**Non commité** : `evo/morphology.py` (étiquettes de fin sans chevauchement, via `charts._end_labels`).

**Décision attendue de Tom** :
- la règle d'arrêt (5 cm) s'applique-t-elle aussi aux créatures tombées des runs B2 de référence, ou seulement à C2 ?
- faut-il diagnostiquer ce mécanisme du moteur validé (rejeu étape par étape des pires cas, n°868 et n°760) avant de
  continuer ?

## Étape 6 : run C2 à 6°, mesures, repli à 30°

**Décisions de Tom** :
- règle relative pour l'énergie des créatures tombées : arrêt seulement si C2 fait plus du double de B2 (en nombre
  au-delà de 5 cm, ou en maximum) ;
- diagnostic en lecture seule des créatures 868 et 760, après le rapport C2 et avant le nettoyage.

**Run complet à 6°** (38266975229) :
- durée : 53,5 / 20,6 / 55,8 min ; SHA-256 OK ; runs extraits dans `runs/butees_corps/S` ;
- champions à la gén. 200 : **+38,89 / +33,85 / +48,50 m** (B2 : 34,24 / 33,45 / 35,32), moyennes +29,3 / +25,9 /
  +40,1 m ;
- audits : 0 J créé hors muscles, aucune alerte ; os ≤ 0,24 %, queue ≤ 0,63 %.

**`pytest` avec les runs à 6°** (38274214543) : 156 passent. Les runs C2 se rejouent au bit près.

**`--tail --crossings`, 50 meilleures** (38274228073) :

| Graine | Critère de repli | Pied de l'autre côté | Jambe/queue (C1) | Os de queue, max | Oscillation |
|---|---|---|---|---|---|
| 0 | garder 6° | 0 % (C1 : 0 %) | 0,0 % (14,0 %) | 0,16 % | ≤ 0,3 % |
| 1 | garder 6° | 0,0 % (C1 : 84 %) | 0,2 % (72,0 %) | 0,68 % | ≤ 0,4 % |
| 2 | garder 6° | 0 % (C1 : 38 %) | 0,0 % (50,1 %) | 0,18 % | ≤ 0,2 % |

- Pénétration ≤ 0,001° pour les meilleures.
- Au hasard, graine 2, n°541 (tombée, rang 995) : queue jusqu'à 161° au-delà du cône, brièvement (au 95e percentile,
  l'écart reste à 6°).

**Créatures tombées, C2 (6°) contre B2** (38274241300 / 38274255041 / 38274268492) :

| Graine, gén. | Tombées B2 / C2 | > 5 cm B2 / C2 | Max B2 / C2 (cm) | Queue > 5 % B2 / C2 | Queue max B2 / C2 |
|---|---|---|---|---|---|
| 0, 0 | 392 / 360 | 5 / 3 | 85,1 / 65,8 | 6 / **82** | 12,2 / 26,1 % |
| 0, 200 | 61 / 120 | 0 / 0 | 3,8 / 2,3 | 0 / 8 | 3,0 / 17,1 % |
| 1, 0 | 408 / 384 | 3 / 6 | 61,3 / 64,1 | 1 / **81** | 6,3 / 24,2 % |
| 1, 200 | 121 / 75 | 7 / 0 | 424,5 / 3,9 | 9 / 3 | 9,8 / 9,5 % |
| 2, 0 | 383 / 353 | 6 / 5 | 645,3 / 46,3 | 6 / **77** | 11,4 / 24,7 % |
| 2, 200 | 51 / 83 | 0 / 0 | 0,0 / 0,0 | 0 / 5 | 2,7 / 22,4 % |

- **Énergie** : la règle relative ne se déclenche pas (au plus 6 contre 3, soit le double et non plus du double).
- **Queue** : nettement pire. Les 12 pires créatures de la gén. 0 (graine 0) ont été rejouées sous Windows (maxima
  identiques à ceux du runner) : **100 % des 4 318 sous-pas au-delà de 5 % ont la queue en butée de cône ET au
  sol.**
- C'est la troisième mesure qui tombe pour ce mécanisme, d'où le **repli direct à 30°** (règle de Tom).

**Repli** :
- `TAIL_CONE_DEG = 30.0` [CHOIX], avec la raison mesurée en commentaire ;
- tests rendus indépendants de l'angle, verts à 6° et à 30° ;
- pytest local : 153 passent ; les 3 échecs sont les rejeux Windows connus.

**Prochaine étape** :
- `pytest` sur le runner ;
- run `butees_corps_30` (200 générations) ;
- puis les mêmes mesures. S'il se déclenche aussi à 30° : arrêt.

**Runner** : `pytest` du repli, 156 passent (38278049033). Les runs à 6° se rejouent avec leur propre config.

**Outil `trace`** (commit `ee5de93`) : rejeu pas à pas audité. `pytest` 157 passent (38278546718).

**Créature n°541 (C2 à 6°, graine 2, gén. 200)**, rejouée au bit près (38278559147) :
- 0 J créé ;
- à t ≈ 8,78 s, en l'air (aucune prise, pas encore tombée : la chute arrive à 9,31 s), un point de queue **alterne
  d'un sous-pas à l'autre** entre le bord du cône et 3°, 10° puis 32° au-delà, sur 116 sous-pas.

C'est une oscillation numérique contre le cône, chez une créature tirée au hasard et pas chez les grimpeuses. Le
critère, qui porte sur les meilleures, ne la voyait pas. Elle est à remesurer à 30°.

**Run à 30° lancé** : 38278062446. Diagnostic B2 lancé en parallèle : `trace` de 868, 760 et 447.
