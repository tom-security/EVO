# Passation du projet EVO : tout, de A à Z

Ce document est écrit pour une IA qui rejoint le projet en cours de route. Il rassemble ce que contiennent le
dépôt, les échanges avec l'utilisateur et les rapports de chaque phase : le but, les règles de travail, le code,
chaque décision prise avec sa raison, les chiffres mesurés, les écarts connus et la suite déjà validée.

État au 14 octobre 2026 : **la v1.1 est sur `main`**, avec le tag `v1.1`.
- Phases 1 à 6, chantiers A, B, C (C1 diagnostic, C2 butées du corps) et D (projection propre), nettoyage et bilan :
  tout est sur `main`. Le tag `v1.0` marque la v1 avant le chantier D.
- Les runs par défaut sont ceux du chantier D (`runs/S`) : report dissipatif de la projection, butées des mains, cône
  de queue de 15°.
- Chantier D : `docs/chantier_d_diagnostic.md` et `docs/chantier_d.md`, validés par l'utilisateur.

**Cap** : EVO devient le socle d'une vidéo YouTube, la **v2 : duel LLM contre évolution**. La v1.1 (la reproduction de
la vidéo de Code BH, avec une physique sans création d'énergie hors muscles) en est le point de départ.

Les autres documents du dépôt restent la référence pour le détail :
- `docs/CODEBH_GRIMPE_SPEC.md` : la spec, **à lire avant toute modification** (règle du `CLAUDE.md`) ;
- `docs/chantier_b_diagnostic.md` (B1), `docs/chantier_b_b2.md` (B2), `docs/chantier_c_diagnostic.md` (C1),
  `docs/chantier_c_c2.md` (C2) ;
- `docs/BILAN_V1.md` : le bilan de la v1, les écarts restants, les décisions en attente, le chantier D proposé ;
- `docs/journal_v1.md` : le journal pas à pas de C2, du nettoyage et du gel (runs GitHub, chiffres, décisions) ;
- `config.py` : chaque paramètre, avec son tag et, souvent, le tableau de mesures qui l'a fixé.

---

## Sommaire

0. L'essentiel en une page
1. Le projet et ses sources
2. Règles de travail (à respecter à la lettre)
3. Environnement, dépôt, branches, fichiers hors git
4. Architecture du code
5. Le moteur physique
6. La créature
7. L'évolution
8. Le rendu et les écrans
9. Historique complet, phase par phase
10. Décisions de l'utilisateur, à ne pas remettre en cause
11. Écarts connus avec la vidéo
12. Suite : la phase C2, déjà validée
13. Pièges techniques et leçons apprises
14. Tests
15. Glossaire et conventions d'angle
16. Images de référence

---

## 0. L'essentiel en une page

- **But :** reproduire la vidéo YouTube de Code BH « J'ai codé l'évolution de créatures qui grimpent » (17:58,
  2025) : un moteur physique 2D maison, des lézards qui grimpent un tronc, un algorithme évolutif (1000 créatures,
  10 s, les 500 meilleures ont chacune un enfant muté), puis le rendu jungle low-poly, le HUD et les écrans
  d'analyse de la vidéo.
- **Langue :** tout est en français (code, commentaires, commits, rapports, échanges).
- **Méthode :** phase par phase. Pour chaque étape, l'utilisateur envoie un prompt détaillé. On propose un plan,
  il le valide ou l'ajuste, on exécute, on rapporte avec des chiffres, **et on s'arrête** jusqu'à sa validation.
- **Pile :** Python 3.11, numpy 2.4.6, numba 0.67.0, pygame 2.6.1 (épinglés), pytest ; ffmpeg pour les MP4. Tout passe
  par `python main.py <commande>`.
- **Paramètres :** tout ce qui est [CHOIX] ou [DÉDUIT] va dans `config.py`, avec son tag et sa source.
- **Où tourne quoi :**
  - le PC de l'utilisateur (Windows, 2 cœurs) sert au code, aux tests et aux lectures de npz ;
  - **GitHub Actions** (`.github/workflows/train.yml`, runner ubuntu-24.04) sert aux entraînements, aux rejeux et aux
    écrans (§3.5) ;
  - **un run ne se rejoue au bit près que sur le runner Linux** : sous Windows, la bibliothèque mathématique diffère.
- **Runs** (hors git, tous sauvegardés sur la branche `sauvegarde-runs`, §3.3) :
  - `runs/<graine>` (graines 0, 1, 2) : **runs par défaut depuis la v1.1**, chantier D (butées articulaires et du
    corps, mains, cône de queue de 15°, report dissipatif de la projection) ;
  - `runs/butees_corps_30/<graine>` : C2 à 30°, les runs par défaut de la v1.0 ;
  - `runs/butees_articulaires/<graine>` : B2 (butées articulaires seules) ;
  - `runs/butees_corps/<graine>` : C2 avec un cône de 6° (rapport C2) ;
  - graine 2 par défaut pour les écrans.
- **Branches :**
  - `main` : la v1.1, tag `v1.1` (tag `v1.0` : la v1 avant le chantier D) ;
  - `claude/chantier-c2-butees-corps`, `claude/nettoyage-v1`, `claude/chantier-d-diagnostic` et `claude/chantier-d` :
    leurs commits sont dans `main` ;
  - `sauvegarde-runs` : archives des runs de référence (D, C2 à 30°, C2 à 6°, B2).
- **Prochaine étape :** la v2 (`docs/BILAN_V1.md`).
- **Tests :** 185 (`pytest -q tests/`). Sur le runner, tous passent. Sous Windows, les 3 tests qui rejouent les runs
  locaux échouent, et c'est attendu (§3.5).

---

## 1. Le projet et ses sources

### 1.1 La vidéo et la spec

`docs/CODEBH_GRIMPE_SPEC.md` décrit la vidéo de façon exhaustive, à partir de la transcription, de ≈ 70 images
analysées et de couleurs mesurées pixel par pixel. Chaque information y porte un tag :
- **[VU]** : dit ou montré dans la vidéo, à reproduire tel quel ;
- **[DÉDUIT]** : pas montré mais cohérent avec ce qui l'est, point de départ raisonnable ;
- **[CHOIX]** : choix d'implémentation, adaptable mais à signaler.

Code BH ne montre ni son code ni ses constantes. Tout ce qui n'est pas [VU] doit donc être exposé dans `config.py`
et calibré contre les résultats de référence du §9 de la spec.

Sections de la spec :
- §0 vue d'ensemble ;
- §1 moteur physique ;
- §2 créature ;
- §3 sélection naturelle ;
- §4 performance ;
- §5 direction artistique (palette, typographie, lézard, surcouche anatomique, décor) ;
- §6 HUD ;
- §7 écrans d'analyse ;
- §8 CLI ;
- §9 résultats de référence ;
- §10 plan en 6 phases ;
- §11 checklist finale.

Points structurants de la spec :
- **Vue :** de face sur un tronc vertical, lézard vu de dessus (comme un gecko sur un mur), gravité vers le bas de
  l'écran. **La simulation est 2D dans le plan du mur**, sans profondeur.
- **Moteur maison :** points, gravité, `Hold()` (fixer une patte au mur), liens rigides par correction de vitesse
  itérée (Gauss-Seidel), contraction d'articulation par couples de forces de somme nulle, masse = somme des
  demi-longueurs d'os.
- **Créature à topologie imposée :** 14 points, 13 os, plus une tête et une queue. 16 muscles nommés (8 par côté,
  deux sens par articulation). Contrôleur à horloge et K poses ; chaque pose donne les angles cibles et, pour
  chaque patte, tenir ou lâcher.
- **Fitness :** hauteur finale − pénalité d'énergie − pénalité de masse musculaire.
- **§9, la trajectoire à retrouver qualitativement :**
  - génération 0 : ≈ 450 créatures au sol, la meilleure ne grimpe pas ;
  - générations 1 à 10 : « piège de la flemme », la masse musculaire tombe de 13,2 à 7,3 et la période de
    l'horloge monte de 2,9 à 4,5 s ;
  - génération 12 : première grimpe ;
  - générations 80 à 85, puis 140 à 150 : chutes brutales de la période ;
  - génération 200 : champion à 36 m (période 0,6 s, énergie 32,5, muscle 13,5), majorité entre 30 et 35 m,
    ≈ 30 créatures au sol ;
  - forces du champion en % du maximum : deltoïde 22 %, grand dorsal 76 %, biceps 57 %, fléchisseur de
    hanche ≈ 31 % ; démarche diagonale.

### 1.2 Les images de référence

`docs/reference/` contient 40 captures de la vidéo en 1280 × 720. Le nom donne le numéro, le sujet et l'instant :
`21_schema_contraction_newton_t4m32s.png` correspond à « t = 4:32 » dans la spec. La liste complète est au §16.
Toutes les comparaisons visuelles du projet (palette, positions du HUD en pixels, géométrie de l'histogramme,
parallaxe…) ont été faites contre ces images.

### 1.3 `CLAUDE.md` (règles du dépôt)

```
Lis docs/CODEBH_GRIMPE_SPEC.md avant toute modification.
Les images de référence sont dans docs/reference/ : chaque nom donne le numéro, le sujet et l'instant
de la vidéo (ex. 21_schema_contraction_newton_t4m32s.png = « t = 4:32 » dans la spec).
Avance phase par phase (section 10), et ne passe à la phase suivante qu'après validation.
Tout ce qui est marqué [CHOIX] ou [DÉDUIT] va dans config.py.
```

Une ancienne version renvoyait à une « section 12 » qui n'existe pas (la spec s'arrête à la section 11). Elle a été
remplacée en phase 1 par la règle de nommage des images.

---

## 2. Règles de travail (à respecter à la lettre)

### 2.1 Le cycle de travail avec l'utilisateur

1. L'utilisateur envoie un prompt détaillé pour une phase ou un chantier, avec le contexte, les étapes, les
   critères, les livrables et le point d'arrêt.
2. On lit la spec et le code concerné, on mesure si besoin (en lecture seule), puis on écrit un **plan**.
3. L'utilisateur valide le plan, souvent avec des ajustements. Il les écrit parfois dans le **refus** de l'outil de
   validation du plan : un « refus » contient alors ses instructions, ce n'est pas un rejet du travail.
4. On exécute exactement ce qui a été validé.
5. On rapporte en français, avec des tableaux de chiffres, les écarts par rapport à la vidéo et au plan, et les
   décisions à prendre.
6. **On s'arrête.** On ne passe jamais à l'étape suivante sans validation explicite, même si elle paraît évidente.

### 2.2 Ce que l'utilisateur attend, et ce qui l'agace

- **Des chiffres, pas des impressions.** Chaque affirmation est mesurée (au pixel, au joule, au pourcentage), avec
  les valeurs de référence à côté.
- **Mesurer avant de conclure.** Exemple de B2 : avant de parler de régression du temps de rendu, rechronométrer
  l'ancien champion dans les mêmes conditions (c'était la machine).
- **Ne pas enquêter sur ce qui est déjà expliqué.** Exemple : le décalage de l'histogramme confirmait la baisse
  déjà connue des créatures au sol ; pas besoin d'une enquête séparée.
- **Trancher entre hypothèses avec un test** quand deux explications sont possibles (exemple : miniatures
  repliées = effet du run ou défaut de rendu ?).
- **Signaler chaque écart** avec la vidéo ou avec la consigne, même quand on a suivi l'image plutôt que le texte :
  voile du carton, grille 50 × 20, parallaxes mesurées…
- **Ne rien appliquer sans accord** quand plusieurs options raisonnables existent : les présenter avec les chiffres
  et attendre, en posant la question explicitement.
- **Budgets d'essais :** pour une calibration, 3 grilles maximum par étape. Sans convergence, s'arrêter et
  présenter les chiffres.
- **Essais en `--set`**, avec `config.py` intact pendant les explorations ; on ne fige une valeur qu'après
  validation.
- **Ne pas toucher à ce qui est validé :** écrans, physique, squelette, fitness, g, S_MAX, TORQUE_SCALE, KP/KD,
  sauf demande explicite.
- **Garder les écarts connus en liste** plutôt que de les corriger au passage (voir §11).
- **Pas d'écran de fin « teaser » volcan :** il reproduirait l'identité d'un vrai créateur. Exclu volontairement.

### 2.3 Git

- Commits en français, descriptifs, qui finissent par le pied `Co-Authored-By: Claude Opus 5.5
  <noreply@anthropic.com>`. Sur le PC de l'utilisateur, git n'a pas d'identité configurée : l'auteur des commits est
  passé commande par commande (`git -c user.name=Claude -c user.email=noreply@anthropic.com commit …`), sans toucher
  à la configuration globale.
- Aucun identifiant de modèle dans le code ou les docs (le pied de commit mis à part).
- Push avec `git push -u origin <branche>` ; **jamais `--force`**, jamais de réécriture d'historique, aucune
  suppression de branche ou de run sans accord. Git Credential Manager garde les identifiants une fois que
  l'utilisateur s'est connecté dans son propre terminal.
- **Pas de pull request** sauf demande explicite.
- Branche de référence : `main`. L'utilisateur demande une **nouvelle branche par chantier** ; une fois validé, le
  chantier est ramené par avance rapide sur `main`, sur sa demande. Jusqu'au 12 octobre 2026, la branche de
  référence s'appelait `claude/modest-ritchie-mkwjnd` : les rapports plus anciens la citent encore. Rien n'est
  fusionné sur `main` sans décision de l'utilisateur.
- **Journal** : pendant une mission en autonomie, chaque étape est notée dans `docs/journal_v1.md` (fait, chiffres,
  runs GitHub, prochaine étape) et commitée, pour pouvoir reprendre si la session s'interrompt.

---

## 3. Environnement, dépôt, branches, fichiers hors git

### 3.1 Logiciels

- **Versions de référence** (épinglées dans `requirements.txt`) : Python 3.11, numpy 2.4.6, numba 0.67.0 (llvmlite
  0.49.0), pygame 2.6.1 (SDL 2.28.4), pytest. Les runs de référence ont été entraînés avec elles. Jusqu'à C1, c'était
  sur Python 3.11.15, dans un conteneur cloud Linux à 4 cœurs ; depuis C2, sur le runner GitHub ubuntu-24.04
  (4 vCPU).
- **PC de l'utilisateur** : Windows 11, portable i3-1115G4 (2 cœurs, 4 threads, 7,7 Go). Environnement :
  ```
  python -m venv .venv
  .venv\Scripts\python.exe -m pip install -r requirements.txt imageio-ffmpeg
  .venv\Scripts\python.exe -m pytest -q tests/
  ```
  - Python 3.11.9 (dernier installeur Windows de la 3.11) ;
  - la suite complète prend ≈ 3 à 4 min sur ce PC ;
  - git et la CLI GitHub (`gh`) sont installés ; `gh` est connecté au compte de l'utilisateur ;
  - les nouvelles sessions doivent recharger le PATH (`git`, `gh`) si le terminal a été ouvert avant leur
    installation.
- numba parallélise l'évaluation batchée (blocs de `BATCH_BLOCK` = 64 créatures, 8 blocs au plus pour 500 enfants).
- **ffmpeg** : `pip install imageio-ffmpeg` (ou ffmpeg dans le PATH). `evo/video.py` cherche ffmpeg dans le PATH,
  puis via `imageio-ffmpeg`, sinon il écrit une séquence PNG et affiche la commande ffmpeg. Sans lui, 2 tests vidéo
  sont sautés.
- fontTools n'a servi qu'une fois, pour extraire l'instance SemiBold de Nunito Sans. La police produite est
  versionnée : on n'en a plus besoin.
