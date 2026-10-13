# Bilan de la v1

**La v1 d'EVO reproduit la vidéo de Code BH**
[« J'ai codé l'évolution de créatures qui grimpent »](https://www.youtube.com/watch?v=PiWgzThhF9M) : moteur physique
maison, lézards qui grimpent, sélection naturelle, rendu jungle, HUD et écrans d'analyse. Elle est finie et nettoyée,
et elle attend son gel. Ce document dit ce qui est fait, comment elle se compare à la vidéo, ce qui reste en écart,
et quelles décisions attendent l'utilisateur, avec des propositions qui ne sont pas appliquées.

**État au 13 octobre 2026** :

| Branche | Commit | Contenu |
|---|---|---|
| `main` | `d9317eb` | phases 1 à 6, A, B, C1, workflow |
| `claude/chantier-c2-butees-corps` | `30b1a61` | C2 |
| `claude/nettoyage-v1` | dernier commit de ce bilan | C2 + nettoyage + bilan |

Chacune contient la précédente. Rien n'est fusionné sur `main`. Le journal pas à pas est dans
`docs/journal_v1.md` ; l'état complet, les décisions et les règles dans `docs/PASSATION.md`.

## 1. Ce qui est fait

| Étape | Contenu | Document |
|---|---|---|
| Phase 1 | moteur : points, gravité, `Hold`, liens rigides (Gauss-Seidel), `Contract`, masses ; 9 bancs d'essai | PASSATION §9 |
| Phase 2 | sol, mur, créature (16 muscles, contrôleur à horloge, 4 poses) | PASSATION §9 |
| Phase 3 | audit d'énergie, évaluateur batché identique au bit près (1 000 × 10 s en ≈ 5 s), évolution, calibration | PASSATION §9 |
| Phase 4 | décor jungle low-poly (6 couches, parallaxes mesurées), lézard, replay | PASSATION §8 |
| Phase 5 | HUD, vue population et histogramme, mode analyse, comparaison de générations | PASSATION §8 |
| Phase 6 | export MP4, options, checklist du §11 de la spec | PASSATION §9 |
| Chantier A | cycle complet de la vue population, décor au-dessus de 23 m | PASSATION §9 |
| Chantier B | butées articulaires dans le moteur (B1 diagnostic, B2 implémentation) | `chantier_b_*.md` |
| Chantier C | butées du corps : pieds de leur côté de l'axe, queue dans un cône (C1 diagnostic, C2 implémentation) | `chantier_c_*.md` |
| Outillage | GitHub Actions (entraînement, reproductibilité, tests, analyse), mesures de queue et des créatures tombées, `trace`, `diag-projection`, `morpho`, `planche` | PASSATION §3.5, §4 |
| Nettoyage | sans changement de comportement : tags, versions épinglées, docs à jour, `README.md` public | journal |

**Tests** : 158, tous verts sur le runner GitHub, y compris le rejeu au bit près des runs B2 et C2.

## 2. Chiffres clés contre la vidéo

Génération 200, 1 000 créatures, graines 0 / 1 / 2. B2 = runs par défaut actuels ; C2 = `runs/butees_corps_30`,
référence proposée pour la v1.

| Repère (spec §9) | Vidéo | B2 | C2 |
|---|---|---|---|
| champion | 36 m | 34,2 / 33,4 / 35,3 m | **39,5 / 37,1 / 42,8 m** |
| majorité de la population | entre 30 et 35 m | 72 / 72 / 62 % entre 30 et 35 m | médianes 38,4 / 34,9 / 41,7 m (2 / 27 / 2 % entre 30 et 35 m) |
| créatures au sol | ≈ 30 | 61 / 121 / 51 | 119 / 90 / 84 |
| période d'horloge | 0,6 s | 1,54 / 0,88 / 0,60 s | 0,86 / 1,47 / 0,87 s |
| masse musculaire moyenne | 10,5 | 14,6 / 16,7 / 10,0 | 16,4 / 13,5 / 13,8 |
| énergie du champion | 32,5 | 11,3 / 12,3 / 8,8 | 16,4 / 13,3 / 15,6 |
| gén. 0 : au sol | ≈ 450 | 392 / 408 / 383 | 378 / 389 / 361 |
| gén. 0 : meilleure | ne grimpe pas | +2,2 / −0,3 / +3,0 m | +2,1 / −0,3 / +3,0 m |
| flemme (gén. 1 à 20) | muscle 13,2 → 7,3 ; période jusqu'à 4,5 s | muscle min 9,1 / 7,6 / 8,2 ; période max 3,8 / 3,5 / 4,8 s | 8,6 / 6,9 / 9,2 ; 3,4 / 3,7 / 4,2 s |
| chutes de période | gén. 80 à 85, puis 140 à 150 | sous 1,5 s dès les gén. 102 / 16 / 51 | dès les gén. 31 / 184 / 30 |
| forces du champion, graine 2 | deltoïde 22 %, grand dorsal 76 %, biceps 57 %, fléchisseurs de hanche ≈ 31 % | 0 / 40 / 23 / 0 % | 100 / 64 / 99 / 0 % |
| démarche diagonale | oui | une pose sur quatre (graine 2) | une pose sur quatre (graine 1), aucune (graines 0 et 2) |
| pieds de l'autre côté de l'axe | non (images 11, 12) | 0 / 84 / 38 % du temps | 0 / 0,1 / 0 % |
| queue | droite, 1,7 à 5,7° de l'axe | libre, jusqu'à 180° | dans un cône de 30°, 24 à 28° de l'axe (médiane) |

Ce qui est reproduit fidèlement :
- le moteur et ses 5 fonctions ;
- la sélection, avec la phase flemmarde puis la grimpe ;
- l'ordre de grandeur des hauteurs ;
- les écrans : décor, HUD, population, histogramme, analyse, comparaison.

Les écarts tiennent surtout à la calibration (§3).

## 3. Écarts restants (état après C2 ; liste complète : PASSATION §11)

**Calibration et évolution** :
- génération 0 trop bonne : la meilleure monte, contre « ne grimpe pas » dans la vidéo ;
- chute de période trop précoce ou trop tardive selon la graine ;
- trop de créatures au sol (84 à 119, contre ≈ 30) ;
- **hauteurs au-dessus de la vidéo avec C2** (médianes 35 à 42 m, contre une majorité entre 30 et 35 m) ;
- masse musculaire trop haute ;
- énergie du champion deux fois plus basse : c'est la définition de E ;
- forces réparties autrement ;
- démarche diagonale partielle.

**Morphologie** :
- le lézard est encore trapu sur certains os (graine 2 : demi-bassin à 1,37) ;
- queue physique courte (1,2 × la colonne) ;
- **queue dessinée courbée à 30°**, contre une queue droite dans la vidéo ;
- **résidu jambe–queue** de 6,8 et 7,5 % (graines 1 et 2) ;
- **bras croisés de la graine 0** : bras gauche et droit croisés 89 % du temps, mains devant la tête 91 % du temps.

**Rendu** :
- canopées de l'arbre latéral plates ;
- 4 couleurs [VU] lues autrement sur la vidéo ;
- point rouge d'une paume non reproduit ;
- **courbes au style vidéo du §7.3 non faites** : c'est la seule mise en forme de la spec qui manque ;
- cadrage pendant le carton.

**Limites du moteur** (§4 et chantier D) :
- énergie créée par les créatures couchées (déjà en B2) ;
- queue des créatures tombées étirée à l'impact ;
- sortie de cône d'un seul sous-pas en l'air ;
- erreur de longueur des os jusqu'à 1,97 % dans une posture coincée rare.

Les grimpeuses ne sont touchées par aucune de ces limites : 0 J créé hors muscles chez les champions et les meilleures
de 5 générations, pénétration des butées ≤ 0,03°.

**Coût** : avec les 14 butées du corps, l'évaluation coûte ×2,2 (26 s contre 12 s par génération sur le PC,
18 à 44 min par graine sur le runner).

