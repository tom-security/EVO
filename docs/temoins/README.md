# Témoins du duel (v2, GECKO-10)

Courbes des témoins du duel, recalculées sur le runner GitHub (ubuntu-24.04) : l'évolution (moteur D, corps libre),
l'évolution à corps figé (manche 1), le hasard pur et l'évolution à petit budget (témoin du LLM à 50 et 200 essais,
depuis le 15 octobre 2026). Chaque camp joue 5 fois (décision de Tom et Dorian).
Graphique : `courbes_temoins.html` (une figure par manche, moyenne et bande min–max, tableau de valeurs).

## Sources

| Camp | Runs | Entraînement (GitHub Actions) | Courbe (mode analyse) |
|---|---|---|---|
| Évolution, moteur D | `runs/0` à `runs/4` | 38411711297 (graines 0 à 2, v1.1), 38594982071 (3 et 4) | 38591827980, 38591833025, 38591838125, 38602057823, 38602068889 |
| Évolution à corps figé (`FROZEN_BODY = True`) | `runs/corps_fige/0` à `4` | 38591806655 (0 à 2), 38594977725 (3 et 4) | 38599424135, 38599428680, 38599433812, 38602053650, 38602062343 |
| Hasard pur | graines 100 à 104, manches 1 et 2 | — | 38595306742 |
| Évolution à petit budget (10 lézards, 200 évaluations) | graines 0 à 4, manches 1 (corps figé) et 2 | dans le même job | 38760481447 (runs dans l'artefact, `out/petit_budget/`) |

Runs sauvegardés sur `sauvegarde-runs` (`e6ca06d`), SHA-256 vérifiés, restauration vérifiée sur un clone neuf.

**Méthode** (`evo/courbes.py`) :
- évolution : chaque génome évalué par le run est réévalué par l'évaluateur batché, dans l'ordre du run (1 000 à la
  génération 0, puis les 500 enfants de chaque génération : 101 000 évaluations). Garde-fou : hauteur et énergie
  identiques au bit près aux valeurs stockées ; vérifié pour les 505 000 réévaluations des 5 + 5 runs ;
- hasard pur : 200 génomes par tirage, générateur de la génération 0 de l'évolution, manche 1 à corps figé ;
- évolution à petit budget : 10 lézards (5 survivants, 5 enfants), même moteur et mêmes mutations, 38 générations,
  audit d'énergie du champion à chaque génération, puis la même réévaluation vérifiée ;
- la courbe est la meilleure hauteur accrochée parmi les n premiers lézards testés.

Fichiers : `<nom>_resume.json` (lectures à 50 et 200, meilleur, paliers), `<nom>_paliers.csv` (chaque nouveau record).
Les évaluations complètes (`<nom>_evaluations.npz`, 22 Mo) sont dans les artefacts des runs ci-dessus.

## Lectures (meilleure hauteur accrochée, moyenne des 5 graines ou tirages ; min à max)

| Lézards testés | Évolution D | Évolution à corps figé | Hasard, manche 1 | Hasard, manche 2 |
|---|---|---|---|---|
| 1 | −5,31 (−6,84 à −3,16) | −3,82 (−6,93 à −0,49) | −2,81 (−6,93 à +0,11) | −2,86 (−6,64 à +0,13) |
| 10 | −0,05 (−2,50 à +1,06) | −0,79 (−3,52 à +0,77) | +0,73 (−0,33 à +1,96) | +0,75 (−0,40 à +2,10) |
| **50** | +1,89 (+0,56 à +3,13) | +1,74 (+0,77 à +2,57) | +1,89 (+0,76 à +3,06) | +2,33 (+1,10 à +3,49) |
| **200** | +3,43 (+3,13 à +3,71) | +3,34 (+2,33 à +5,18) | +2,72 (+1,86 à +3,56) | +2,86 (+2,19 à +3,49) |
| 1 000 | +4,10 (+3,44 à +5,29) | +4,88 (+4,00 à +5,52) | — | — |
| 10 000 | +10,76 (+9,17 à +13,24) | +10,83 (+8,43 à +12,80) | — | — |
| 101 000 | **+36,89** (+30,90 à +43,80) | **+37,19** (+35,98 à +38,96) | — | — |

Jusqu'à 1 000 évaluations, l'évolution n'a encore évalué que sa génération 0, qui est elle-même un tirage au hasard :
évolution et hasard s'y confondent, à la variabilité des graines près.

## Évolution à petit budget : le témoin du LLM à 50 et 200 essais

Correction d'équité décidée le 15 octobre 2026, avant toute partie (spec, « Témoin à 50 et 200 essais »).

| Essais | Évolution à petit budget, manche 1 | Hasard, manche 1 | Évolution à petit budget, manche 2 | Hasard, manche 2 |
|---|---|---|---|---|
| **50** | +0,59 (−0,01 à +1,02) | +1,89 (+0,76 à +3,06) | +1,37 (+0,80 à +2,13) | +2,33 (+1,10 à +3,49) |
| **200** | +0,72 (−0,01 à +1,09) | +2,72 (+1,86 à +3,56) | +2,99 (+0,97 à +6,10) | +2,86 (+2,19 à +3,49) |

Par graine (0 à 4), à 200 essais : manche 1 +1,04 / +0,78 / +1,09 / +0,69 / −0,01 m ; manche 2 +1,04 / +2,03 / +6,10 /
+0,97 / +4,82 m.

- En manche 1, l'évolution à petit budget fait moins bien que le hasard pur ; en manche 2, elle fait autant en moyenne,
  avec deux graines nettement au-dessus (+6,10 et +4,82 m) et trois en dessous.
- Constat sur les populations finales (génération 38) : 0 à 2 lézards tombés sur 10, la plupart accrochés près de 0 m ;
  dans 2 runs sur 10, le champion au score est un lézard économe (énergie 1,2 et 2,1) plus bas que le plus haut. Hypothèse,
  non mesurée plus avant : avec 10 lézards, la sélection au score (hauteur − 0,4 énergie − 0,1 masse musculaire) retombe
  dans l'« attracteur paresseux » de la phase 3b (rester accroché sans dépenser), là où le hasard explore 200 génomes
  indépendants.
- Énergie créée hors muscles (390 audits) : aucune alerte ; au plus 0,043 J (0,19 mm d'équivalent hauteur) et
  0,0097 J (0,04 mm), chez deux champions au score qui ne grimpent pas (−4,31 et −0,67 m) ; 0 J ailleurs. C'est la limite
  connue des créatures tombées du moteur D (chantier D : au plus 0,87 cm), 260 fois sous le seuil d'audit de 5 cm.
- Coût : 11 à 12 s de calcul par run de 200 évaluations (102 s pour le premier du job, compilation numba comprise).

## Coût de calcul (runner GitHub, Linux, 4 vCPU)

| Camp | Calcul noté par le programme | Durée des jobs |
|---|---|---|
| Évolution D, par graine | 28,7 / 14,2 / 47,9 / 20,5 / 33,2 min (moyenne 28,9 min ; 17,2 ms par évaluation) | 29,6 / 14,8 / 48,8 / 21,3 / 34,2 min |
| Évolution D, 5 graines | 2,41 h | 2,48 h |
| Corps figé, par graine | 49,0 / 23,9 / 14,9 / 34,9 / 45,9 min (moyenne 33,7 min ; 20,0 ms par évaluation) | 50,1 / 24,7 / 15,5 / 35,9 / 46,9 min |
| Corps figé, 5 graines | 2,81 h | 2,88 h |
| Hasard pur, un tirage de 200 | 6,4 à 6,7 s (43,4 s pour le premier du job, compilation numba comprise) | 3,1 min pour les 10 tirages (installation et garde-fou compris) |

- Calcul noté par le programme : somme des `eval_seconds` de `stats.csv` (évaluation et mutations de chaque génération)
  pour l'évolution, temps de l'évaluation pour le hasard ; durée des jobs : `jobs_github.tsv` (API GitHub).
- Le temps d'une graine varie du simple au triple pour la même quantité d'évaluations (101 000) : la cause n'a pas
  été mesurée.