- Sans écran : `SDL_VIDEODRIVER=dummy` (les exports le posent eux-mêmes).

### 3.2 Arborescence

```
README.md, CLAUDE.md, config.py, main.py, requirements.txt, pytest.ini (pythonpath = ., testpaths = tests)
.github/workflows/train.yml   entraînements, rejeux, tests et écrans sur GitHub Actions (§3.5)
docs/      spec, rapports des chantiers B et C, bilan, journal, ce document, images de référence, figures
assets/fonts/   Questrial-Regular.ttf, NunitoSans-SemiBold.ttf, leurs licences OFL, README (sources, SHA-256)
evo/       le code (§4)
tests/     15 fichiers, 185 tests (§14)
runs/      runs d'évolution            ← hors git (.gitignore)
out/       exports PNG/MP4 par phase   ← hors git
cache/     couches de décor pré-rendues ← hors git
artefacts/ archives et sorties rapatriées du runner GitHub ← hors git
.venv/     environnement Python du PC   ← hors git
```

### 3.3 Les runs (hors git ; ceux de référence sont sauvegardés sur la branche `sauvegarde-runs`)

**Sauvegarde :** la branche `sauvegarde-runs` n'a pas de code et pas d'historique commun avec les autres. Elle
contient 12 archives d'≈ 25 Mo et un README avec les SHA-256 et la restauration :
- chantier D (`runs_chantier_d_S.tar.gz`, run GitHub 38411711297, ajoutées à la v1.1, `28d7440`) ;
- C2 à 30° (`runs_butees_corps_30_S.tar.gz`) ;
- C2 à 6° (`runs_butees_corps_S.tar.gz`) ;
- B2 (`runs_S.tar.gz`).

Les archives de C2 et de D sont celles des artefacts GitHub ; elles y ont été ajoutées par des commits ordinaires.

**Restauration vérifiée** :
- les archives clonées depuis GitHub redonnent les dossiers identiques octet par octet (1 851 fichiers au gel de la
  v1 ; les 615 fichiers des runs D à la v1.1) ;
- le job `reproductibilite`, qui restaure depuis `sauvegarde-runs`, rejoue les champions de la génération 200 à
  leur hauteur stockée ;
- pour restaurer : `.github/scripts/restaurer_runs.sh` (bash, à la racine du dépôt) recrée les dispositions de la
  v1.1, avec les SHA-256 vérifiés.

**Non sauvegardés** : les anciens runs (`legacy_no_limits`), les runs de calibration, l'essai de 5 générations et les
exports de `out/`. C'est le choix de l'utilisateur ; les exports se refont en quelques minutes à partir des runs.

| Dossier | Contenu | Config |
|---|---|---|
| `runs/0`, `runs/1`, `runs/2` | **runs par défaut depuis la v1.1** : chantier D, butées articulaires et du corps, mains, cône de queue de 15°, report dissipatif (run GitHub 38411711297) | `CLEAN_PROJECTION = True`, `HAND_LIMITS = True`, `TAIL_CONE_DEG = 15`, `TAIL_CURVATURE_LIMITS = False` |
| `runs/butees_corps_30/0..2` | C2 à 30°, runs par défaut de la v1.0 (run GitHub 38278062446) | `BODY_LIMITS = True`, `TAIL_CONE_DEG = 30`, pas de clé du chantier D, donc False |
| `runs/butees_articulaires/0..2` | B2, butées articulaires seules ; runs par défaut jusqu'au gel de la v1 | `JOINT_LIMITS = True`, pas de clé `BODY_LIMITS`, donc False |
| `runs/butees_corps/0..2` | C2 avec un cône de 6°, gardé pour le rapport C2 (run GitHub 38266975229) | `BODY_LIMITS = True`, `TAIL_CONE_DEG = 6` |
| `runs/essai/0..2` | essai de 5 générations de C2 (durées sur le runner) | comme `butees_corps` |
| `runs/legacy_no_limits/0..2` | anciens runs de la phase 3b, sans butées (absents du PC actuel) | pas de clé `JOINT_LIMITS`, donc False |
| `runs/calib/*` | 6 runs de 30 générations (calibration de TORQUE_SCALE et de la prise, phase 3b, étape 1) | cités dans `config.py` |
| `runs/fit/*` | runs de 40 générations (grilles de fitness, phase 3b, étape 2) | cités dans `config.py` |
| `runs/train_*.log` | journaux d'entraînement (`train_chantier_d_sS.log` : runs par défaut ; `train_sS.log` : B2 ; `train_butees_corps_30_sS.log` : C2 à 30° ; `train_butees_corps_sS.log` : 6°) | |

- Chaque run contient : `gen_0000.npz` à `gen_0200.npz`, `stats.csv`, `config.json` (instantané complet de la
  config au lancement, `--set` compris) et `audit.csv`.
- **Durée** :
  - B2 : ≈ 15 à 18 min d'évaluation par graine (867 / 990 / 1071 s pour les graines 0 / 1 / 2) ; ≈ 8,5 min sans
    butées ;
  - C2 à 30° : 18 à 44 min par graine sur le runner. Les 14 butées du corps coûtent ×2,2 en évaluation ;
  - D : 15 à 49 min par graine sur le runner.
- **Disposition** :
  - jusqu'au gel de la v1, les runs de C2 s'appelaient `runs/butees_corps_30/S`, et ceux de B2 `runs/S` ;
  - de la v1.0 à la v1.1, `runs/S` contenait C2 à 30°, revenu depuis dans `runs/butees_corps_30/S` ;
  - pendant le chantier D, les runs D s'appelaient `runs/chantier_d/S` ;
  - les rapports citent les chemins de leur époque (notes en tête du rapport C2 et de `docs/chantier_d.md`).
- **Régénérer des runs** : sur le runner, `gh workflow run train.yml --ref <branche> -f mode=train -f run_name=<nom>`
  (§3.5) ; ou en local, `python main.py train --seed S --generations 200 --pop 1000 --run-dir runs/<nom>/S --set
  AUDIT_EVERY=10`. Le run est déterministe sur une même machine : même graine, même code, même config donnent les
  mêmes générations. Entre Linux et Windows, ce n'est pas vrai (§3.5).
- **Régénérer les anciens runs :** les relancer avec `--set JOINT_LIMITS=False` dans
  `--run-dir runs/legacy_no_limits/S`. Attention : le code a changé depuis, et l'identité au bit près avec les
  runs d'origine n'est garantie que pour le rejeu, pas pour un ré-entraînement.

### 3.4 Arbre des branches

| Branche | Contenu |
|---|---|
| `main` | phases 1 à 6, chantiers A, B et C1, et le workflow GitHub Actions (`d9317eb`) |
| `claude/chantier-c2-butees-corps` | `main` + C2 : moteur, butées du corps, outils de mesure, repli à 30°, rapport C2 |
| `claude/nettoyage-v1` | la branche C2 + le nettoyage (aucun changement de comportement), ce document à jour, README, bilan |
| `claude/chantier-d-diagnostic` | `main` (`v1.0`) + le diagnostic du chantier D (outils de mesure, rapport) |
| `claude/chantier-d` | la branche de diagnostic + le moteur D, ses mesures, son réentraînement et les runs D par défaut |
| `sauvegarde-runs` | pas de code : archives des runs de référence (D, C2 à 30°, C2 à 6°, B2 ; `28d7440`, §3.3) |

Chacune contient la précédente : nettoyage ⊂ diagnostic D ⊂ chantier D. `main` a été avancée sur
`claude/nettoyage-v1` au gel de la v1 (tag `v1.0`), puis sur `claude/chantier-d` (tag `v1.1`).

Ménage du 12 octobre 2026, validé par l'utilisateur : `main` (qui ne contenait que le commit initial) a été avancée
jusqu'au dernier commit de `claude/chantier-c-collisions`. Les branches `claude/modest-ritchie-mkwjnd`,
`claude/chantier-b-limites-articulaires` et `claude/chantier-c-collisions` ont ensuite été supprimées : chacune était
entièrement contenue dans `main`, rien n'a été perdu.

### 3.5 GitHub Actions et reproductibilité

**Pourquoi.** Le PC de l'utilisateur est lent (2 cœurs), et surtout **il ne rejoue pas les runs au bit près**. Mesuré
sur les champions B2 de la génération 200, entraînés sous Linux, avec les mêmes versions de numpy et numba :

| Graine | Hauteur stockée | Rejouée sous Windows | Écart |
|---|---|---|---|
| 0 | +34,241587941 m | +34,240889724 m | −0,7 mm |
| 1 | +33,447863030 m | +33,207706444 m | −24,0 cm |
| 2 | +35,323759508 m | +35,293234546 m | −3,05 cm |

C'est la bibliothèque mathématique (§5.3, §13) : la dynamique est chaotique, et un bit d'écart suffit. Le runner
GitHub ubuntu-24.04, lui, rejoue les 3 champions à l'identique (run 38255551159). **Tout ce qui rejoue ou mesure un
run entraîné passe donc par le runner.** Le PC reste utile pour le code, les tests (hors rejeu des runs), les lectures
de npz (`morpho`, `graphs`) et les planches.

**Le workflow** `.github/workflows/train.yml` est lancé à la main (`workflow_dispatch`). Il utilise la version du
fichier de la branche passée en `--ref`. Son environnement est figé : ubuntu-24.04, Python 3.11, numpy 2.4.6,
numba 0.67.0, pygame 2.6.1. Entrée `mode` :

| Mode | Ce qu'il fait |
|---|---|
| `train` | matrice sur `seeds` (3 graines en parallèle) ; `train --pop 1000 --set AUDIT_EVERY=10 <extra_set>` dans `runs/<run_name>/S` ; archive `runs_<run_name>_S.tar.gz` + SHA-256 + `pip_freeze.txt`, en artefact gardé 30 jours |
| `reproductibilite` | restaure les runs de référence depuis `sauvegarde-runs` (`.github/scripts/restaurer_runs.sh`, SHA-256 vérifiés), rejoue les champions de la génération 200 de D (`runs/S`), de C2 à 30° (`runs/butees_corps_30/S`) et de B2 (`runs/butees_articulaires/S`), échoue sur tout écart |
| `pytest` | la suite complète, avec les runs de référence restaurés (le test des runs locaux les rejoue) et, en option, les archives de un ou deux runs `train` (`source_run_id`, `source_run_id_2`) |
| `analyse` | runs de référence et archives des runs sources ; garde-fou (rejeu des champions D, C2 à 30° et B2) ; captures de la vidéo remplacées par des aplats (les artefacts sont publics) ; cache du décor ; `commandes` = sous-commandes de `main.py` séparées par « ; » (liste blanche, sans shell, sans guillemets ni espaces dans les valeurs) ; `out/` et les journaux en artefact |

```
gh workflow run train.yml --ref <branche> -f mode=pytest -f source_run_id=38278062446
gh workflow run train.yml --ref <branche> -f mode=train -f run_name=essai -f generations=5
gh workflow run train.yml --ref <branche> -f mode=analyse -f source_run_id=38278062446 -f "commandes=joints --seed 2 --gen 200 --top 50 --tail --run-dir runs/butees_corps_30/2 --export out/tail ; replay --gen 200 --run-dir runs/butees_corps_30/2 --export out/replay"
gh run watch <id>
gh run download <id> -D artefacts/<id>
```

- `gh run download` crée un sous-dossier par artefact.
- Vérifier les SHA-256 avant d'extraire (`Get-FileHash … -Algorithm SHA256`), puis `tar -xzf` à la racine du dépôt.
- Les images de `docs/reference/` ne sortent jamais dans les artefacts. Les planches avec les captures de la vidéo se
  font sur le PC (`planche`), à partir des rendus rapatriés.

---

## 4. Architecture du code

### 4.1 Modules (`evo/`)

| Module | Rôle |
|---|---|
| `physics.py` | `World` (points, liens, masses, prises, articulations, butées sur leurs propres triplets `limit_joints`), les 5 fonctions de la vidéo (`movement`, `gravity`, `hold`, `link`, `contract`), la projection de position, `substep`/`step`, les noyaux numba et leur référence Python, `spring_link` (méthode naïve du banc 4) |
| `skeleton.py` | topologie : indices des points (NECK=0 … R_FOOT=13, HEAD=14, queue à partir de 15), 13 os, `BRACES` (liens invisibles de rigidité des ceintures), `build_skeleton()` |
| `creature.py` | `Genome`, `random_genome`, `diagonal_gait_genome` (marche écrite à la main), `limp_genome`, `Creature` (contrôleur PD à horloge, prises, chute, énergie, hauteur), `JOINTS`, `JOINT_SIGNS`, `joint_limits_phi`, `body_limits` et `limit_groups` (C2), `target_bounds`, `torque_unit`, `fitness` |
| `batch.py` | évaluateur batché : toute la simulation de 10 s de toute la population dans un noyau numba, **identique au bit près** au moteur scalaire ; `pack`, `evaluate`, `benchmark` |
| `evolution.py` | `Population`, mutations, sélection, `train` (avec reprise), sauvegardes npz/csv/json, `run_config` + `LEGACY_DEFAULTS`, `apply_config`, `audit_champion` |
| `audit.py` | audit d'énergie étape par étape : qui ajoute ou retire de l'énergie ; classement par état des butées (engagement, contact, libre) |
| `joint_audit.py` | commande `joints` : angles anatomiques, butées, tours complets, côté de l'axe, croisements de segments, cône de queue, sauts d'énergie (`--energy`), croisements (`--crossings`) |
| `benches.py`, `debug_physics.py`, `calibration.py`, `render_schema.py` | phase 1 : les 9 bancs d'essai (8 de la spec + le sol), leur fenêtre et leur export, le tableau de stabilisation, le style « schéma pédagogique » |
| `render_debug.py`, `debug_creature.py` | vue debug de la créature (§7.6) : écorché sur fond bleu nuit |
| `scene.py` | décor jungle : cadrage (`Framing`), caméra en lerp, 6 couches pré-rendues avec parallaxe, cache disque, repères de hauteur |
| `render_lizard.py` | `LizardShape` : le lézard (queue, pattes en capsules, doigts, torse, tête, yeux), recalculé à chaque frame ; mode silhouette pour les miniatures |
| `replay.py` | `Replay` (rejeu au moteur scalaire, hauteur vérifiée) et `JungleView` (décor + lézard + HUD), fenêtre interactive, export |
| `hud.py` | badges, texte, étiquette de hauteur, carton de génération, icône ⏩ |
| `fonts.py` | chargement des polices avec repli ; vide son cache à `pygame.quit()` |
| `population.py` | vue population (grille de miniatures, tri animé) et cycle complet (`--cycle`) |
| `charts.py` | courbes d'évolution, histogramme (style calibration et style vidéo), comparaison de deux runs, graphe de diversité |
| `analysis.py` | mode analyse biomécanique : zoom, surcouche os + muscles, pourcentages |
| `compare.py` | comparaison de générations : fantômes |
| `video.py` | export MP4 via ffmpeg |
| `decor_check.py` | commande `decor` : contrôle du décor au-dessus de 23 m |
| `tail_audit.py` | C2 : `joints --tail` (queue à chaque sous-pas : longueur des os, oscillation contre le cône, posture, pénétration des butées par groupe, verdict du critère de repli) et `joints --fallen` (toutes les créatures tombées d'une génération, énergie et queue contre les seuils d'audit) |
| `morphology.py` | C2 : commande `morpho`, facteur moyen de longueur de chaque os par génération, deux runs superposés (npz seuls) |
| `planches.py` | C2 : commande `planche`, images côte à côte légendées (planches avec les captures de la vidéo, sur le PC) |
| `trace.py` | C2 : commande `trace`, rejeu pas à pas d'une créature avec l'audit d'énergie à chaque sous-pas (diagnostic) |
| `diag_projection.py` | chantier D : commande `diag-projection`, moteur tel quel contre des variantes substituées le temps de la mesure (projection : `vitesse_proj`, `dissipatif`, `passes120` ; queue : `courbure<β>` ; ordre : `alterne`), ou le moteur D avec un cône de ±θ (`D<θ>`) ; créature inerte (`--inerte`) ; énergie, queue, enfoncement par groupe de butées, singularité du cône, croisements, mains (lecture seule) |
| `diag_alterne.py` | chantier D : copies des noyaux du solveur où les butées de queue sont parcourues à l'envers une passe sur deux (mesure seulement) |