## 4. Chantier D proposé : « projection propre » (préalable à la v2, rien n'est appliqué)

### 4.1 Le problème

La stabilisation retenue (`BETA = 0`, projection de position seule, ordre liens → butées → sol) a trois effets de bord,
qui ont la même cause : **la projection corrige les positions sans corriger les vitesses**.

1. **Énergie créée par les créatures couchées.** Ce problème existait en B2, et C2 l'a mesuré.
   - Mécanisme, sur les créatures 868, 760 et 447 rejouées pas à pas (`trace`) :
     - la créature est couchée, des points au sol, 2 à 3 butées articulaires actives, muscles en action ;
     - à chaque sous-pas, la gravité ajoute ≈ 1,2 J d'énergie cinétique, le mouvement enfonce les points dans le sol
       (−1,2 J d'énergie potentielle), et la projection les remonte (+0,8 à +1,1 J) ;
     - la vitesse vers le bas n'est jamais annulée, et l'énergie monte de ≈ 200 J/s.
   - Ampleur, sur toutes les créatures tombées des générations 0 et 200 :
     - B2 : jusqu'à 1 292 J (6,45 m d'équivalent hauteur), 3 à 7 créatures par génération au-delà de 5 cm ;
     - C2 à 30° : 68 cm au plus.
   - Effet sur la sélection : marginal. Les créatures en cause finissent couchées à une hauteur normale ; une seule
     sur 27 était au rang 499, juste sous la limite des survivantes.
