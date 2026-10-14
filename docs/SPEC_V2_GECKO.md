# Gecko v2 : spécification du duel LLM contre évolution

Version du 14 octobre 2026, révisée le même jour (chaque camp joue 5 fois ; duel à coût égal). Ce document fait foi pour la v2 ; toute modification des règles passe par Tom.

## Objet

La v2 mesure combien d'essais aveugles vaut un essai réfléchi : un LLM conçoit des lézards grimpeurs avec un rapport détaillé après chaque essai, face à l'évolution (environ 100 000 lézards évalués sur 200 générations) et au hasard pur.

Le budget n'est pas une règle qui désigne un vainqueur, c'est une mesure. On compare des courbes de meilleure hauteur en fonction du nombre de lézards testés, et on lit le « taux de change » entre réflexion et hasard. La v2 sert de base à la vidéo phare de la chaîne « L'IA Va ».

## Les joueurs

Trois joueurs, sur le même moteur (moteur D, v1.1) et avec la même règle de victoire. Le hasard pur est l'arbitre : si le LLM ne le bat pas, sa réflexion ne sert à rien.

| Joueur | Ce qu'il fait | Budget | Ce qu'il apprend d'un essai |
| --- | --- | --- | --- |
| LLM | Conçoit un génome, lit le rapport, corrige | 50 essais annoncés par partie ; en manche 2, prolongés jusqu'à 200 pour 2 parties sur 5 | Le rapport d'essai complet |
| Évolution | 1000 lézards, les 500 meilleurs ont un enfant muté | 200 générations, environ 100 000 évaluations, 5 graines par manche | Le score seulement |
| Hasard pur | Tire des génomes aléatoires, garde le meilleur | 200 génomes par tirage (le budget maximal du LLM), 5 tirages par manche | Rien |

## Les deux manches

| Manche | Ce que le joueur règle | Corps | Référence évolution |
| --- | --- | --- | --- |
| 1. Le chorégraphe | Période, 4 poses, prises, 8 forces (une par muscle, appliquée aux deux côtés) | Imposé : longueurs de référence | Run d'évolution témoin à corps figé (5 graines) |
| 2. Le créateur | Tout le génome, longueurs des 7 os comprises | Libre, dans les bornes du génome | Les runs par défaut (moteur D, 5 graines) |

## Règles fixées à l'avance

Écrites avant la première partie, elles ne changent plus après avoir vu un résultat.

- **Budget annoncé** : 50 essais par manche, un seul génome par essai, aucun lot.
- **Forces symétriques** : dans les deux manches, le génome donne 8 forces, une par muscle, appliquées à l'identique à
  gauche et à droite, comme pour l'évolution et le hasard pur (décision de Tom du 14 octobre 2026).
- **Prolongation** : seulement en manche 2, pour 2 parties sur 5, désignées avant de jouer : le LLM continue jusqu'à
  200 essais pour savoir s'il plafonne. Le résultat à 50 reste celui qu'on annonce. En manche 1, chaque partie s'arrête
  à 50 essais.
- **Critère de victoire, la « hauteur accrochée »** : hauteur du centre du torse au dernier instant où au moins une patte tient le tronc, sur 10 s. Un saut final ne rapporte rien (cas de la créature n°677 : la hauteur à 10 s récompensait une créature en chute).
- **Départage** : l'énergie dépensée, la plus basse gagne.
- **Équité** : les champions de l'évolution sont recalculés avec la hauteur accrochée, par rejeu.
- **Répétitions** : chaque camp joue 5 fois par manche (décision de Tom et Dorian) : 5 parties pour le LLM, 5 graines
  pour l'évolution, 5 tirages pour le hasard pur. On montre la moyenne et l'écart, jamais la seule meilleure partie.
- **Pas d'optimisation automatique** : le LLM écrit chaque génome à la main. Il ne lance aucun script de recherche ou d'optimisation.
- **Transparence** : le carnet de bord complet est publié, échecs compris.

## Ce que sait le LLM

Le LLM joue en « ingénieur informé ».

