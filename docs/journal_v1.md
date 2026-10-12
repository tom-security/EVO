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

**Prochaine étape** : `mode=pytest` sur le runner (rejeu B2 au bit près), puis commit 2 (butées du corps).