2. **Queue étirée à l'impact (C2).** La queue en butée de cône et posée au sol est étirée par la projection.
   - C2 à 30° : jusqu'à 43,8 % (n°677) ; 0 à 19 créatures par génération au-delà de 5 % (B2 : 0 à 9).
3. **Sortie de cône d'un seul sous-pas (C2).** En l'air, quand plusieurs butées de queue agissent ensemble, la
   correction de position fait sortir un point du cône pendant un sous-pas.
   - Jusqu'à 144° au-delà (n°808 : 16 fois en 0,12 s) ; 0 J créé.

### 4.2 Le correctif mesuré : `vitesse_proj`

Reporter sur la vitesse toute correction de position de la projection : v += Δp / h, comme dans les schémas « position
based ». Mesuré en lecture seule par `diag-projection`, la variante étant substituée le temps de la commande. Moteur tel
quel identique au bit près dans les 6 cas (run 38360431755) :

| Cas | Moteur tel quel | `vitesse_proj` |
|---|---|---|
| B2 n°868 (couchée) | 1 292,5 J créés, queue 9,1 % | **9,6 J**, queue 0,3 % |
| B2 n°760 (couchée) | 825,2 J créés, queue 9,8 % | **12,9 J**, queue 0,9 % |
| C2 n°677 (impact) | 0 J, queue **43,8 %**, 10 sorties de cône | 0 J, queue **0,2 %**, 0 sortie |
| C2 n°808 (en l'air) | 0 J, **16 sorties de cône** (117°) | **17,7 J (10,4 cm)**, 0 sortie |
| C2 champion, graine 0 | +39,91 m, 0 J | +39,84 m, 0 J |
| C2 champion, graine 1 | +37,10 m, 0 J | +37,21 m, 0 J |

Les trois autres options mesurées sur les mêmes créatures couchées n'agissent presque pas (rejeu sous Windows, au bit
près pour la n°868) :
- annuler seulement la vitesse descendante des points remontés au sol : 1 289 J ;
- 60 passes de Gauss-Seidel : 1 158 J ;
- 120 passes : 1 075 J.

**Bilan du correctif** :
- il supprime l'essentiel des trois effets : énergie divisée par 100, queue étirée de moins de 1 %, aucune sortie de
  cône ;
- il ne change presque pas les grimpeuses : champions à ±0,1 m ;
- **mais il n'est pas neutre** :
  - il crée lui-même de l'énergie dans un cas (n°808 : 10,4 cm, au-delà du seuil d'audit) ;
  - il change la dynamique : la n°677 ne tombe plus et finit à +1,85 m au lieu de −8,99 m.

Il faudrait donc l'audit habituel sur des populations entières avant de le retenir.

### 4.3 Butée « mains de leur côté de l'axe »

Sur le modèle des pieds :
- 2 butées (NECK, PELVIS, L_HAND / R_HAND), u ∈ [m, 180° − m] ;
- même primitive, 2 triplets de plus (24 butées en tout).

Motivation mesurée (C2 à 30°, graine 0, 50 meilleures) :
- mains de l'autre côté de l'axe **91,4 % du temps**, à 98,8 % devant la tête, 0,83 m au-delà de l'axe (médiane) ;
- bras gauche et droit croisés 89,2 % du temps.

Les graines 1 et 2 ne sont pas concernées (0 à 0,2 %).

### 4.4 Déroulé proposé

