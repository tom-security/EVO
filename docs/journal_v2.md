# Journal de la v2 : Gecko, duel LLM contre évolution

Suite de `docs/journal_v1.md`. Spécification : `docs/SPEC_V2_GECKO.md`. Chaque étape d'une mission en autonomie est
notée ici et commitée, pour reprendre si la session s'interrompt.

## Étape 0 : reprise et environnement (14 octobre 2026)

**Constat** : le PC n'avait plus le dépôt, ni Python, ni `gh`.

**Fait** (PASSATION §3.1, « Réinstallation du 14 octobre 2026 ») :
- dépôt recloné dans `Bureau\Gecko` ;
- Python 3.11.9 et `gh` 2.102.0 installés par winget ; `gh` connecté par Tom (droits d'administration sur le dépôt) ;
- venv : numpy 2.4.6, numba 0.67.0 (llvmlite 0.49.0), pygame 2.6.1 (SDL 2.28.4), pytest 9.1.1, imageio-ffmpeg ;
- runs restaurés depuis `sauvegarde-runs` (`28d7440`) : 12 SHA-256 conformes, 2 469 fichiers ;
- **pytest local** : 182 passent, 3 échouent (les 3 rejeux Windows connus de
  `test_local_runs_replay_with_their_own_flag`) ; 242 s.

`docs/SPEC_V2_GECKO.md` était déjà sur `main` (commit `8e2b088`, ajouté par Tom depuis GitHub), identique au
fichier fourni : rien à commiter.

## Étape 1 : GECKO-13, EVO devient Gecko

**Fait** :
- `gh repo rename Gecko -R tom-security/EVO` : le dépôt est `tom-security/Gecko` ; remote local mis à jour
  (`https://github.com/tom-security/Gecko.git`) ;
- branche `claude/gecko-13-renommage`, partie de `main` (`8e2b088`) : README, CLAUDE.md, PASSATION (note en tête,
  environnement, commandes `gh`, historique, branches), BILAN (note en tête), commentaire du workflow ;
- non renommés : le dossier local, le paquet `evo/` et ses modules (les `config.json` des runs en dépendent),
  l'historique et les rapports passés.

**Vérifications** (commit `d29b267`, dépôt déjà renommé) :
- push vers `tom-security/Gecko` : OK (git authentifié par `gh auth login`) ;
- `pytest` sur le runner : **185 passent**, 0 échec, avec les runs de référence restaurés (run 38541628281) ;
- `reproductibilite` : les 9 champions de la gén. 200 (D, C2 à 30°, B2) et les 9 créatures n°0 de la gén. 0
  rejoués à l'identique (run 38541631664, 1 min 47 s).

**Reste à décider par Tom** : avance rapide de `main` sur `claude/gecko-13-renommage`.

## Étape 2 : GECKO-9, outils du duel : plan (rien n'est codé)

Mesure de préparation, en lecture seule : les génomes des runs D (entraînés sur le runner) réévalués sous Windows
par l'évaluateur batché (`out/mesures_v2/ecart_plateforme.py`, hors git), contre les hauteurs stockées. Chiffres dans le
plan présenté à Tom.
