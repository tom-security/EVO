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

**Décision de Tom** : avance rapide de `main` sur `claude/gecko-13-renommage` (faite : `main` = `6d6f040`).

## Étape 2 : GECKO-9, outils du duel : plan

**Mesure de préparation** (lecture seule) : génomes des runs D (entraînés sur le runner) réévalués sous Windows par
l'évaluateur batché (`out/mesures_v2/ecart_plateforme.py`, hors git), contre les hauteurs stockées. Gén. 200, graines
0 / 1 / 2 :

| | Graine 0 | Graine 1 | Graine 2 |
|---|---|---|---|
| hauteurs identiques au bit près | 0 / 1 000 | 0 / 1 000 | 0 / 1 000 |
| écart médian | 2,5 cm | 19,0 cm | 10,9 cm |
| écart p95 | 1,27 m | 5,14 m | 1,52 m |
| au-delà de 1 m | 64 | 164 | 68 |
| statut « tombée » inversé | 15 | 17 | 8 |
| 50 meilleures : écart médian ; max | 1,5 cm ; 0,55 m | 16,2 cm ; 1,86 m | 7,3 cm ; 0,49 m |
| plus haute : Linux ; Windows | 30,897 ; 30,756 m | 40,878 ; 40,708 m | 43,797 ; 43,803 m |

Graine 1 : la meilleure sous Windows n'est pas la même ; rejouée sous Linux, elle fait 40,159 m (−72 cm). Gén. 0 : écart
médian 0,01 à 0,03 cm, p95 11 à 13 cm. Évaluation d'une population de 1 000 sous Windows : 7 à 9 s ; une créature au
moteur scalaire : 0,6 s.

**Décisions de Tom** (plan validé) :
1. plateforme : tester d'abord WSL (Ubuntu 24.04, versions épinglées). Critère : les 18 créatures de
   `reproductibilite` à l'identique, puis les générations 0, 100 et 200 des runs D (3 graines) identiques au bit près
   aux hauteurs du runner. Si oui, les essais officiels se jouent sous WSL ; sinon option C (jeu sur le PC, chiffres
   officiels refaits sur le runner, écart PC/runner noté dans chaque rapport). Résultat rapporté avant de coder ;
2. forces : 8 valeurs appliquées aux deux côtés, comme l'évolution ; `docs/SPEC_V2_GECKO.md` mis à jour sur ce seul
   point ;
3. génome jamais accroché : hauteur accrochée = hauteur à 10 s, avec la mention « jamais accrochée » ; départage :
   énergie sur les 10 s ;
4. format du génome : validé tel que l'exemple du plan ;
5. ensuite, partie 2 en autonomie sur `claude/gecko-9-outils-duel`, `pytest` et `reproductibilite` sur le runner à
   chaque étape ; arrêt à la fin des 4 points ou si un rejeu n'est plus identique au bit près.

**Exigence pour GECKO-11** (pour plus tard, rien n'est fait maintenant) : la session du joueur LLM ne doit pas pouvoir
lire le code du projet.

## Étape 3 : test de WSL

- `wsl --install -d Ubuntu-24.04 --no-launch` (élevé) : code 0, mais WSL2 ne démarre pas, « la virtualisation n'est
  pas activée » ;
- `wsl --install --no-distribution` (élevé) active la « Plateforme d'ordinateur virtuel » : **redémarrage du PC
  nécessaire**. Le test reprend après le redémarrage.
- Après le 1er redémarrage : « Plateforme d'ordinateur virtuel » activée, hyperviseur présent, WSL 3.0.3.0 installé,
  mais le composant « Sous-système Windows pour Linux » restait désactivé (`wsl --install` le disait activé sans le
  faire). Activé avec `dism /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart`
  (élevé) : **second redémarrage nécessaire**.