| Il reçoit | Il ne reçoit pas |
| --- | --- |
| Le squelette, les 7 os et leurs longueurs de référence | Le code du projet |
| Les 16 muscles et l'action de chacun | Les runs d'évolution et leurs statistiques |
| Le contrôleur : horloge, 4 poses, prises, contrôle PD | Les génomes des champions |
| Les règles physiques en langage clair (gravité, prise seulement sur le tronc, chute dès qu'un point du corps touche le sol, butées) | La marche diagonale écrite à la main |
| Le format du génome et ses bornes, la règle de victoire | Les résultats des autres parties |

Mémoire : à chaque essai, le LLM revoit tout l'historique de la partie (génomes, rapports, carnet). Avant chaque essai, il écrit son hypothèse en une ou deux phrases dans le carnet de bord.

## Le rapport d'essai

Texte compact, quelques centaines de mots, toujours dans le même ordre :

1. **Résultat** : hauteur accrochée, hauteur à 10 s, énergie, masse musculaire.
2. **Trajectoire** : hauteur du torse toutes les 0,5 s.
3. **Chute** : instant, point du corps qui a touché le sol, ou « pas de chute ».
4. **Prises** : pour chaque patte et chaque pose, si la prise a tenu, échoué (hors du tronc) ou n'était pas demandée.
5. **Articulations** : plage parcourue par chacune des 8, et part du temps en butée.
6. **Corps** : part du temps où un pied ou une main est de l'autre côté de l'axe, croisements jambe–queue.

Aucune comparaison avec l'évolution ni avec les autres parties.

## Mesures et livrables

- Courbe par joueur : meilleure hauteur accrochée en fonction du nombre de lézards testés (échelle logarithmique, 1 à 100 000).
- Taux de change : nombre d'évaluations dont l'évolution a besoin pour égaler la meilleure hauteur du LLM après 50, puis 200 essais.
- Courbe de l'évolution : meilleure hauteur accrochée cumulée à chaque évaluation, recalculée sur les runs existants.
- Hasard pur : 5 tirages de 200 génomes aléatoires par manche, courbes lues à 50 et à 200 essais.
- Par partie du LLM : journal complet (génome, rapport, hypothèse), champion rejoué et exporté.

## Duel à coût égal

En plus du nombre de lézards testés, chaque camp est mesuré à ce qu'il coûte.

- **Coût du LLM** : les tokens consommés (entrée, sortie, cache), au tarif public de l'API du modèle.
- **Coût de l'évolution et du hasard** : le temps de calcul réellement consommé, au tarif public d'une machine
  équivalente au runner (Linux, 4 vCPU). Évolution : temps de chaque génération noté par le run ; hasard : temps de
  l'évaluation de ses génomes ; la durée des jobs est notée à côté.
- **Tarifs** : relevés et datés avant de jouer (source, date, prix unitaire), puis gardés pour tout le duel.
- **Arène** : elle enregistre les tokens consommés à chaque essai (entrée, sortie, cache), avec le modèle et sa version.
- **Lecture** : meilleure hauteur accrochée en fonction du coût, en plus des courbes en nombre de lézards testés.

## Mise en œuvre (ordre)

1. **Hauteur accrochée** : calculée identiquement dans le moteur scalaire et l'évaluateur en lot (test au bit près), sans changer le score d'évolution ni le rejeu des runs existants.
2. **Format JSON du génome** lisible (muscles et os nommés, angles en degrés anatomiques, bornes vérifiées) et commande qui affiche le schéma et les bornes.
3. **Commande `essai genome.json`** : simule, écrit le rapport d'essai et le fichier d'états.
4. **Export des états** (aussi `replay --export-etats` pour les champions de l'évolution).
5. Fiche du joueur (rédigée à part), témoins (évolution à corps figé, hasard pur), puis les parties.

Le joueur LLM est d'abord Claude, dans une session Claude Code séparée qui n'a accès qu'à la fiche du joueur, à la commande `essai` et à son journal.

## Export des états pour le rendu

Chaque lézard montré dans la vidéo est rendu à partir d'un fichier d'états : ce qu'on voit est exactement ce qui a été simulé.

- **Quand** : les essais du LLM à la fin de chaque essai ; les champions de l'évolution et du hasard par rejeu sur le runner.
- **En-tête** : identifiant du run et de l'essai, hash du commit, graine, 60 images/s, unités, convention d'axes (origine, axe vertical), liste des os et longueurs.
- **Par image** : positions des 27 points, état des 4 prises, activation des 16 muscles.
- **Empreinte** : hash des états calculé à la simulation ; un rejeu ultérieur qui donne une autre empreinte a divergé.
- **Import Blender** : un repère animé en position par point, chaque os suit par contraintes ; axes convertis vers Z vertical.
- **Patte levée** : léger relief dérivé des prises, lissé à l'entrée et à la sortie.
- **Pattes et queue** : en vue de dessus, une jambe peut croiser la queue (jusqu'à 23,4 % du temps, graine 2, pied levé dans 83,8 % des cas). C'est de la profondeur : au rendu, les pattes passent au-dessus de la queue.

**Règle d'intégrité** : les plans du duel viennent uniquement de ces fichiers. Aucun outil génératif ne retouche le mouvement d'un lézard du duel.