### 4.2 Commandes (`main.py`)

```
python main.py debug-physics [--bench N] [--export DIR] [--calibrate]
python main.py debug-creature [--mode diagonale|...] [--seed S] [--export DIR]
python main.py benchmark --pop 1000 [--seed S]
python main.py train --seed S --generations 200 --pop 1000 [--run-dir DIR] [--set CLE=VALEUR …] [--no-audit]
python main.py graphs --seed S [--run-dir DIR] [--out DIR] [--compare AUTRE_RUN] [--labels REF RUN]
python main.py histogram --seed S --gen G [--style calibration|video]
python main.py population --seed 2 --gen 200 [--export DIR] [--export-video MP4] [--cycle]
python main.py replay --seed 2 --gen 200 --rank 1 [--creature I] [--speed X] [--slow] [--title-card "…"]
                      [--export DIR] [--export-video MP4] [--no-cache] [--fps-report]
python main.py analyze --seed 2 --gen 200 --rank 1 [--speed X] [--slow] [--export DIR] [--export-video MP4]
python main.py compare --seed 2 --gens 0 23 100 200 [--speed X] [--slow] [--export DIR] [--export-video MP4]
python main.py decor --seed 2 --export DIR [--no-cache]
python main.py joints --seed S --gen G [--top N] [--sample N] [--energy] [--crossings] [--tail] [--export DIR]
python main.py joints --seed S --gen G --fallen [--run-dir DIR] [--export DIR]
python main.py morpho --seed S [--run-dir DIR] [--compare AUTRE_RUN] [--gens G …] [--out DIR]
python main.py trace --seed S --gen G --creature I [--run-dir DIR] [--export DIR]
python main.py diag-projection --seed S --gen G --creature I [--run-dir DIR]
python main.py planche IMAGE … --out PNG [--labels …] [--height H] [--crop X0 Y0 X1 Y1]
```

- `--seed` vaut 2 par défaut pour les écrans, 42 pour `train` et `graphs`.
- `--run-dir` est disponible partout (défaut `runs/<seed>`).
- `replay` sort en erreur (code 1) si la hauteur rejouée diffère de la hauteur stockée.

### 4.3 Formats des fichiers de run

- **`gen_XXXX.npz`** :
  - génome de toute la population : `lengths` (N,7), `strengths` (N,2,4,2), `period` (N,), `targets` (N,K,8),
    `holds` (N,K,4) ;
  - résultats : `score`, `height`, `energy`, `muscle_mass`, `fallen` ;
  - lignée : `parent` (indice dans la génération précédente), `is_child`, `root` (ancêtre de génération 0) ;
  - `stats` (JSON).
  - **Convention de lignée :** dans la génération N+1, les indices 0 à 499 sont les survivantes de la génération N
    dans l'ordre du classement (même génome, même score, pas de réévaluation) ; l'indice 500 + j est l'enfant de la
    survivante de rang j.
- **`stats.csv`**, une ligne par génération :
  - `gen`, `n` ;
  - hauteur : `height_mean`, `height_median`, `height_min`, `height_max` ;
  - `period_mean`, `period_std`, `muscle_mean` ;
  - énergie : `energy_mean`, `energy_median`, `energy_max` ;
  - `score_mean`, `score_max` ;
  - au sol : `fallen`, `fallen_frac` ;
  - `ancestors` (ancêtres distincts de génération 0) ;
  - meilleure : `best_index`, `best_height`, `best_period`, `best_energy`, `best_muscle` ;
  - `eval_seconds` ;
  - 50 colonnes d'histogramme `h-10` … `h+39` (barres de 1 m, valeurs hors bornes ramenées dans les barres
    extrêmes).
