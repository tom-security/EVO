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
