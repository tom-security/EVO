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
- Après le 2e redémarrage : les deux composants se déclarent activés, l'hyperviseur tourne, mais WSL2 ne démarre
  toujours pas. Cause trouvée : `vmcompute.exe` (service de calcul Hyper-V, fourni par la « Plateforme d'ordinateur
  virtuel ») est absent ; le composant était marqué activé sans être installé. Tom choisit de réparer WSL avant de
  passer à l'option C.
- Réparation : `dism /disable-feature VirtualMachinePlatform` (désactivé aussitôt, preuve qu'il n'était pas installé),
  puis `dism /enable-feature VirtualMachinePlatform /all`, qui installe cette fois réellement le composant (progression
  jusqu'à 100 %) : **3e redémarrage nécessaire**.
- Après le 3e redémarrage : **échec**. Les deux composants restent « activés » pour DISM, l'hyperviseur tourne
  (la virtualisation du processeur est donc active dans le BIOS), mais `vmcompute.exe` est toujours absent et WSL
  répond que ni WSL1 ni WSL2 ne peuvent démarrer. Les composants sont enregistrés sans que leurs fichiers soient
  installés : un défaut de maintenance de Windows (build 26300), hors de portée du projet. Aucun rejeu n'a pu être
  fait sous WSL.
- **Décision de Tom** : il répare Windows lui-même, puis le test WSL sera refait. Rien n'est codé pour la partie 2 en
  attendant.

**Pour reprendre** : vérifier `Test-Path C:\Windows\System32\vmcompute.exe` et `wsl --status` ; si WSL2 démarre,
`wsl --install -d Ubuntu-24.04`, Python 3.11 et les versions épinglées, puis les 18 créatures de `reproductibilite`
et les gén. 0, 100 et 200 des runs D (3 graines) contre les hauteurs du runner.

## Étape 4 : GECKO-9, outils du duel (option C), en autonomie

**Décision de Tom** : option C ; chaque rapport et chaque `resultat.json` notent la plateforme et l'écart avec le runner
quand il est connu ; job de vérification d'une partie sur le runner prévu dès maintenant ; plateforme configurable
(bascule vers WSL sans rien réécrire). Branche `claude/gecko-9-outils-duel`.

| Point | Commit | Contenu | `pytest` runner | `reproductibilite` |
|---|---|---|---|---|
| 1 | `4521bbf` | hauteur accrochée, scalaire = batchée au bit près | 191 passent (38546515611) | 18/18 identiques (38546520230) |
| 2 | `123d02a` | génome JSON, commande `genome` | 203 passent (38547611459) | 18/18 (38547615394) |
| 3 | `b5e77d3` | `essai`, rapport, partie, carnet, budget, plateforme, `verifier-partie` | 212 passent (38547706556) | 18/18 (38547709809) |
| 4 | `f26b124`, `4b6fdd4` | `replay --export-etats`, mode `verification` du workflow, partie de démonstration, parties gardées octet pour octet | 214 passent (38547887904) | 18/18 (38547892172) |

| fin | `045ea7e` | écart au millimètre dans le rapport ; PASSATION, README | 214 passent (38548886054) | 18/18 (38548889932) |

pytest local (Windows) : 211 passent, plus les 3 rejeux Windows connus.

**Choix d'exécution** :
- `config.DUEL_PLATEFORME_OFFICIELLE = "runner"` [CHOIX] ; budgets 50 / 200 et pas de 0,5 s de la trajectoire dans
  `config.py` ; un essai joué ailleurs est noté non officiel, avec la ligne « Écart avec la plateforme officielle » ;
- le génome d'un essai est copié tel quel (octets du fichier) : son SHA-256 est contrôlé à la vérification ; d'où
  `duel/** -text` dans `.gitattributes`, sans quoi git change les fins de ligne et la vérification refuse l'essai
  (trouvé avant le premier envoi) ;
- un génome invalide ne consomme pas d'essai ; une hypothèse est exigée dans une partie, écrite au carnet avant la
  simulation ;
- les fichiers d'états des parties restent hors git (≈ 0,8 Mo chacun) ; les états officiels viennent de la
  vérification.

**Partie de démonstration** `duel/demo_outils` (4 essais joués sur le PC, ≈ 2 s chacun), vérifiée sur le runner (runs
38547897355 puis 38548882028, mêmes chiffres ; le second est intégré dans la partie avec `--integrer`) :

| Essai | Génome | Hauteur accrochée PC | Runner | Écart | États |
|---|---|---|---|---|---|
| 1 | exemple du format | +8,603 m | +8,603 m | 6·10⁻¹⁰ m | différents |
| 2 | horloge 0,9 s, poussée plus forte | +8,127 m | +8,118 m | +9,5 mm | différents |
| 3 | aucune prise (jamais accrochée, chute à 1,13 s) | −8,780 m | −8,761 m | −18,9 mm | différents |
| 4 | pose 4 sans prise (dernière prise à 9,50 s ; à 10 s : −1,71 m) | −0,373 m | −0,373 m | +0,09 mm | différents |

**Champions D exportés sur le runner** (`replay --export-etats`, run 38547901338) : rejeux identiques ; hauteur accrochée
= hauteur à 10 s pour les trois (+30,897 / +40,878 / +43,627 m) : ils tiennent le tronc jusqu'au bout, la règle ne
change pas leur hauteur. Empreintes : `16fd76e9…`, `a8fa12da…`, `431461d3…`.

**Fin de GECKO-9** : les 4 points sont faits, aucun rejeu n'a divergé. Rien n'est fusionné sur `main` ; arrêt pour
validation. Suite (spec, étape 5) : fiche du joueur, témoins (évolution à corps figé, hasard pur), parties ; GECKO-11 :
la session du joueur ne doit pas pouvoir lire le code.

## Étape 5 : GECKO-9 validé ; décisions de Tom

1. `main` avancée sur `claude/gecko-9-outils-duel` (`8f5bfb9`).
2. Partie de démonstration gardée, déplacée de `duel/demo_outils` vers `duel/demonstration/demo_outils` (sous `duel/`,
   le mode `verification` du workflow l'accepte toujours) ; les étapes précédentes de ce journal citent l'ancien chemin.
3. L'exemple `genome --exemple` grimpe (+8,6 m) : il ne doit jamais être montré au joueur LLM. Nouvelle option
   `genome --exemple-neutre` (articulations au repos, toutes les prises relâchées, forces égales, horloge de 1 s, corps
   de référence) : valide, ne s'accroche jamais et tombe (test) ; le schéma renvoie vers lui. Il servira pour la fiche
   du joueur.
4. **Exigences de GECKO-11** (rien à coder maintenant) :
   - la session du joueur LLM ne doit pouvoir lire ni le code du projet, ni la partie de démonstration
     (`duel/demonstration/`), ni le dossier `demo_dorian/`, ni aucun génome issu de l'évolution (runs, champions,
     fichiers d'états de l'évolution) ;
   - l'arène doit accepter n'importe quel modèle d'IA, pas seulement Claude, pour servir de banc de test à chaque
     nouveau modèle.

**Changement de règle (Tom et Dorian, en cours de GECKO-10, avant toute partie)** : chaque camp joue 5 fois.
- évolution témoin à corps figé : 5 graines (0 à 2 déjà lancées, 3 et 4 ajoutées sans relancer les autres) ;
- évolution normale (moteur D) : graines 3 et 4 entraînées avec le moteur D actuel (config identique à celle des runs 0
  à 2, hors nouvelles clés de la v2 ; `AUDIT_EVERY = 10` comme eux), sauvegardées sur `sauvegarde-runs` ;
- hasard pur : 5 tirages de 200 génomes par manche (graines 100 à 104), courbes lues à 50 et à 200 essais ;
- coût : temps de calcul réellement consommé par chaque camp, noté pour le duel à coût égal ;
- spec mise à jour : 5 parties par manche pour le LLM, 5 tirages, 5 graines ; prolongation à 200 seulement en manche 2,
  pour 2 parties sur 5 (désignées avant de jouer) ; section « Duel à coût égal » (tokens au tarif public de l'API,
  temps de calcul au tarif public d'une machine équivalente au runner, tarifs relevés et datés avant de jouer) ;
- **exigence de plus pour GECKO-11** : l'arène enregistre les tokens consommés à chaque essai (entrée, sortie, cache),
  avec le modèle et sa version. À régler aussi dans l'arène : le budget de chaque partie (50 en manche 1 ; 50 ou 200 en
  manche 2) ; la commande `essai` borne aujourd'hui toutes les parties à 200.

Puis GECKO-10 en autonomie, sur `claude/gecko-10-temoins` : évolution témoin à corps figé (manche 1), courbes de
l'évolution en hauteur accrochée, hasard pur (2 manches), sauvegarde des runs témoins. Arrêt si un test échoue, si un
rejeu n'est plus identique au bit près, si de l'énergie est créée hors muscles ou si un champion témoin passe sous
20 m ; sinon arrêt et rapport à la fin, avec les courbes des trois joueurs par manche.
