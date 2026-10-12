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