Comme C2 :
1. drapeau `CLEAN_PROJECTION` (absent = False, pour que B2 et C2 se rejouent tels quels) et drapeau `HAND_LIMITS` ;
2. tests sur le modèle de `test_body_limits.py`, avec la non-régression de l'énergie sur les créatures couchées ;
3. réentraînement des 3 graines sur le runner ;
4. mesures `--fallen`, `--tail`, `--crossings` et `diag-projection` ;
5. rapport.

Préalable conseillé à la v2 : une créature couchée qui crée de l'énergie, ou une queue qui saute d'un sous-pas, peut
fausser une comparaison LLM contre évolution.

## 5. Décisions qui attendent l'utilisateur

1. **Le résidu jambe–queue** des graines 1 et 2 à 30° (6,8 et 7,5 % du temps ; B2 : 72 et 50 %) : collision ciblée
   tibia–queue, ou rien.
2. **Le jugement visuel de la queue à 30°**. Elle est tenue dans le cône et courbée de 13 à 16° (médiane), soit 24 à
   28° d'écart à l'axe, contre une queue droite à 1,7 à 5,7° dans la vidéo.
   - Planche : `docs/chantier_c_c2/queue_pieds_avant_apres.png` ; version avec l'image 11 :
     `out/chantierC/planches/queue_pieds_contre_image11.png` (hors git).
   - À 6°, la queue était droite, mais ce cône a déclenché le repli (§3 du rapport C2).
3. **Le chantier D** (§4) : à faire avant la v2, pendant, ou pas.
4. **Les écarts de calibration** (§3) : à reprendre pour la v1, ou à laisser en l'état pour la v2.
5. **Les courbes au style vidéo du §7.3**, seule mise en forme manquante de la spec.
6. **`docs/reference/`** : les 40 captures de la vidéo de Code BH sont versionnées dans le dépôt public depuis le
   début. Elles ne sortent jamais dans les artefacts du workflow, mais le dépôt les expose. Les retirer ne les
   effacerait pas de l'historique git.
7. **La sauvegarde des runs C2.** Les archives `runs_butees_corps_30_S.tar.gz` et `runs_butees_corps_S.tar.gz` ne
   sont que des artefacts GitHub, et elles **expirent le 11 novembre 2026**. Il existe une copie locale dans `runs/`
   sur le PC.
8. **Le coût ×2,2** des butées du corps, pour les entraînements de la v2.

## 6. Propositions pour le gel (aucune n'est appliquée)

**a) Fusion sur `main`**, en avance rapide : `main` (`d9317eb`) et la branche C2 sont des ancêtres de
`claude/nettoyage-v1` (vérifié avec `git merge-base --is-ancestor`).

```
git fetch origin
git switch main
git merge --ff-only origin/claude/nettoyage-v1
git push origin main
```

**b) Runs C2 comme runs par défaut**, comme après B. À faire sur le PC, dans `code/`, avec les runs extraits. Les runs
restent hors git.

```
Move-Item runs\0 runs\butees_articulaires\0      # idem pour 1 et 2 : B2 devient runs/butees_articulaires/S
Move-Item runs\butees_corps_30\0 runs\0          # idem pour 1 et 2 : C2 à 30° devient runs/S
```

À mettre à jour en même temps :
- dans `test_local_runs_replay_with_their_own_flag` : `runs/S` à (True, True), `runs/butees_articulaires/S` à
  (True, False), ainsi que le cas `butees_corps_30` ;
- dans le workflow, les modes `reproductibilite`, `pytest` et `analyse`, qui restaurent B2 dans `runs/S` depuis
  `sauvegarde-runs` ;
- `sauvegarde-runs` : y ajouter les archives C2 (`runs_S.tar.gz` renommées, avec leurs SHA-256 et un README mis à
  jour), sans supprimer celles de B2 ;
- les chemins cités dans PASSATION §3.3 et dans `chantier_c_c2.md`, sur le modèle de la note du §7 de B2.

**c) Tag `v1.0`** sur le commit fusionné :

```
git tag -a v1.0 -m "EVO v1 : reproduction de la vidéo de Code BH (phases 1 à 6, chantiers A, B, C)"
git push origin v1.0
```

L'ordre conseillé : b) puis a) puis c), pour que le tag porte un dépôt dont les runs par défaut sont ceux de C2.