- **`config.json`** : instantané de toutes les constantes en majuscules de `config.py` au lancement. Un rejeu
  applique cette config (`evolution.use_run_config`). Une clé absente prend sa valeur de
  `evolution.LEGACY_DEFAULTS` (aujourd'hui `{"JOINT_LIMITS": False}`) : c'est ce qui fait se rejouer à l'identique
  les runs d'avant une nouveauté.
- **`audit.csv`** : audit du champion toutes les `AUDIT_EVERY` générations. Colonnes :
  - `gen`, `index`, `height`, `height_replay` ;
  - énergie créée : `created_J`, `created_height_m` ;
  - vitesses : `max_speed`, `max_torso_speed` ;
  - erreurs de longueur : `max_length_error`, `max_tail_error` ;
  - `max_height` ;
  - butées : `limit_engagements`, `limit_jump_max_J`, `limit_jump_sum_J`, `free_jump_max_J` ;
  - `alerts`.

### 4.4 Flux de données

- `train` : `random_population` → `batch.evaluate` (10 s × 1000 créatures en un appel numba) → `next_generation`
  (tri, survivantes, enfants mutés, seuls les enfants évalués) → sauvegarde → audit périodique du champion.
- Écrans : `Replay` relit un npz, applique la config du run, rejoue la créature au moteur **scalaire** et enregistre
  un état par frame (1/60 s). `JungleView`, `AnalysisView` et `CompareView` dessinent ces états.
- La vue population n'utilise pas le moteur scalaire (≈ 18 min pour 1000 créatures) : elle recalcule les poses
  finales par l'évaluateur batché (≈ 5 s) et vérifie que les hauteurs égalent les hauteurs stockées.

---

## 5. Le moteur physique

### 5.1 Un sous-pas (`physics.substep`)

```
gravity        v += g·h (points libres)
contract       v += F_muscles/m·h (couples de Contract)
[damping]      désactivé (DAMPING = 0)
hold           v[tenus] = 0
link           passes de Gauss-Seidel sur les vitesses : liens, puis butées, puis sol
hold           v[tenus] = 0
movement       p += v·h
project_links  passes de projection de position : liens, puis butées proches, puis remontée au sol
[report]       chantier D (CLEAN_PROJECTION) : v += α·Δp/h, report dissipatif de la correction de position
```

**Report dissipatif de la projection** (chantier D, drapeau `CLEAN_PROJECTION`, True ; absent d'une config de run :
False) :
- après la projection, avec Δv = Δp/h, B = Σ m·v·Δv et A = Σ m·|Δv|² : v += α·Δv, α = min(1, −2B/A) si B < 0,
  sinon 0. L'énergie cinétique varie de α·B + ½·α²·A ≤ 0 : le report ne peut que retirer de l'énergie ;
- il supprime l'énergie créée par les créatures couchées : la projection les remontait au-dessus du sol sans corriger
  leur vitesse vers le bas (B2 n°868 : 1 292,5 J → 0 J ; tombées de la gén. 0 : 606 J → 5,5 J) ;
- `physics.projection_velocity` (numba et référence Python), même calcul dans `batch._simulate_block` ; étape
  `report_projection` de l'audit d'énergie ; posé par `Creature` (`World.clean_projection`), les bancs de la phase 1
  gardent la projection seule.

- Pas de temps : `DT = 1/60` s, `SUBSTEPS = 8`, donc h = 1/480 s. 10 s = 4 800 sous-pas.
- Passes : `N_ITER = 30` sur les vitesses, `N_POS_ITER = 12` en projection (la spec suggérait 1 à 3).
- **`BETA = 0` : le biais de Baumgarte est désactivé.** La stabilisation ne passe que par la projection de
  position. Historique de ce choix au §9 (phase 3a) : le mélange biais + projection créait de l'énergie.
- Liens rigides : impulsion le long du lien qui annule la vitesse relative, pondérée par les masses inverses ; un
  point tenu a une masse inverse nulle.
- **Sol** (y = `GROUND_Y` = 0), résolu dans les mêmes passes :
  - impulsion normale cumulée ≥ 0 et frottement de Coulomb borné par μ × l'impulsion normale (`GROUND_FRICTION` = 1) ;
  - le contact entre dans le solveur à moins de `CONTACT_MARGIN` = 0,05 m, ou si le point le franchirait dans le
    sous-pas ;
  - terme spéculatif : Ċ ≥ −C/h avant le contact (y arriver pile, pas au-delà), Ċ ≥ −BETA·C/h au-delà ;
  - la pénétration résiduelle est corrigée par la projection.
- **Masses :** chaque os donne la moitié de sa longueur à chacune de ses extrémités (vérifié contre l'image 20).
  Les liens invisibles des ceintures n'ont pas de masse.
- **Dissipation :** la correction des vitesses est stable mais amortie, d'ordre h. Sur un pendule simple à 30°,
  elle retire 3,7 % de l'énergie en 20 s (1,9 % avec 16 sous-pas, 0,96 % avec 32).

### 5.2 Butées articulaires (chantier B2)

- **Contrainte à sens unique** sur l'angle signé θ d'un triplet (A, pivot P, B) : u = signe·θ doit rester dans
  [lo, hi].
- **Impulsion de la forme de `Contract()` :**
  - J_A = (ra_y, −ra_x)/|ra|², J_B = (−rb_y, rb_x)/|rb|², J_P = −(J_A + J_B) ;
  - forces et moments de somme nulle ;
  - impulsion cumulée ≥ 0.
- **Même schéma que le contact au sol :**
  - entrée dans le solveur à moins de `JOINT_LIMIT_MARGIN_DEG` = 2° ou si la butée serait franchie dans le
    sous-pas ;
  - terme spéculatif −C/h ;
  - `BETA = 0` ;
  - pénétration corrigée par la projection seule.
  L'utilisateur a refusé explicitement un biais propre aux butées : « vous avez déjà la preuve que ce mélange crée
  de l'énergie parasite ».
- **Borne visée :** la plus proche sur le cercle, si bien qu'un angle très hors bornes repart par le côté court.
- **Projection restreinte :** seules les butées à moins de la marge au début de la projection y entrent. Les
  recalculer toutes à chaque passe doublait le temps d'évaluation.
- **Ordre dans chaque passe :** liens, butées, sol. Il a été conservé après un cas limite (voir §9, B2).
- **Code partagé :** trois fonctions numba (`_limit_geometry`, `_limit_mass`, `_limit_rate`) servent au noyau
  scalaire, à la référence Python et à l'évaluateur batché, pour garantir les mêmes opérations dans le même ordre.
- **API :** `World.set_joint_limits(sign, lo, hi, triplets=None)`, `World.limit_violation()`, `World.limit_active`
  (butées entrées dans le solveur au dernier sous-pas). Depuis C2, les butées portent sur leurs propres triplets,
  `World.limit_joints` (Q, 3), séparés des muscles (`world.joints`). Sans `triplets`, ce sont les 8 articulations,
  comme en B2, et les opérations restent identiques au bit près.
- **Drapeau `JOINT_LIMITS`** (True). Absent d'une config de run, il vaut False.

**Butées du corps (chantier C2, drapeau `BODY_LIMITS`, True ; absent d'une config de run : False).** Même primitive,
14 butées posées après les 8 articulations, sur des triplets (NECK, PELVIS, X), l'angle étant celui de X vu du bassin
depuis l'axe bassin → cou :
- **pieds** (2) : (NECK, PELVIS, L_FOOT), signe +1, et (…, R_FOOT), signe −1. u ∈ [m, 180° − m] garde chaque pied de
  son côté de l'axe (m = `FOOT_AXIS_MARGIN_DEG` = 0) ;
- **queue** (12) : (NECK, PELVIS, TAIL_k), u ∈ [180° − τ, 180° + τ], τ = `TAIL_CONE_DEG` = **15** [CHOIX] depuis
  le chantier D (C2 : 30°, repli depuis 6° [DÉDUIT], §9). Au repos, la queue est dans l'axe (θ = ±180°), au centre
  du cône ;
- **mains** (2, chantier D, drapeau `HAND_LIMITS`, True ; absent : False) : (NECK, PELVIS, L_HAND), signe +1, et
  (…, R_HAND), signe −1, u ∈ [m, 180° − m] (m = `HAND_AXIS_MARGIN_DEG` = 0), posées après la queue (butées 22 et 23) ;
- `creature.body_limits()` construit ces butées et `limit_groups()` les range par groupe (articulations, pieds,
  queue, mains) ;
- seulement si `JOINT_LIMITS` ;
- coût : ×2,2 sur l'évaluation, la queue étant presque toujours en contact ;
- **queue tenue par sa courbure** (candidat (d) du chantier D, drapeau `TAIL_CURVATURE_LIMITS`, **False**) : explorée
  puis écartée, code gardé. La chaîne de 12 butées couplées ne converge pas avec ce solveur : la créature inerte,
  posée sur sa queue tenue droite comme une échasse, crée 8,16 J (`docs/chantier_d.md` §3) ;
- **limites connues** (`docs/chantier_c_c2.md` §6, `docs/chantier_d.md` §5 et §6) :
  - la queue d'une créature tombée peut s'étirer à l'impact quand elle est à la fois en butée et posée au sol
    (C2 : jusqu'à 43,8 % ; D : jusqu'à 12,3 %) ;
  - singularité du cône : un point de queue revenu près du bassin (sommet du cône) peut sortir du cône pendant un
    sous-pas. Avec le moteur D, aucune grimpeuse n'est touchée, et aucune énergie n'est créée pendant ces sous-pas.

### 5.3 Déterminisme et identité au bit près

- Le noyau numba et la référence Python font exactement les mêmes opérations dans le même ordre. Les tests vérifient
  l'égalité (1e-9 ou `assert_array_equal`).
- L'évaluateur batché reproduit le moteur scalaire **au bit près** :
  - `World.joint_angles` utilise `math.atan2` (bibliothèque C, comme numba), pas `np.arctan2` : la version
    vectorisée de numpy diffère d'un bit dans ≈ 7 % des cas ;
  - les forces musculaires sont accumulées dans l'ordre de `np.add.at` ;
  - la somme des 8 activations suit l'ordre par paires de numpy (`_pairwise_sum8`).
- **La dynamique est chaotique :** un écart d'un bit sur un angle peut faire passer une créature de −8,18 m à
  −7,25 m. Toute modification du moteur, même anodine, change donc les runs. C'est pourquoi chaque nouveauté
  physique a un drapeau dont l'absence redonne l'ancien comportement.
- Graine par génération : `default_rng([seed, gen])` ; la reprise d'un run redonne exactement les mêmes générations.

---

## 6. La créature

### 6.1 Squelette et échelle

- **Points :** 14 points du §2.2, plus HEAD (14), puis la queue : `TAIL_SEGMENTS` = 12 points chaînés depuis le
  PELVIS, longueur totale `TAIL_LENGTH_FACTOR` = 1,2 × la colonne, sans muscles.
- **Os :** colonne, 2 clavicules, 2 humérus, 2 avant-bras, 2 demi-bassins, 2 fémurs, 2 tibias, tête (NECK–HEAD).
- **Liens invisibles (`BRACES`)** : L/R_SHOULDER–PELVIS, L/R_HIP–NECK, HEAD–L/R_SHOULDER. Ils triangulent pour
  rendre les ceintures rigides (les liens épaule–épaule seraient alignés avec les clavicules et ne bloqueraient
  rien). Écart d'angle mesuré sur 303 grimpes : 0,30° au plus.
- **Longueurs de référence** (§2.5, m) : colonne 0,45, clavicule 0,12, humérus 0,22, avant-bras 0,20,
  demi-bassin 0,10, fémur 0,24, tibia 0,20. Le génome les multiplie par U(0,6 ; 1,4).
- **`BODY_SCALE = 7` [DÉDUIT]** : tout le corps est mis à l'échelle ×7. Les longueurs du §2.5 donnent un lézard de
  1,1 m, alors que les images montrent :
  - 20,2 px/m, d'après les étiquettes de hauteur des images 03, 04 et 05 ;
  - un lézard de ≈ 7,7 m de la tête au bout de la queue, et un tronc de 12,3 m de large ;
  - un champion qui monte 36 m en 10 s avec une horloge de 0,6 s, soit 2,2 m par cycle, impossible avec des pattes
    de 0,4 m.
  `BODY_SCALE = 1` redonne exactement les longueurs de la spec.
- **Posture de repos** (`REST_POSE_DEG`, côté gauche, depuis +x ; le droit est le miroir) : humérus 135°,
  avant-bras 100°, fémur 225°, tibia 260°. Bras levés vers le haut et l'extérieur, jambes vers le bas.
- **Côtés :** le côté gauche (points L_*) est à x < 0.

### 6.2 Articulations, muscles, contrôleur

- **8 articulations**, indice j = côté·4 + type (côté 0 gauche, 1 droit ; type 0 épaule, 1 coude, 2 hanche,
  3 genou). Triplets (`creature.JOINTS`) :
  - épaule (NECK, SHOULDER, ELBOW) ;
  - coude (SHOULDER, ELBOW, HAND) ;
  - hanche (PELVIS, HIP, KNEE) ;
  - genou (HIP, KNEE, FOOT).
- **φ** = angle compté depuis le repos, en miroir à gauche et à droite, orienté pour que le muscle « + »
  l'augmente. `JOINT_SIGNS` donne le sens de l'angle moteur A→B correspondant.
- **16 muscles**, deux par articulation :

  | Articulation | Muscle « + » | Muscle « − » |
  |---|---|---|
  | épaule | deltoïde | grand dorsal |
  | coude | biceps | triceps |
  | hanche | fléchisseurs de hanche | fessiers |
  | genou | ischios | quadriceps |

  Un test vérifie que chacun fait l'action de son nom.
- **Forces max** dans [0, `S_MAX` = 1,6] ; `SYMMETRIC_MORPHOLOGY = True` (gauche = droite). Masse musculaire = somme
  des 16 forces ; la queue n'en a pas.
- **Couple** = force × `torque_unit()`, avec torque_unit = `TORQUE_SCALE` × masse totale × g × longueur de colonne
  de la créature de référence. Le calibrage ne dépend donc pas de `BODY_SCALE`.
- **Contrôleur PD :**
  - u = clamp(KP·wrap(φ_cible − φ) − KD·φ̇, −S_minus, +S_plus), avec KP = 6 et KD = 1,5 ;
  - horloge de période `period`, K = 4 poses, pose courante = floor(phase·K) ;
  - la cible change instantanément, le PD lisse.
- **Prises :** au début de chaque intervalle, chaque patte tient (à sa position courante) ou lâche, selon la pose.
  Elle ne peut tenir que si elle est sur la bande du tronc (|x − TRUNK_X| ≤ TRUNK_WIDTH/2 = 6,15 m) et que la
  créature n'est pas tombée.
- **Chute :** dès qu'un point du corps (hors queue) touche le sol, à `FALL_CONTACT_EPS` = 1 mm près, la créature est
  « tombée » et lâche toutes ses prises (`FALL_DISABLES_HOLD`). « Au sol, une créature tombée reste au sol ».
- **Hauteur** = déplacement vertical du centre du torse (milieu NECK–PELVIS) depuis le départ, à
  `START_HEIGHT` = 10,3 m au-dessus du sol. C'est le score de hauteur et la valeur du HUD. Une créature couchée
  finit vers −8,7 m (vidéo : −7,8 à −9 m).
- **Énergie** (`ENERGY_MODE = "torque"`) : E = `ENERGY_SCALE` (0,413) × Σ|force musculaire|·dt. L'échelle a été
  réglée pour donner une médiane de génération 0 à 14,5, contre 13 à 16 dans la vidéo.
- **Fitness :** score = h − 0,4·E − 0,1·M (`FITNESS_ENERGY`, `FITNESS_MUSCLE`).
- **Butées (B2)** : `joint_limits_phi()` traduit `JOINT_LIMITS_DEG` en φ, et `Creature` pose les butées en
  u = signe·θ. Les cibles du génome sont tirées et mutées dans la plage articulaire (`target_bounds()`).

### 6.3 Génome

`Genome(lengths (7,), strengths (2,4,2) [côté, articulation, (+,−)], period, targets (K,8) rad, holds (K,4) bool)`.

| Gène | Initialisation |
|---|---|
| longueurs | référence × BODY_SCALE × U(0,6 ; 1,4) |
| forces | U(0, 1,6) |
| période | U(0,5 ; 5,0) s, bornée à [0,3 ; 8] |
| cibles | dans la plage articulaire (avant B2 : ±90° autour du repos) |
| prises | vraies avec probabilité `HOLD_PROBABILITY` = 0,62 |

Génomes écrits à la main : `diagonal_gait_genome()` (allure diagonale avec double appui, K = 4) et `limp_genome()`
(inerte).

---

## 7. L'évolution

- **Population :** 1000 créatures ; les 500 meilleures au score survivent **avec leurs résultats** (moteur
  déterministe, donc pas de réévaluation) ; chacune a 1 enfant muté ; seuls les 500 enfants sont évalués.
  200 générations.
- **Mutations** (`evolution.mutate`) :
  - chaque gène continu est muté avec `P_MUT` = 0,1 ;
  - amplitude gaussienne, σ = 5 % de la plage d'initialisation du gène (avec butées : de la plage articulaire de
    chaque articulation) ;
  - avec `P_BIG` = 0,05, l'amplitude est ×10 ;
  - les valeurs sont ramenées dans leurs bornes ;
  - les booléens de prise sont inversés avec `P_FLIP` = 0,03 ;
  - en morphologie symétrique, une seule moitié des forces est mutée puis recopiée ;
  - `PERIOD_MUTATION = "linear"` ; le mode `"log"` existe mais n'a pas aidé (§9).
- **Lignée :** `parent`, `is_child`, `root` ; `stats.csv` compte les ancêtres distincts de génération 0.
- **Audit du champion** toutes les `AUDIT_EVERY` générations (`audit.csv`). Alertes :
  - énergie créée hors muscles > 5 cm en équivalent hauteur (énergie ÷ poids) ;
  - vitesse d'un point > 80 m/s ;
  - vitesse du torse > 20 m/s ;
  - hauteur > 50 m ;
  - erreur de longueur des os > 1 %, de la queue > 5 % ;
  - saut d'énergie dans un sous-pas où une butée s'engage > 5 mm.
- **Surcharges :** `--set CLE=VALEUR` sont appliquées avant tout et enregistrées dans `config.json`. Un bug corrigé
  en B2 lisait `AUDIT_EVERY` avant d'appliquer les surcharges.
- **Reprise :** relancer `train` sur un run existant repart de la dernière génération sauvegardée. Une clé de
  `config.json` qui n'existe plus dans `config.py` est ignorée, avec un message (`apply_config(strict=False)`).

---

## 8. Le rendu et les écrans

### 8.1 Décor (`scene.py`)

- **Cadrage :** 1280 × 720 px, `SCENE_SCALE` = 20,2 px/m, haut de l'herbe à y = 548 px, tronc centré.
- **Caméra :**
  - cadrage fixe au départ, puis suivi vertical en lerp (`CAMERA_LERP` = 0,12 de l'écart rattrapé par frame) ;
  - elle ne descend jamais sous le cadrage de départ et s'arrête en haut du décor (`DECOR_TOP_HUD` = 50 m).
- **6 couches** dessinées une seule fois (supersampling ×2) puis blittées avec leur parallaxe. Parallaxes
  **mesurées** sur les images (corrélation verticale 03→05, 03→06, 09→08), au lieu des [CHOIX] du §5.6 :

  | Couche | Parallaxe |
  |---|---|
  | ciel | 0 |
  | très lointain | 0,1 (non mesurable, valeur de la spec) |
  | lointain | 0,28 (spec 0,25) |
  | mi-proche | 0,56 (spec 0,5) |
  | plan (tronc, sol, grand palmier) | 1,0 |
  | premier plan | **1,0** (spec 1,2) |

- **Cache disque** dans `cache/scene/`. La clé couvre `SCENE_SEED`, tous les paramètres de décor, **un hash du code
  source de `scene.py`** (demande de l'utilisateur) et le cadrage ; `--no-cache` force la régénération.
- **Encodage RLE** des couches transparentes : le décor passe de 6 à 2 ms par frame. Un premier blit au chargement
  évite un pic de 45 ms.
- **Éléments :**
  - ciel en dégradé fixe à l'écran, avec le haut mesuré à #7BBA77 ;
  - tronc à facettes éclairé de la gauche, base évasée ;
  - branches en L qui portent les canopées du premier plan : `BRANCHES` à 12, 46 et 58 m, `FG_CANOPY_LIFT` = 5,3 ;
  - silhouettes lointaines en blobs arrondis sur troncs fins, beaucoup de palmiers ;
  - arbre latéral, palmiers, agaves et fougères ;
  - herbe dentelée, terre, rochers ;
  - canopées du premier plan à contour irrégulier (8 à 12 sommets), dessous en deux tons, facettes claires, petits
    triangles sombres, qui passent devant le lézard.
- **Repères de hauteur :**
  - tous les 10 m, ligne blanche et libellé en Questrial 50 ;
  - **transitoires** : affichés au premier franchissement vers le haut de la hauteur HUD, pleins pendant 0,5 s,
    fondu de 0,3 s, jamais redéclenchés ;
  - **jamais quand le HUD est affiché** (images 06 et 08 contre 03, 05 et 09).

### 8.2 Lézard (`render_lizard.py`)

- **Ordre de dessin :** queue, pattes en capsules, doigts (5 rayons en éventail avec un disque au bout), torse
  ovoïde, tête, yeux.
- **Deux tons** par côté anatomique : #5CAC24 à gauche, #4CA40C à droite ; les membres sont un cran plus sombres
  (image 02).
- **Membres et torse ×1,4 :** la vidéo montre un lézard compact.
- **Queue dessinée prolongée** au-delà du dernier point physique jusqu'à `TAIL_VISUAL_FACTOR` = 1,9 × la colonne,
  avec une courbure amortie (`TAIL_VISUAL_DAMPING` = 0,6), sans jamais passer sous le sol. La queue physique fait
  1,2 × la colonne.
- **Supersampling ×2** dans une toile recadrée sur le lézard. Seules les puissances de 2 sont exactes avec
  `smoothscale`.
- **Mode silhouette** (une couleur, sans doigts) pour les miniatures.

### 8.3 HUD (`hud.py`, phase 5a)

- **Badges en haut à gauche** (fond #2C242C à 85 %), icônes vectorielles dessinées ×4 puis réduites :
  - horloge cyan : période ;
  - éclair jaune : énergie cumulée, `ENERGY_SCALE` inclus ;
  - muscle rose : masse musculaire.
- **Texte en haut à droite :** « Génération: N », « Classement: #R » (ou « Créature: i »), « Temps: x.x s ».
- **Étiquette de hauteur** à gauche du tronc, pointe vers la droite, triple chevron vert, hauteur brute
  (« 23.1 m »). Elle reste visible sous une canopée.
- **Carton de génération** : 1,5 s puis fondu de 0,5 s, sous-titre `--title-card`.
- **Icône ⏩** pour un replay accéléré (touche F ou `--speed 4`).
- **Positions :** à 1 à 3 px des images 03 et 09. Coût : 0,4 à 0,5 ms par frame.
- **Polices :** Questrial (HUD, cartons, repères ; reproduit l'encre de la vidéo au pixel près) et Nunito Sans
  SemiBold (instance wght 600 extraite de la police variable de google/fonts). Licence OFL, versionnées, avec repli
  sur les polices du système.
- **Voile du carton clair** (#F0ECE0 à 150/255), d'après l'image 39, alors que le §6 dit « voile sombre ».
  L'utilisateur n'a pas de préférence ; une ligne de config suffit pour revenir au sombre.

### 8.4 Vue population et histogramme (`population.py`, `charts.py`, phase 5b et chantier A)

- **Grille de 50 × 20**, d'après l'image 24 et le choix de l'utilisateur (le §7.1 dit 40 × 25) : origine
  (67,5 ; 64,5), pas (23,43 ; 30,68) px. Fond à vignette mesuré.
- **Miniatures** en silhouette verte #7AA842 à 2,2 px/m, avec un point clair aux mains et aux pieds. Elles sont
  **redressées tête en haut** (axe PELVIS→NECK vertical), y compris les créatures au sol, à la demande de
  l'utilisateur (images 24 et 25) ; dans la grille seulement.
- **Place de calcul** = indice du npz, rangé en colonnes. **Place triée** = rang, en lecture par lignes (1 = en haut
  à gauche). **Tri animé** : ease-in-out, 2 s après 0,5 s d'attente.
- **Cycle complet (`--cycle`, chantier A)**, 13,7 s, qui demande la génération N+1 sauvegardée :
  1. apparition des 50 colonnes de gauche à droite en 2,5 s. C'est une **cadence fixe de présentation**, choisie
     par l'utilisateur : l'évaluateur calcule tout d'un bloc, sans ordre d'arrivée réel ;
  2. tri, puis histogramme pendant 2 s ;
  3. élimination des 500 perdantes colonne par colonne (l'image 25 correspond à 6 colonnes éliminées) ;
  4. naissance de l'enfant de la survivante de rang j dans la case 500 + j, **dans sa posture de repos** (choix de
     l'utilisateur : il n'est pas encore évalué).
- **Histogramme style vidéo** (images 26 à 28) :
  - x de −10 à 40 m, barres de 1 m contiguës #94F474 ;
  - y fixe de 0 à 500 ; une barre au-delà est dessinée tronquée ;
  - géométrie à 1 px près ;
  - le style « calibration », à trois panneaux, reste celui par défaut de `graphs`.

### 8.5 Mode analyse (`analysis.py`, phase 5c)

- **Zoom :** 61,3 px/m, pour que la colonne mesure 177 px comme sur l'image 11 ; torse à y = 389 ; **sans le
  premier plan**, dont les canopées cacheraient la surcouche.
- **Os** crème #FCECD4, articulations en disques, NECK et PELVIS plus gros.
- **16 muscles :**
  - grand dorsal en « V » ;
  - fléchisseurs de hanche en triangle pointe en haut ;
  - deltoïde et fessiers en ovales ;
  - fuseaux de part et d'autre de l'humérus (biceps, triceps) et du fémur (ischios, quadriceps) ;
  - taille ∝ force max du génome ;
  - couleur de #FC5464 à #FC0434 selon la contraction instantanée enregistrée.
- **8 pourcentages** (force max en % de S_MAX), en Nunito Sans SemiBold 40, reliés par un trait blanc ; ils
  apparaissent un par un, de 1 s à 8,7 s.
- **Ralenti** ×0,25 (`--slow`, touche S).
- **Pas reproduit :** le petit point rouge foncé d'une paume (images 11 et 12), dont le sens est inconnu.

### 8.6 Comparaison de générations (`compare.py`, phase 5c)

- **Champions :** générations 0, 23, 100 et 200 rejoués, partis ensemble et montrés au même instant, chacun à sa
  hauteur. Ce [CHOIX] a été signalé : la vidéo ne montre pas le détail.
- **Fantômes** d'opacité 0,45 à 0,9 croissante avec la génération ; **un libellé souligné par fantôme**, empilés
  sans chevauchement, avec une ombre de 1 px.
- **Échelle fixe** calculée une fois pour que le plus grand écart des 10 s tienne dans l'écran (marges 7 et 7,5 m).
  Pas de zoom dynamique : le décor est pré-rendu à une seule échelle. Sans premier plan.
- **Libellés qui débordent :** la pile remonte en bloc et finit 4 px au-dessus du bord.

### 8.7 Vidéo (`video.py`, phase 6)

- Chaque image est rendue puis envoyée en RGB brut à ffmpeg (libx264, yuv420p, crf 18, 60 images/s), sans PNG
  intermédiaires. Le rendu est identique à la fenêtre : lerp, carton, HUD, ⏩ ; la dernière image est tenue 1 s.
- **stderr de ffmpeg** dans un fichier temporaire, relu seulement en cas d'échec (demande de l'utilisateur : un tube
  plein bloquerait l'encodage).
- **Contrôle :** les images extraites des MP4 ne s'écartent en moyenne que de 1,6 à 1,8 niveaux (sur 255) des PNG
  exportés aux mêmes instants (compression).

### 8.8 Contrôle du décor en hauteur (`decor_check.py`, chantier A)

- Une seule image de référence montre le décor au-dessus de 23 m : l'image 08 (repère de 30 m). Aucune ne couvre 30
  à 50 m.
- **Comparaison avec l'image 08** : relevé de palette (médiane par zone, ±12) et position de la canopée par rapport
  au repère.
- **Cohérence interne de 20 à 50 m :**
  - répétition entre tranches de 5 m ≤ 4 % ;
  - tronc continu ;
  - repères à 0,1 px de leur position calculée ;
  - le décor couvre tout le haut de l'écran à 50 m.

### 8.9 Temps par frame (conteneur sans écran)

| Écran | Temps moyen |
|---|---|
| Replay | ≈ 4,5 à 6,5 ms |
| Analyse | 10,5 ms (phase 5c), 12,5 à 14,8 ms plus tard sur une autre machine |
| Comparaison | 10,9 à 15 ms |

- La fenêtre interactive simulée tient ≈ 61,8 fps.
- Les mesures varient d'un facteur 3 selon l'hôte (la session a changé de machine plusieurs fois) : à refaire sur
  une machine stable avant de juger le budget de 16,7 ms.
- Commande à lancer chez soi : `python main.py replay --seed 2 --gen 200 --rank 1 --fps-report`.

---

## 9. Historique complet, phase par phase

### Phase 1 : moteur et bancs d'essai

**Demande et décisions initiales**
- Plan proposé et discuté. Choix de l'utilisateur : stabilisation Baumgarte + projection, numpy simple d'abord,
  comparaison avec la méthode « ressort » naïve sur le banc 4 (touche M), validation visuelle par fenêtre et PNG.
- Ajustements demandés ensuite :
  - noyau de liens en numba (`@njit(cache=True)`), avec la boucle Python gardée comme référence (égalité à 1e-9) ;
  - comparer BETA seul, projection seule et les deux ;
  - test du pendule simple contre T = 2π√(L/g) ;
  - priorité au moteur, aux tests et aux PNG, le mode interactif ensuite ;
  - corriger la « section 12 » de `CLAUDE.md`.

**Bancs d'essai** (chacun atteint son critère chiffré)
- mouvement rectiligne : 6·10⁻¹⁴ m d'écart ;
- gravité : 12,26 mm d'écart à la parabole, l'erreur attendue du schéma ;
- point fixé : immobile ;
- lien rigide : < 0,001 % d'erreur, contre 14,8 % d'étirement pour le ressort naïf ;
- itérations : erreur de 4,5·10⁻¹ à 0 passe, 3,4·10⁻⁷ à 20 passes ;
- contraction : somme des forces et des moments ≈ 10⁻¹⁶ ;
- masses : identiques à l'image 20 ;
- pendule humain (pendu 10 s par une main) : 0,14 % d'erreur sur le corps, 0,50 % sur la queue ;
- sol (ajouté en phase 2).

**Stabilisation** (tableau dans `config.py`) : Baumgarte seul injecte 0,53 J et étire la queue de 9,8 % ; « les
deux » (BETA 0,2 + 8 passes) a été retenu en phase 1, sans énergie injectée sur ce banc.

**Pendule simple** (masse sur les extrémités, donc pendule idéal) : écart de 0,047 % à 5°, l'effet d'amplitude
θ0²/16. Tolérances : 1e-3 sur la formule brute, 1e-4 sur la formule corrigée.

**Vitesse :** physique en numba à 0,32 ms par frame (52 × le temps réel), contre 3,34 ms en Python.

**Validation :** `SUBSTEPS = 8` gardé et configurable.

### Phase 2 : sol, mur, créature

**Fait**
- Sol dans le solveur (inélastique, μ = 1) et banc 9 : la distance de glissement égale v0²/(2μg) à 5 mm près.
- Mur : prise seulement sur la bande du tronc. Créature complète : 16 muscles, contrôleur PD à horloge, K = 4 poses.
- **`BODY_SCALE = 7` [DÉDUIT]** proposé et validé (voir §6.1).
- Test de fin de phase : la marche diagonale avec double appui écrite à la main monte de +3,75 m en 10 s sans tomber.
  Sans double appui, elle fait +4,83 m mais tombe vers 12 à 14 s : le contrôleur ne connaît pas l'orientation du
  corps, qui penche un peu plus à chaque cycle.

**Validation et consignes suivantes**
- L'utilisateur fixe `START_HEIGHT = 9`.
- Avant la phase 3, il demande de vérifier qu'aucun mécanisme ne crée d'énergie, sur la créature aléatoire qui
  monte de +9 m.

### Phase 3a : audit d'énergie et évaluateur batché

**Audit d'énergie** (`evo/audit.py`, rejeu étape par étape)
- La créature n° 35 de la graine 123 grimpe légitimement : 0 J créé hors muscles, montée entièrement payée par les
  muscles.
- **Défaut du moteur trouvé :** sur une créature inerte, 7,7 J étaient créés à l'impact au sol. La queue,
  comprimée de 5 %, recevait du biais de Baumgarte une vitesse qui écartait ses points, pendant que la projection
  corrigeait la même erreur. C'est exactement le risque que l'utilisateur avait signalé en phase 1.
- **Correctif : `BETA = 0` et 12 passes de projection.** Il reste 0,14 J à l'impact, venus de la projection qui
  décomprime la queue (0,008 % de l'énergie de la chute). C'est **l'origine de la règle « pas de biais »** reprise
  pour les butées.

**Évaluateur batché**
- 1000 créatures × 10 s en 4,86 s sur 4 cœurs (objectif : < 10 s).
- Gain obtenu par l'entrelacement de 64 créatures par cœur (`BATCH_BLOCK`), qui masque la latence de Gauss-Seidel
  (26,1 s à 1 par bloc), et par `error_model="numpy"`.
- Identité au bit près sur 21 créatures, grâce au correctif `math.atan2`.

### Phase 3b : évolution et calibration

**Étape 1 : TORQUE_SCALE, prise, énergie, hauteur de départ**
- **Blocage :** TORQUE_SCALE seul ne peut pas donner à la fois « ≈ 45 % au sol » et « la meilleure ne grimpe pas »
  (balayage de 0,10 à 1,50). La part au sol dépend surtout de `HOLD_PROBABILITY` : 51 des 70 créatures au sol d'un
  échantillon tenaient encore le mur quand un pied a touché le sol (descente « en rappel »).
- **Intervention de l'utilisateur :** « le plafond de force est aussi le plafond de grimpe ». Il fait comparer
  (0,10 ; prise 0,65) et (0,25 ; 0,62 à 0,65) sur 30 générations, avec `ENERGY_SCALE` = 14,5 ÷ médiane brute pour
  chaque configuration, et la saturation à S_MAX jugée sur les 10 % meilleures et le champion. À 0,10, le champion
  plafonne vers +7 m.
- **Retenu :** TORQUE_SCALE = 0,25, prise = 0,62, ENERGY_SCALE = 0,413, START_HEIGHT = 10,3 m (mesuré sur les
  images ; une créature couchée finit à −8,71 m).

**Étape 2 : fitness**
- **3 grilles sans convergence.** Avec c_M ≥ 0,3, l'« attracteur paresseux » gagne : rester accroché ne coûte
  rien, et une créature presque sans muscles (M ≈ 0,5) bat les grimpeuses.
- **Option B écartée par l'utilisateur :** faire coûter les prises. La vidéo montre une immobile à E = 0,5 qui reste
  accrochée, donc la tenue y est presque gratuite aussi.
- **Grille 4 autorisée, après un re-score sans simulation** de 260 populations sauvegardées et l'analyse de la
  contrainte du §9 (à la génération 23, la grimpeuse h 2,3, E 4,9, M 8,0 doit battre l'immobile h −0,1, E 0,5).
  Zone compatible : c_E de 0,40 à 0,45, c_M ≤ 0,10.
- **Retenu : c_E = 0,4, c_M = 0,1**, qui passe sur les 3 graines :
  - champions de la génération 40 à +7,3 / +16,7 / +13,0 m ;
  - muscle au plus bas entre 7,6 et 8,9 ;
  - période au plus haut entre 3,0 et 3,4 s.
- **Audit :** le seuil devient « énergie créée > 5 cm en équivalent hauteur ». Une alerte de 0,77 J, soit 4,3 mm,
  venait de la projection sur une créature tenue par 3 pattes.

**Étape 3 : runs de 200 générations, graines 0, 1 et 2, sans butées** (aujourd'hui `runs/legacy_no_limits/`)
- Colonnes ajoutées à `stats.csv` : `ancestors`, `period_std`, `fallen_frac`.
- Champions : +16,7 m (période 1,02 s), **+37,3 m** (2,03 s), +33,8 m (1,11 s, 75 % de la population entre 30 et
  35 m).
- La période ne chute qu'une fois, vers la génération 10 au lieu de 80 à 85. La graine 1 reste bloquée à 2,0 s.
- **Règle 1** (période > 1,5 s après la génération 100, graine 1) : la mutation de période en échelle log ne
  débloque rien.
  - Vers 2 s, le pas en log (0,20 s) est presque celui du linéaire (0,225 s).
  - La démarche est liée à sa période : rejoué à 1,8 s, le champion tombe de 36,8 à 22,1 m ; de 1,2 à 1,6 s, il
    tombe au sol.
- **Règle 2** (ancêtres < 20) : non déclenchée. La perte d'ancêtres vient d'une innovation (invasion par la
  première lignée qui grimpe), et les records progressent jusqu'aux générations 184 à 189.
- **Validation :** « Ne touche ni à g, ni à S_MAX, ni à la fitness ». Les écarts (génération 0 trop bonne, période
  finale de 1 à 2 s, force au plafond, pas de démarche diagonale) sont mis en liste. Runs de référence : 1 et 2,
  graine 2 par défaut.

### Phase 4 : décor et lézard (4a-1, 4a-2, pas de 4b)

**4a-1 : ciel, tronc, sol, caméra, lézard, replay**
- Rejeu exact (+33,838209355 m). Palette dans ±12 partout.
- Consignes de l'utilisateur :
  - deux points de contrôle ;
  - relevé de palette par médiane de zone avec une tolérance de ±12 (la spec est à ±4) ;
  - cache disque avec un hash de `scene.py` et `--no-cache` ;
  - donner la commande pour vérifier les 60 fps chez lui ;
  - ne pas toucher au squelette.

**Corrections demandées après la 4a-1**
- lézard ×1,4 et queue dessinée à 1,9 × la colonne ;
- `CAMERA_LERP` à 0,12 ;
- repères seulement une fois atteints, puis **transitoires** (0,5 s + fondu de 0,3 s, premier franchissement vers
  le haut, jamais redéclenchés).

**4a-2 : couches 1, 2, 3 et 6**
- Parallaxes mesurées (voir §8.1).
- Canopées irrégulières, silhouettes lointaines arrondies, disques des doigts −30 %, fougères plus grandes.
- 4 écarts de palette [VU] laissés tels quels :

  | Rôle | Référence | Nous (§5.2) |
  |---|---|---|
  | branche | #643B27 | #74442C |
  | facette claire des rochers | #B6763A | #C47C4C |
  | lianes | #647923 | #6C7C14 |
  | doigts | #DAF389 | #D4FC7C |

- Fps tenus avec les canopées à l'écran (mesuré à part, à la demande de l'utilisateur).

**Validation :** « pas de 4b ». Les défauts restants sont notés : arbre latéral plat, queue et pose du lézard.

### Phase 5 : HUD et écrans d'analyse

- **5a, HUD :**
  - voile du carton clair selon l'image 39 (l'utilisateur n'a pas de préférence) ;
  - « pas de repères avec HUD » (choix de l'utilisateur) ;
  - polices téléchargées depuis google/fonts.
- **5b, vue population et histogramme :**
  - grille de 50 × 20 choisie par l'utilisateur ;
  - poses par l'évaluateur batché (export en ≈ 10 s) ;
  - puis, à sa demande, miniatures redressées tête en haut.
- **5c, analyse et comparaison :**
  - mode analyse validé du premier coup ;
  - comparaison corrigée : un seul fantôme semblait visible (même couleur olive sur le tronc, un seul libellé), une
    case de planche noire (6 cases pour 5 instants), une caméra sans zoom qui perdait la génération 0. D'où un
    libellé par fantôme, une opacité croissante, une échelle fixe ajustée (16,6 px/m pour la graine 2) et 6
    instants dans la planche.

### Phase 6 : polish et bilan

- Options exposées partout (`--slow`, `--speed`, `--export-video`). Export MP4. Pas d'écran de fin volcan.
- **Checklist du §11 :** 10 points faits, 2 partiels.
  - **Point 8**, flemme puis paliers : partiel, à cause des écarts de calibration.
  - **Point 11**, vue population, histogramme, courbes : partiel. La grille est en 50 × 20, et les courbes **au
    style vidéo du §7.3** ne sont pas faites (hauteur ÷ 10 superposée, bandes de phases colorées, encarts en verre
    dépoli pendant les replays) : seul le style de calibration à trois panneaux existe. **C'est la seule mise en
    forme de la spec qui manque.**
  - Le reste est fait, avec des écarts de forme pour la scène et le lézard.

### Chantier A : vue population complète et décor en hauteur (rendu seul)

**Point 1 : cycle complet de la vue population**
- Commande `--cycle` (voir §8.4). Deux décisions de l'utilisateur : cadence fixe pour l'apparition, posture de repos
  pour les enfants.

**Point 2 : décor au-dessus de 23 m**
- Seule l'image 08 couvre cette zone, d'où la commande `decor`.
- Deux écarts trouvés, puis corrigés à la demande de l'utilisateur :
  - canopée du premier plan 2,7 m trop basse : `FG_CANOPY_LIFT` passe de 2,6 à 5,3. L'image 09 avait été mal lue en
    phase 4 ;
  - branche de 31 m qui ajoutait une canopée absente de l'image 08 : les branches passent de 31 et 43 m à 46 et
    58 m, en [CHOIX] au-delà de 45 m.
- Au repère de 30 m, le lézard est maintenant caché à 64 % par la canopée, comme dans la vidéo.

**Bug corrigé en route :** `--export` + `--export-video` faisait planter le processus en silence. Une police mise en
cache était réutilisée après `pygame.quit()` ; le cache est maintenant vidé à la fermeture de pygame.

### Chantier B : butées articulaires

**B1 (diagnostic, sur une nouvelle branche)**
- Conventions d'angle anatomique (§15) et cartographie : les 8 articulations à contraindre sont les 8 articulations
  musclées. NECK et PELVIS (plus de 2 os) sont déjà rigides via les `BRACES` ; la queue est hors périmètre.
- Mesures sur 303 grimpes. **Dépassement large :**
  - graine 0 : bras passés devant la tête (épaule jusqu'à +160°) ;
  - graine 1 : fémur en hélice, ≈ 9 tours en 10 s, genou à l'envers 47 % du temps ;
  - graine 2 : fémurs rabattus derrière le bassin (−125°), jambes croisées 62 % du temps ;
  - génération 0 : 44 à 46 % des créatures font un tour complet d'une articulation.
- **Deux causes :**
  - le contrôleur pousse par le côté court (`wrap_angle`), ce qui fabrique les hélices ;
  - la plage des cibles du génome contenait des angles impossibles (3 à 52 % des cibles hors butées).
- **Butées validées telles quelles :** épaule [−60°, +90°], coude [0°, 140°], hanche [−80°, +75°], genou [0°, 140°].
  Les tags sont dans `config.py`.
- **Décisions :** cibles du génome ramenées à la plage articulaire (oui) ; réentraînement des 3 graines avec le
  drapeau `JOINT_LIMITS`, les anciens runs restant rejouables (oui). L'utilisateur exige une vérification des
  hauteurs après réentraînement.

**B2 (implémentation)**
- **Deux ajouts de l'utilisateur :**
  - des tests unitaires sur la contrainte elle-même ;
  - une surveillance des sauts d'énergie à l'engagement des butées, en rapportant les **valeurs réelles** et pas
    seulement le dépassement d'un seuil.
- **Schéma imposé :** celui du contact au sol, sans biais propre.
- **Résultats** (détail dans `docs/chantier_b_b2.md`) :
  - champions de la génération 200 avec butées : **+34,2 / +33,4 / +35,3 m** (sans butées : 16,7 / 37,3 / 33,8 m) ;
    les constantes de la phase 3 se transfèrent ;
  - la graine 2 finit comme la vidéo : période 0,60 s, masse musculaire 10,0 ;
  - la phase flemmarde réapparaît pour les graines 0 et 2 (période à 4,0 et 4,8 s), mais la chute arrive aux
    générations 35 à 40 au lieu de 80 à 85 ;
  - pénétration de 0,000° à la génération 200, et 0,39° au plus à la génération 0 (critère : 0,5°) ;
  - **0 J** créé hors muscles dans 150 × 4 800 sous-pas audités et dans 51 audits de champion ;
  - marge visible : la projection remonte au plus 0,079 J à l'engagement, soit 0,35 mm, 14 fois sous le seuil ;
  - coût de l'évaluation : +45 %.
- **Limite connue, documentée sans réentraîner :**
  - un champion coincé (3 prises et 3 butées) a une erreur de longueur des os de 1,97 % pendant 0,9 s, sans énergie
    créée ;
  - mettre les butées d'abord dans la projection donnerait 0,93 % mais une pénétration de 1,0° (×500) ;
  - 24 passes donneraient 1,27 % ;
  - décision de l'utilisateur : **garder l'ordre liens, butées, sol**.
- **Écrans refaits** sur le run avec butées. Nouveau constat : une **morphologie trapue**. Toute la population de la
  graine 2 a une colonne à 0,62 × la référence (borne basse), un fémur à la borne basse et un demi-bassin à 1,36
  (borne haute à 1,4).
- **Miniatures repliées :** c'est un effet du run et pas du rendu. La queue n'est pas masquée, elle est 32 % plus
  courte, comme la colonne ; le code redonne la 5b au pixel près sur l'ancien run.
- **Temps de rendu :** c'est la machine, pas B2 (ancien et nouveau champion rechronométrés en alternance).
- **Fusion** par avance rapide sur `claude/modest-ritchie-mkwjnd`, puis réorganisation des runs : `runs/butees/S`
  devient `runs/S`, et l'ancien `runs/S` devient `runs/legacy_no_limits/S`. Un test rejoue les deux au bit près,
  chacun avec son drapeau. Une note en tête du §7 de `chantier_b_b2.md` explique ces chemins.

### Chantier C : collisions entre membres

**Point de départ :** le moteur n'a aucune collision entre segments. Les butées de B règlent une articulation seule,
pas les effets combinés : en B2, les pieds du champion de la graine 1 étaient de l'autre côté de l'axe 90 % du
temps.

**C1 (diagnostic, sur une nouvelle branche ; moteur intact)** — détail dans `docs/chantier_c_diagnostic.md`, outil
`joints --crossings`.
- **Mesures** sur 300 grimpes (50 meilleures et 50 au hasard par graine, génération 200) :
  - pieds de l'autre côté de l'axe bassin–cou : graine 0 : 0 % ; graine 1 : 84 % (profond : 0,58 m en médiane,
    pied en l'air) ; graine 2 : 38 % (quelques cm, pied tenu). Toujours derrière le bassin, dans la zone de la
    queue ;
  - croisements jambe/queue : 14 % / 72 % / 50 % du temps ;
  - jambe gauche contre jambe droite : 39 % pour la graine 1 ;
  - bras/jambe du même côté (revérifié avec les nouveaux gaits) : ≤ 0,1 % ;
  - bras, torse, tête, ceintures : ≈ 0.
- **Deux mécanismes :**
  1. le pied passe sous la queue (hanche en butée + genou fléchi) : graine 1 et une partie de la graine 2 ;
  2. la queue, sans contrainte, balaie les jambes : graine 0, où la queue se replie jusqu'à 180°.
- **Pistes**, estimées sur les trajectoires enregistrées (ordre de grandeur, puisque les gaits changeront) :

  | Contrainte | Croisements restants (graines 0 / 1 / 2) |
  |---|---|
  | pied de son côté de l'axe, seul | 100 / 0 / 23 % |
  | + queue dans un cône de ±30° | 0 / 0 / 18 % |
  | + queue dans un cône de ±10° | 0 / 0 / 1 % |
  | + queue dans un cône de ±6° | 0 / 0 / 0 %, mais le cône agirait 99 à 100 % du temps |

  La séparation complète (pied hors du cône de la queue) agirait 96 à 97 % du temps.
- **Verdict validé :**
  - piste (a) étendue à la queue : le pied reste de son côté de l'axe, la queue reste dans un cône ;
  - collision générale rejetée : aucune autre paire ne se croise de façon mesurable, et ≈ 200 paires de contacts
    non lisses apporteraient un risque sans gain mesuré ;
  - séparation complète rejetée ;
  - décision sur le résidu de la graine 2 reportée après le réentraînement de C2.
- **Angle de la queue mesuré sur les images 11, 12 et 40**, à la demande de l'utilisateur au lieu d'un 30° rond :
  écart queue/axe de 1,7°, 5,7° et 3,3°, queue droite (résidu < 1 px). La mesure est nette, d'où
  **`TAIL_CONE_DEG = 6` [DÉDUIT]**. Limites :
  - trois images du même champion ;
  - queue dessinée, que le rendu peut lisser ;
  - grimpe verticale, où la gravité aligne une queue passive.
  Repli à 30° [CHOIX].
- **C2 :** l'utilisateur valide C1 et lance C2, avec un critère de repli objectif (§12).

**Passage sur le PC de l'utilisateur et GitHub Actions (12 octobre 2026).**
- Dépôt reconstruit à partir d'un bundle, puis ménage des branches (§3.4).
- Python 3.11 installé sur le PC.
- Les rejeux divergent sous Windows (§3.5) : l'utilisateur fait passer tous les rejeux, entraînements, mesures et
  écrans par le workflow GitHub Actions, avec ses modes `reproductibilite`, `pytest` et `analyse`.
- Vérifications :
  - le runner rejoue les champions B2 au bit près ;
  - le mode `analyse` redonne les chiffres de C1 à l'identique.

**C2 (exécution, mission en autonomie du 12 au 13 octobre 2026)** — détail dans `docs/chantier_c_c2.md` et
`docs/journal_v1.md`.
- **Moteur** : `limit_joints`, puis les 14 butées du corps derrière `BODY_LIMITS`. B2 se rejoue au bit près.
- **Tests existants adaptés sur décision de l'utilisateur** (moteur inchangé), pour la créature inerte avec les
  butées du corps :
  - elle finit couchée à −7,95 m : la borne de hauteur est alignée sur la plage de la vidéo (−9 à −7,8 m) ;
  - elle crée 4,39 J hors muscles à 6° : seuil propre à ce cas, 6 J ;
  - sa queue s'étire de 9,37 % : seuil propre à ce cas, 10 % ;
  - mécanisme : après la chute, la queue est en butée de cône et posée au sol.
- **Run à 6°** : champions à 38,9 / 33,9 / 48,5 m ; critère de repli « garder 6° » sur les grimpeuses.
- **Repli à 30°**, par la règle de l'utilisateur (repli direct si une troisième mesure tombe à cause du même
  mécanisme). La troisième mesure : 77 à 82 créatures tombées par graine en gén. 0 avec un os de queue au-delà de 5 %
  (B2 : 1 à 6) ; 100 % de ces sous-pas ont la queue en butée et au sol.
- **Run à 30°** (référence C2) :
  - champions à **39,5 / 37,1 / 42,8 m** ;
  - 0 J créé hors muscles chez les champions et les 10 meilleures de 5 générations ;
  - pieds de l'autre côté de l'axe : 0 à 0,1 % (graine 1 en B2 : 84 %) ;
  - jambe/queue : 0 / 6,8 / 7,5 % (B2 : 14 / 72 / 50 %) ;
  - critère « garder 30° ».
- **Constats et décisions de l'utilisateur** :
  - la queue des créatures tombées étirée à l'impact, et la sortie de cône d'un sous-pas en l'air, deviennent des
    **limites connues** ;
  - les bras croisés de la graine 0 rejoignent les écarts connus ;
  - l'énergie créée par les créatures couchées existait déjà en B2 (jusqu'à 6,45 m d'équivalent), jamais mesurée
    jusque-là. Règle relative : C2 fait mieux que B2 (68 cm au plus). Diagnostic et correctif proposé : chantier D
    (bilan).

**Nettoyage (13 octobre 2026, sans changement de comportement).**
- Tags de `config.py`, avec `config_snapshot()` identique.
- Un import inutilisé retiré.
- Versions épinglées dans `requirements.txt`, `.gitignore` complété.
- Docs périmées corrigées, ce document mis à jour, `CLAUDE.md` complété, `README.md` public.
- Chaque commit de code est validé par `pytest` sur le runner, rejeux B2 et C2 compris.

### Chantier D : projection propre (13 et 14 octobre 2026)

Détail : `docs/chantier_d_diagnostic.md`, `docs/chantier_d.md`, journal (étapes 12 à 15).
- **Diagnostic** (lecture seule, variantes substituées le temps de la mesure, `diag-projection` et `trace --variante`) :
  - les 17,7 J de la n°808 avec (a) `vitesse_proj` et les sorties de cône d'un sous-pas viennent de la singularité du
    cône au sommet (un point de queue revenu sur le bassin) ;
  - (b) le report dissipatif supprime l'énergie des créatures couchées (n°868 : 1 292,5 J → 0 J) sans en créer ;
    (a) en crée (n°808), (c) 120 passes n'agit presque pas : (b) retenu ;
  - (d) courbure de queue : supprime la singularité, mais ses butées couplées s'enfoncent (p95 ≈ 1°, max 14,6°) ;
    dernier tour à β = 1° et 2,5°, dans l'ordre actuel ou alterné : β = 2,5° retenu par la règle de l'utilisateur.
- **Étape 3** : drapeaux `CLEAN_PROJECTION`, `TAIL_CURVATURE_LIMITS`, `HAND_LIMITS` dans les trois
  implémentations. Arrêt : avec (d), la créature inerte crée 8,16 J et finit à −7,74 m, hors des seuils validés.
  Décision : (d) écarté (code gardé, drapeau False), cône choisi par la mesure, aucun nouveau seuil.
- **Cône** : 10°, 15° et 30° mesurés ; 15° retenu (§10).
- **Réentraînement** (run 38411711297) : champions 30,9 / 40,9 / 43,6 m ; 0 J créé dans les 63 audits ; tombées :
  0 au-delà de 5 cm ; mains et bras de la graine 0 réglés ; croisement jambe–queue de la graine 2 à 23,4 %, sans
  collision (décision).
- **v1.1** : runs D par défaut (C2 à 30° dans `runs/butees_corps_30/S`), sauvegardés sur `sauvegarde-runs`, `main`
  avancée, tag `v1.1` après `pytest` sur le runner.

---

## 10. Décisions de l'utilisateur, à ne pas remettre en cause

| Sujet | Décision |
|---|---|
| Stabilisation | `BETA = 0`, projection seule (12 passes), y compris pour les butées : jamais de biais de Baumgarte ajouté à une projection |
| Échelle | `BODY_SCALE = 7` [DÉDUIT] |
| Départ | `START_HEIGHT = 10,3` m |
| Calibration | TORQUE_SCALE 0,25, prise 0,62, ENERGY_SCALE 0,413, c_E 0,4, c_M 0,1 ; ne toucher ni à g, ni à S_MAX, ni à la fitness, ni à KP/KD sans accord |
| Coût des prises (option B) | refusé : la tenue est presque gratuite dans la vidéo aussi |
| Énergie | E = Σ\|τ\|·dt (`"torque"`), pas le mode `"power"` |
| Squelette et physique | inchangés pendant les phases de rendu ; la queue physique reste à 1,2 × la colonne, prolongée au dessin |
| Parallaxes | valeurs mesurées sur les images |
| Repères | transitoires, premier franchissement vers le haut, jamais avec le HUD |
| Carton | voile clair (image 39), pas de préférence de l'utilisateur |
| Grille de population | 50 × 20 (image 24) ; miniatures redressées tête en haut |
| Cycle de population | apparition à cadence fixe ; enfants en posture de repos |
| Écran de fin volcan | exclu (identité d'un vrai créateur) |
| Pas de 4b | les défauts restants sont notés, pas corrigés |
| Butées articulaires | valeurs du §3 de B1 ; cibles du génome dans la plage ; drapeau absent = False ; ordre de projection liens, butées, sol conservé malgré le cas à 1,97 % |
| Runs | depuis la v1.1 : `runs/<graine>` = **chantier D** (défaut) ; `runs/butees_corps_30/<graine>` = C2 à 30° (défaut de la v1.0) ; `runs/butees_articulaires/<graine>` = B2 ; `runs/butees_corps/<graine>` = C2 à 6° ; `runs/legacy_no_limits/` = sans butées ; tous sauf legacy sauvegardés sur `sauvegarde-runs` |
| Queue courbée | 30° acceptée pour la v1.0 ; 15° depuis le chantier D ; notée dans les écarts connus |
| `docs/reference/` | laissé tel quel pour l'instant |
| Chantier C | pied de son côté de l'axe + queue dans un cône ; pas de collision générale ; pas de séparation complète |
| Croisement jambe–queue | **pas de collision** (chantier D) : en vue de dessus, une patte qui croise la queue passe au-dessus d'elle ; c'est de la profondeur, pas une interpénétration. Écart connu, avec le temps pied tenu et pied levé (§11) |
| Cône de queue | C2 : 6° [DÉDUIT] au départ, 30° [CHOIX] appliqué (repli direct par la règle « troisième mesure tombée à cause de la queue en butée et au sol ») ; **chantier D : 15° [CHOIX]**, l'angle le plus serré (10°, 15°, 30° mesurés) qui respecte tous les seuils actuels de la créature inerte sans en modifier aucun ; le critère de repli reste le seul juge sur les grimpeuses |
| Reproductibilité | le runner GitHub ubuntu-24.04 fait foi pour tout rejeu, test de rejeu, mesure de run et écran ; versions épinglées ; les captures de la vidéo ne sortent jamais dans les artefacts publics |
| Créature inerte avec butées du corps | hauteur dans la plage de la vidéo, seuils propres à ce cas (énergie < 6 J, queue < 10 %) ; 0,23 J et 8 % partout ailleurs ; **aucun nouveau seuil** pour la queue (chantier D) |
| Créatures tombées | énergie créée jugée **relativement à B2** (arrêt seulement si C2 fait plus du double) ; queue étirée à l'impact et sortie de cône d'un sous-pas en l'air : limites connues, documentées |
| Chantier D (projection propre) | **appliqué** (v1.1) : report dissipatif de la projection (b) ; butées des mains ; cône de 15° ; (a) `vitesse_proj` et (c) 120 passes écartés ; (d) courbure de queue explorée puis écartée (énergie de la créature inerte), code gardé derrière son drapeau (False) |
| Graine 0 du chantier D | champion à 30,9 m (C2 : 39,5 m) : **accepté**, effet attendu de la butée des mains |
| Cap du projet | la v1.1 est sur `main` ; la v2 (duel LLM contre évolution) partira d'elle |

---

## 11. Écarts connus avec la vidéo

État après le chantier D (référence : `runs/S`, graines 0 / 1 / 2 ; valeurs de C2 à 30° entre parenthèses). Ils sont
gardés en liste volontairement, sans y toucher sans accord.

**Calibration et évolution**
- **Génération 0 trop bonne :** la plus haute monte de +4,6 / +3,4 / +3,7 m, alors que la meilleure de la vidéo ne
  grimpe pas (−0,1 m). La piste « baisser la qualité des grimpeuses de génération 0 » (prise, KP/KD) n'a jamais été
  testée.
- **Flemme :** présente (période moyenne max 3,9 / 2,9 / 4,4 s, muscle moyen min 8,6 / 8,1 / 9,4 sur les gén. 1 à 20).
  Mais la chute de période arrive tôt (sous 1,5 s dès les gén. 35 / 24 / 29) au lieu des générations 80 à 85 puis
  140 à 150.
- **Créatures au sol** à la génération 200 : 158 / 87 / 121 (119 / 90 / 84), contre ≈ 30.
- **Hauteurs :** champions à 30,9 / 40,9 / 43,6 m (39,5 / 37,1 / 42,8), vidéo 36 m.
  - **Graine 0 plus basse** (30,9 m) : effet attendu de la butée des mains, **accepté** par l'utilisateur. Sa démarche
    de C2 passait les mains de l'autre côté de l'axe 91 % du temps.
  - Graines 1 et 2 au-dessus de la vidéo. La majorité n'est pas « entre 30 et 35 m » (13 / 31 / 21 créatures). B2
    était conforme sur ce point (720 / 718 / 623).
- **Masse musculaire** trop haute : 14,1 / 16,1 / 15,7 en moyenne (16,4 / 13,5 / 13,8), contre 10,5.
- **Période finale :** 0,81 / 1,05 / 1,33 s en moyenne (0,86 / 1,47 / 0,87), contre 0,6 s.
- **Énergie du champion :** 13,3 / 14,9 / 12,7 (16,4 / 13,3 / 15,6), contre 32,5. Écart lié à la définition de E,
  inchangé depuis la phase 3.
- **Forces du champion** et **démarche diagonale** : non remesurées depuis B2 (forces réparties autrement que dans la
  vidéo ; démarche diagonale partielle).

**Morphologie**
- **Lézard trapu :** mesuré en C2 (`docs/chantier_c_c2.md` §7), non remesuré pour le chantier D.
- **Queue physique courte** (1,2 × la colonne), prolongée au dessin à 1,9 ×.
- **Queue courbée :** elle s'écarte de 15° de l'axe (médiane des 50 meilleures, cône de 15°), contre 25 à 28° avec
  C2 à 30°, et 1,7 à 5,7° sur les images 11, 12 et 40.
- **Croisement jambe–queue en vue de dessus** (`joints --crossings`, 50 meilleures de la gén. 200) :
  - 0 / 0 / 23,4 % du temps (C2 : 0 / 6,8 / 7,5 % ; B2 : 14 / 72 / 50 %). C'est le tibia qui croise la queue ; le cône
    de 15° la garde plus près des jambes ;
  - pendant ces croisements, graine 2 : pied tenu 16,2 % du temps, pied levé 83,8 % (C2 à 30° : 5,2 % et 94,8 % ;
    graine 1 de C2 : 64,7 % et 35,3 %) ;
  - **décision de l'utilisateur : pas de collision.** En vue de dessus, une patte qui croise la queue passe au-dessus
    d'elle : c'est de la profondeur, pas une interpénétration.
- **Bras et mains (graine 0) :** réglés par le chantier D. Mains de l'autre côté de l'axe 0 % (C2 : 91,4 %), bras
  croisés 0 % (C2 : 89,2 %).

**Rendu**
- Canopées de l'arbre latéral plates.
- Quatre couleurs [VU] du §5.2 que la vidéo montre autrement (branche, facette claire des rochers, lianes, doigts).
- Point rouge foncé d'une paume non reproduit (images 11 et 12).
- Courbes au style vidéo du §7.3 non faites.
- Cadrage pendant le carton : la vidéo cadre plus haut à t = 0,5 s (image 39) ; non modifié.
- Créature 1 de la génération 0 différente de celle de la vidéo : ce n'est pas le même run, rien à corriger.
- Écrans non refaits sur les runs du chantier D (les écrans de C2 sont sur `runs/butees_corps_30/2`).

**Limites du moteur**
- Erreur de longueur des os jusqu'à 1,97 % dans une posture sur-contrainte rare, sans énergie créée ; l'alerte
  d'audit reste active.
- **Énergie créée par les créatures couchées : réglée par le chantier D** (report dissipatif). Tombées des vraies
  populations : 0 au-delà de 5 cm, au plus 0,87 cm (C2 : 10 au-delà de 5 cm, jusqu'à 68 cm).
- **Queue des créatures tombées étirée à l'impact** : 0 à 5 créatures par génération au-delà de 5 %, jusqu'à 12,3 %
  (C2 : jusqu'à 43,8 %). Limite connue.
- **Singularité du cône** (un point de queue revenu près du bassin) : sorties de cône d'un sous-pas chez des créatures
  tombées, aucune chez les grimpeuses, 0 J créé (`docs/chantier_d.md` §5).

---

## 12. La phase C2 (faite) et la suite

> **C2 est faite** (`docs/chantier_c_c2.md`). Le plan ci-dessous a été suivi, avec deux changements :
> - l'entraînement et les mesures sont passés sur GitHub Actions (§3.5) ;
> - le cône est passé à 30° par une règle ajoutée par l'utilisateur (§9).
>
> La suite après C2 est au §12.3.

### 12.1 Consigne de l'utilisateur (texte exact)

> C1 validé, TAIL_CONE_DEG = 6 [DÉDUIT] accepté comme point de départ pour C2, avec un critère de repli objectif
> plutôt qu'une impression : mesure l'erreur de longueur des os le long de toute la chaîne de la queue après
> réentraînement (pas juste ponctuellement comme en B2, puisque la contrainte sera quasi permanente) — si elle
> dépasse 1 % de façon systématique, ou si tu observes une oscillation numérique de la queue contre sa butée,
> repasse à 30° [CHOIX] comme prévu dans ton repli. Vérifie aussi visuellement, une fois les écrans refaits, que la
> queue n'a pas l'air raide plutôt que naturellement tenue. Lance C2.

### 12.2 Plan validé (rien n'est codé ; à faire sur une nouvelle branche de chantier partie de `main`)

**Moteur : même primitive que B2, sur d'autres triplets**
- **`physics.py` :**
  - ajouter `World.limit_joints` (Q, 3), les triplets des butées, séparés de `world.joints` (les muscles) ;
  - `set_joint_limits(sign, lo, hi, triplets=None)`, avec par défaut les 8 articulations (comportement de B2) ;
  - `link()`, `project_links()`, la référence Python et `limit_violation()` lisent `limit_joints` au lieu de
    `joints[:Q]` ;
  - aucune opération ne change dans les noyaux. Drapeau désactivé : mêmes triplets, mêmes opérations, donc les runs
    de B2 se rejouent au bit près.
- **`batch.py` :**
  - `pack()` ajoute `lim_joints` (identiques pour toutes les créatures, à vérifier) ;
  - `_simulate_block` et `_simulate_population` le prennent pour leurs trois boucles de butées.
- **`creature.py` :** si `config.BODY_LIMITS`, ajouter à la suite des 8 butées :
  - **pieds** (2 butées) : triplets (NECK, PELVIS, L_FOOT) et (NECK, PELVIS, R_FOOT) ; signes +1 et −1 (le pied
    gauche est à θ > 0) ; bornes u ∈ [m, 180° − m], avec m = `FOOT_AXIS_MARGIN_DEG`. C'est exactement « le pied
    reste de son côté de l'axe bassin–cou » ;
  - **queue** (12 butées) : triplets (NECK, PELVIS, TAIL_k), bornes [180° − τ, 180° + τ]. Au repos, la queue est
    dans l'axe (θ = ±180°), au centre du cône ; le repli sur le cercle gère le passage de +180° à −180° ;
  - ordre dans les passes : liens, butées (articulations, pieds, queue), sol ;
  - `limit_groups()` : quelle butée appartient à quel groupe, pour les mesures.
- **`config.py` :**
  - `BODY_LIMITS = True` [CHOIX] ;
  - `FOOT_AXIS_MARGIN_DEG = 0.0` [CHOIX] ;
  - `TAIL_CONE_DEG = 6.0` [DÉDUIT] images 11, 12, 40 (1,7°, 5,7°, 3,3°), repli 30 [CHOIX] en commentaire ;
  - les seuils du critère de repli.
- **`evolution.py` :** `LEGACY_DEFAULTS` reçoit `"BODY_LIMITS": False`.
- **Audit d'énergie :** rien à ajouter, puisque `limit_active` inclura les nouvelles butées.

**Tests** (`tests/test_body_limits.py`, sur le modèle de `tests/test_joint_limits.py`)
- pied lancé vers l'axe (vraie créature, sans gravité ni sol) : il s'y arrête, pénétration ≤ 0,5°, sans rebond ni
  gain d'énergie ; deux cas, pied libre et pied tenu ;
- queue lancée contre le bord du cône : arrêt à τ, sans rebond ni gain d'énergie, os de la queue < 1 % ;
- scalaire et batché au bit près avec les butées du corps réellement engagées ;
- noyau numba et référence Python identiques avec les 22 butées ;
- départ hors bornes (queue pliée à 40°, pied de l'autre côté) : retour par le côté court, sans NaN ni énergie ;
- aucune énergie créée sur une grimpe aléatoire ;
- drapeau : désactivé, `limit_joints` = `joints` ; un run sans la clé se rejoue sans butées du corps ; un nouveau run
  enregistre `BODY_LIMITS: true` ;
- runs locaux : étendre `test_local_runs_replay_with_their_own_flag` à `runs/butees_corps/<graine>` (True),
  `runs/<graine>` (False) et `runs/legacy_no_limits/<graine>` (False et False) ;
- tests de l'outil de mesure sur des signaux construits.

**Mesures et critère de repli** (`joints --tail`, dans `evo/joint_audit.py`), à chaque sous-pas, sur les 50
meilleures et 50 créatures au hasard de la génération 200 :
- **Erreur de longueur de la queue**, sur chacun des 12 os : max, p95, part du temps au-delà de 1 %, et où dans la
  chaîne.
  - **« Systématique »** = pour au moins une graine, plus de `TAIL_FALLBACK_SHARE` = 10 % [CHOIX] des 50 meilleures
    dépassent 1 % pendant plus de `TAIL_FALLBACK_TIME` = 1 % de leur grimpe (0,1 s cumulée).
  - **Référence mesurée** sans cône, sur les 15 meilleures de chaque graine des runs de B2 :
    - p95 de 0,04 à 0,13 % ;
    - maximum ponctuel de 0,5 à 1,1 % ;
    - grimpes au-delà de 1 % pendant plus de 0,1 s : 0 % sur les 3 graines (au hasard : 20 % pour la graine 1,
      0 % sinon).
- **Oscillation numérique contre la butée :**
  - signal : écart signé δ_k de chaque point de queue à l'axe ;
  - une alternance au sous-pas n, quand les pas δ(n+1) − δ(n) et δ(n) − δ(n−1) sont de signes opposés et dépassent
    tous deux `TAIL_CHATTER_MIN_DEG` = 0,01° [CHOIX] ;
  - comptée seulement pendant le contact, |δ| ≥ τ − 2° ;
  - **oscillation constatée** si l'alternance dépasse `TAIL_CHATTER_MAX` = 10 % [CHOIX] des sous-pas de contact
    chez plus de 10 % des 50 meilleures ;
  - justification : un mouvement physique ne change de sens qu'à ses rebroussements (une queue qui balance à 5 Hz
    alterne sur ≈ 2 % des sous-pas), une oscillation numérique sur près de 100 % ;
  - rapporter aussi l'amplitude des alternances et la même mesure sur les runs de B2.
- **Posture de la queue**, en appui au contrôle visuel : écart à l'axe (médiane, p95), part du temps collée à une
  borne, courbure entre le premier et le dernier point, comparaison avec les images 11, 12 et 40 (écart de 1,7 à
  5,7°, écart latéral de 1,0 à 5,4°).
- **Ligne de verdict :** « critère de repli : … → garder 6° | repli à 30° ».
- **Comme en B2 :** `--crossings` (avant/après de C1), pénétration des 22 butées ≤ 0,5°, erreur des os du corps,
  `--energy`.

**Déroulé**
1. Code (moteur, batché, créature, config, mesures) et tests, puis contrôles avant réentraînement :
   - `pytest` complet ;
   - replay au bit près des runs de B2 et de `legacy_no_limits` ;
   - `benchmark --pop 1000`, comparé aux 7,7 à 8,4 s de B2 ;
   - commit et push.
2. Réentraînement :
   ```
   python main.py train --seed S --generations 200 --pop 1000 --run-dir runs/butees_corps/S --set AUDIT_EVERY=10
   ```
   pour S = 0, 1, 2. Compter ≈ 30 min par graine, en séquence (estimation : +40 à +60 % de temps d'évaluation).
3. Critère de repli (`joints --tail`). S'il se déclenche : `TAIL_CONE_DEG = 30` [CHOIX] dans `config.py`, avec la
   raison mesurée en commentaire ; réentraînement dans `runs/butees_corps_30/S`, en gardant les runs à 6° pour le
   rapport ; puis on reprend ce point.
4. Vérification comme en B2 :
   - hauteurs et scores contre B2 (34,2 / 33,4 / 35,3 m) et la vidéo (36 m) ;
   - statistiques de population et repères du §9 ;
   - `graphs --compare runs/S` ;
   - énergie aux générations 0, 50, 100, 150 et 200 ;
   - erreur des os du corps ;
   - `--crossings` avant/après, y compris le résidu jambe–queue de la graine 2, **présenté à l'utilisateur pour sa
     décision**.
   - Si les champions passent sous ≈ 27 m (−20 %), s'arrêter et rapporter avant les écrans.
5. Écrans refaits sur `runs/butees_corps/2` (ou le run à 30°), même liste qu'en B2 §7, dans
   `out/chantierC/ecrans/` : replay, population 200, cycle 0→1, histogrammes 0, 1 et 200, analyse, comparaison et les
   6 vidéos. **Contrôle visuel de la queue :** regarder les planches et les miniatures, et dire si elle paraît
   tenue ou raide, chiffres de posture à l'appui.
6. Rapport `docs/chantier_c_c2.md`, organisé comme `chantier_b_b2.md`, avec les courbes dans `docs/chantier_c_c2/`.
   Commit, push, **arrêt pour validation** (pas de réorganisation de `runs/`).

### 12.3 Après C2 : gel de la v1, chantier D, v1.1

- **Gel de la v1, fait le 13 octobre 2026**, validé par l'utilisateur :
  - runs C2 à 30° devenus les runs par défaut, sauvegardés sur `sauvegarde-runs` ;
  - `main` avancée en avance rapide ; tag `v1.0` posé après un `pytest` vert sur le runner ;
  - queue courbée à 30° acceptée pour la v1 (écart connu) ; `docs/reference/` laissé tel quel.
- **Chantier D, « projection propre »**, fait les 13 et 14 octobre 2026 et validé par l'utilisateur
  (`docs/chantier_d_diagnostic.md`, `docs/chantier_d.md`, journal étapes 12 à 15) :
  - diagnostic en lecture seule de quatre candidats : (a) `vitesse_proj`, (b) report dissipatif, (c) 120 passes,
    (d) courbure de queue ; (b) retenu ;
  - (d) codé derrière son drapeau puis écarté : la créature inerte crée 8,16 J (seuil validé : 6 J) ;
  - cône de queue choisi par la mesure parmi 10°, 15° et 30° : **15°** (à 10°, la créature inerte glisse au sol de
    5,97 cm, au-delà du seuil de 5 cm) ;
  - butées des mains ; réentraînement des 3 graines : champions 30,9 / 40,9 / 43,6 m, 0 J créé ;
  - runs D devenus les runs par défaut, sauvegardés ; `main` avancée ; tag `v1.1`.
- **Restent ouverts** :
  - les écarts de calibration (§11) : génération 0 trop bonne, chute de période trop précoce, créatures au sol,
    hauteurs, masse musculaire ;
  - les courbes au style vidéo du §7.3, seule mise en forme manquante de la spec ;
  - les écrans, non refaits sur les runs D.
- La v2 : duel LLM contre évolution, à partir de la v1.1.

---

## 13. Pièges techniques et leçons apprises

**Physique et numérique**
- **Biais de Baumgarte + projection de position = énergie créée** quand l'écart dépasse ce que la projection
  résorbe (7,7 J à un impact). Garder `BETA = 0`.
- **`np.arctan2` ≠ `math.atan2`** d'un bit dans ≈ 7 % des cas. Pour l'identité scalaire/batché, n'utiliser que la
  bibliothèque C (`math.atan2`, ce que fait numba).
- **Dynamique chaotique :** un bit change le destin d'une créature. Toute modification du moteur passe derrière un
  drapeau dont l'absence dans `config.json` redonne l'ancien comportement (`LEGACY_DEFAULTS`).
- **L'évaluateur batché doit refaire exactement les mêmes opérations dans le même ordre** que le moteur scalaire :
  ordre d'accumulation des forces, sommation par paires, mêmes fonctions partagées. Toute nouveauté physique doit
  être ajoutée aux trois implémentations (numba scalaire, Python, batché), avec un test d'égalité.
- **Projection restreinte aux butées proches :** les recalculer toutes à chaque passe doublait le coût.
- **Contrôleur et `wrap_angle` :** sans butées, une articulation à plus de 180° de sa cible est poussée par l'autre
  côté et tourne sans fin (hélices de la graine 1).

**Rendu (pygame)**
- `smoothscale` n'est exact que pour les facteurs puissances de 2 : ×3 perd des niveaux de couleur et d'alpha.
- `surface.set_alpha(None)` supprime aussi l'alpha par pixel : utiliser `set_alpha(255)`.
- Encodage RLE : faire un premier blit vers la surface d'affichage au chargement, sinon pic de 45 ms à la première
  frame.
- Après `pygame.quit()`, une `Font` gardée en cache fait planter le processus (code 139) : `fonts.py` vide son cache
  via `pygame.register_quit`.
- `(1−u)**taper` avec u > 1 donne NaN et figeait `pygame.draw.polygon` : borner u et vérifier la finitude avant de
  dessiner.
- Le cache du décor doit être invalidé par le code de `scene.py`, pas seulement par la config.

**Outils et processus**
- **ffmpeg :** stderr dans un fichier temporaire, jamais dans un tube non lu.
- **`--set` :** l'appliquer avant de lire les paramètres qui en dépendent (bug d'`AUDIT_EVERY`).
- **Comptage hors bornes :** une tolérance d'arrondi (1e-6°) est nécessaire. Sans elle, une cible posée pile sur la
  butée (−60,000000000000014°) comptait comme hors bornes.
- **Mesures de répétition du décor :** comparer des détails (changement vertical de couleur) présents dans les deux
  tranches. Les aplats et les structures verticales donnaient de faux positifs.
- **Temps de rendu :** l'hôte du conteneur change. Comparer toujours deux versions en alternance dans la même
  session.
- **Notifications parasites :** une phrase d'interface (« Cette session n'est pas en cours d'exécution… ») est un
  jour apparue au milieu d'un prompt collé. Elle était sans conséquence.
- **Windows ne rejoue pas les runs Linux au bit près** (§3.5). Ne jamais conclure d'un rejeu sous Windows ; une
  créature de génération 0 se rejoue parfois à l'identique, les grimpes plus longues divergent.
- **Une mesure de queue, c'est par point et par sous-pas.** Le minimum d'une marge sur toute la chaîne saute d'un point
  à l'autre. Pour un test de choc, suivre le point qui touche, et prendre comme contact une marge de 1e-8 rad (le
  terme spéculatif pose le point pile sur la borne ; un point qui l'effleure seulement reste à 1e-4).
- **Ne pas juger le repli sur les seules grimpeuses :** les créatures tombées et tirées au hasard ont montré à 6° ce
  que les 50 meilleures ne montraient pas (queue en butée et au sol, sorties de cône d'un sous-pas).
- **PowerShell 5.1** supprime les arguments vides (`""`) passés à un exécutable : une légende vide se passe sous la
  forme `" "`. `&&` n'existe pas : enchaîner avec `;` et `if ($?)`.
- **git dans une session non interactive** : il ne peut pas demander d'identifiants. Le premier push se fait depuis
  le terminal de l'utilisateur (Git Credential Manager garde ensuite l'accès).
- **`workflow_dispatch`** n'apparaît que si le fichier est sur la branche par défaut. Lancé avec `--ref <branche>`,
  il exécute la version du workflow de cette branche. Les entrées de type texte ne gardent pas les guillemets :
  `commandes` est découpée sans shell.

---

## 14. Tests

`pytest -q tests/` : 185 tests, cas paramétrés compris ; ≈ 4 à 6 min. Avec ffmpeg (ou `imageio-ffmpeg`) pour les
tests vidéo, sinon 2 sont sautés. Sur le runner (`mode=pytest`), tout passe. Sous Windows, les 3 cas de
`test_local_runs_replay_with_their_own_flag` échouent, et c'est attendu (§3.5).

| Fichier | Tests | Ce qui est vérifié |
|---|---|---|
| `test_physics.py` | 22 | mouvement, gravité (erreur d'ordre 1), prise, liens rigides contre ressort, quantité de mouvement, pendule simple, convergence des itérations, Contract (3ᵉ loi de Newton, travail → énergie cinétique), masses de l'image 20, topologie, numba = Python, stabilisation sans énergie injectée, pendule humain |
| `test_creature.py` | 28 | sol (sans pénétration ni rebond, distance de Coulomb), prises sur la bande du tronc, chute, créature inerte (−9 ≤ h ≤ −7,8 ; seuils propres au cas inerte avec `BODY_LIMITS`), muscles et leurs actions, contrôleur PD et horloge, énergie, génome, fitness, marche écrite à la main, audit d'énergie, replay |
| `test_batch.py` | 4 | batché = scalaire au bit près |
| `test_evolution.py` | 7 | mutations (bornes, symétrie, taux, grosses mutations, mode log), sélection sans réévaluation, run déterministe, reprise et rejeu, audit du champion, cadence d'audit passée en `--set` |
| `test_render.py` | 9 | décor, couches, canopée qui masque le lézard, repères transitoires, canopées irrégulières, queue dessinée au-dessus du sol, caméra, cache du décor, lézard |
| `test_hud.py` | 7 | polices versionnées et repli, formats et durée du carton, disposition, énergie rejouée = énergie du run, étiquette visible sous une canopée, repères seulement sans HUD, polices après `pygame.quit` |
| `test_population.py` | 10 | 1000 cases distinctes, tri (meilleure en premier), animation, poses batchées, redressement, histogramme (somme, bornes), cycle (lignée des enfants, chronologie, transparence) |
| `test_analysis.py` | 7 | 16 muscles dimensionnés par leur force, sens des fuseaux vérifié par la physique, couleurs et libellés, vue d'analyse, comparaison (même instant, caméra, échelle ajustée, libellés) |
| `test_video.py` | 4 | avancement identique à la fenêtre, repli PNG sans ffmpeg, toutes les images dans le MP4, échec de ffmpeg signalé |
| `test_decor.py` | 3 | répétition, repères, canopée |
| `test_joint_audit.py` | 13 | conventions d'angle, miroir, tours, croisements (dont jambe sur la queue, pied tenu ou levé), axe, cône de queue, audit d'un petit run |
| `test_joint_limits.py` | 19 | butées : arrêt pile, sans rebond ni énergie, batché = scalaire, départ hors bornes, drapeau, runs locaux (D, C2 à 30° et à 6°, B2, legacy, chacun avec ses drapeaux) ; moteur de la v1 (drapeaux du chantier D à False) |
| `test_body_limits.py` | 15 | butées du corps (C2) : disposition et repos, pied libre ou tenu arrêté sur l'axe, queue lancée contre le cône (2, 5, 10 m/s) sans rebond ni énergie, départ hors bornes, batché = scalaire et numba = Python avec les 22 butées, énergie sur deux grimpes, drapeau et `config.json` ; verts à 6° comme à 30° ; moteur de C2 (drapeaux du chantier D à False) |
| `test_chantier_d.py` | 23 | moteur D : disposition des 24 butées, report dissipatif (ne crée jamais d'énergie cinétique), numba = Python, batché = scalaire au bit près avec pied, main et queue engagés, main lancée vers l'axe, queue contre le cône, départ hors bornes, énergie sur trois grimpes (seuils de la créature inerte inchangés), créatures du diagnostic, drapeaux ; courbure (écartée) : disposition et bit près |
| `test_tail_audit.py` | 14 | outils de C2 sur signaux construits et petit run : oscillation, étirement, pénétration et posture de la queue, verdict de repli, `--tail`, `--fallen`, `trace`, `diag-projection` (moteur rendu intact), `morpho`, `planche`, variantes du diagnostic du chantier D |

`test_local_runs_replay_with_their_own_flag` saute les runs locaux absents (clone neuf, ou runs C2 non extraits).

---

## 15. Glossaire et conventions d'angle

- **h** : sous-pas (1/480 s). **frame** : 1/60 s (8 sous-pas).
- **θ** : angle signé moteur de rA = A−P vers rB = B−P, dans ]−π, π] (`World.joint_angles`).
- **φ** : angle du contrôleur, 0 au repos, + dans le sens du muscle « + » (`Creature.joint_phi`).
- **u** : signe·θ, la variable bornée par une butée. **C** : distance à la borne la plus proche (> 0 dans la plage).
- **Angles anatomiques** (B1, vue de dessus, gauche et droite en miroir) :
  - épaule et hanche, **α** : angle de l'humérus (du fémur) depuis l'axe latéral, c'est-à-dire le prolongement de
    la clavicule (du demi-bassin). + = protraction, vers la tête ; − = rétraction ; ±90° = os parallèle à la
    colonne ;
  - coude et genou, **β** : flexion, 0 = tendu, + = pli naturel (avant-bras tourné vers la tête, tibia vers la
    queue), − = pli à l'envers ;
  - liens avec φ, vérifiés à 1e-9° près : α épaule = φ + 45°, β coude = φ + 35°, α hanche = φ − 45°,
    β genou = φ + 35°.
- **Axe du corps** (C1) : droite PELVIS→NECK prolongée. Zones le long de l'axe : queue (derrière le bassin), torse,
  tête (devant le cou).
- **Cône de queue** : angle de chaque point de queue vu du bassin, depuis le prolongement de la colonne vers
  l'arrière.
- **Hauteur HUD** : hauteur du centre du torse depuis le départ (le score de hauteur).
- **Graine** : graine du run. Les générations utilisent `default_rng([graine, génération])`.
- **Champion** : rang 1 au score d'une génération.

---

## 16. Images de référence (`docs/reference/`)

| N° | Sujet | Instant |
|---|---|---|
| 01 | scène jungle au départ | 8:02 |
| 02 | gros plan du lézard | 7:54 |
| 03 | HUD, génération 0, créature 1 | 10:20 |
| 04 | génération 0, créature au sol | 10:40 |
| 05 | HUD, génération 23, classement 1 | 13:10 |
| 06 | repère de hauteur 10 m | 13:55 |
| 07 | carton génération 148 | 14:12 |
| 08 | repère 30 m, canopée du premier plan | 14:26 |
| 09 | HUD, génération 200, champion | 14:34 |
| 10 | génération 200, la pire (#1000) | 15:52 |
| 11 | analyse, gros plan des muscles | 16:15 |
| 12 | analyse, pourcentage de la hanche | 16:35 |
| 13 | structure, noms des os | 6:12 |
| 14 | structure, noms des muscles | 6:38 |
| 15 | debug physique, grille | 6:52 |
| 16 | debug créature | 7:12 |
| 17 | debug, chaîne de la queue | 7:30 |
| 18 | horloge et poses | 7:05 |
| 19 | slide « Moteur physique » | 4:42 |
| 20 | schéma des masses (demi-longueurs) | 4:50 |
| 21 | schéma de la contraction (Newton) | 4:32 |
| 22 | schéma des liens à 3 points | 3:35 |
| 23 | schéma d'un membre | 2:25 |
| 24 | population, grille (nommée « 40x25 », en réalité 50 × 20) | 10:49 |
| 25 | population, élimination | 11:20 |
| 26 | histogramme, génération 0 | 11:12 |
| 27 | histogramme, génération 1 | 11:45 |
| 28 | histogramme, génération 200 (pris en pleine animation) | 15:45 |
| 29 | graphe horloge (cyan) et distance (vert) | 15:00 |
| 30 | graphe de la masse musculaire | 15:30 |
| 31 | replay avec graphes incrustés en verre dépoli | 13:30 |
| 32 | replay, masse musculaire | 12:07 |
| 33 | slide récapitulative de la sélection | 9:35 |
| 34 | slide des mutations | 9:20 |
| 35 | slide de la mutation flemmarde | 12:30 |
| 36 | silhouettes du décor (Illustrator) | 7:51 |
| 37 | comparaison de générations | 16:48 |
| 38 | écran de fin, palette volcan | 17:48 |
| 39 | carton génération 0 | 10:14 |
| 40 | champion en zoom, bords du décor | 16:42 |
