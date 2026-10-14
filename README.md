# Gecko : l'évolution de créatures qui grimpent

Gecko (ex-EVO) reproduit, en Python, la simulation de la vidéo YouTube de **Code BH**
[« J'ai codé l'évolution de créatures qui grimpent »](https://www.youtube.com/watch?v=PiWgzThhF9M) (2025).

> Le projet s'appelait **EVO** jusqu'au 14 octobre 2026 (dépôt `tom-security/EVO`, devenu
> [`tom-security/Gecko`](https://github.com/tom-security/Gecko)). Le paquet Python garde son nom, `evo/` : les
> `config.json` des runs en dépendent. Les rapports écrits avant le renommage parlent d'EVO.

**L'idée, la mise en scène et le style visuel sont de Code BH.** Ce dépôt en est une reconstruction indépendante,
écrite à partir de ce que la vidéo montre et explique. Code BH n'a publié ni son code ni ses constantes. Tout ce qui
n'est pas visible dans la vidéo est déduit ou choisi ici, et signalé comme tel dans `config.py` ([VU], [DÉDUIT],
[CHOIX]). Pour découvrir le projet d'origine, regardez sa vidéo.

## Ce que fait Gecko

- **Moteur physique 2D maison** :
  - points, gravité, prises sur le mur ;
  - liens rigides par correction de vitesse itérée (Gauss-Seidel) ;
  - contraction des muscles par couples de forces de somme nulle ;
  - sol avec frottement ;
  - butées articulaires, et butées du corps (pieds et mains de leur côté de l'axe, queue dans un cône) ;
  - projection de position dont la correction est reportée sur la vitesse sans jamais créer d'énergie.
- **Lézards** de squelette imposé : 14 points, 13 os, une tête, une queue, 16 muscles, pilotés par une horloge et
  quatre poses.
- **Algorithme évolutif** : 1 000 créatures, 10 s chacune ; les 500 meilleures ont chacune un enfant muté ;
  200 générations. L'évaluation de toute une population est compilée avec numba.
- **Rendu** :
  - jungle low-poly, HUD ;
  - vue de la population, tri animé, histogrammes, courbes ;
  - mode analyse des muscles, comparaison de générations ;
  - export vidéo.

Le code, les commentaires et les documents sont en français.

## Installation

Python 3.11 :

```
git clone https://github.com/tom-security/Gecko.git
cd Gecko
python -m venv .venv
.venv\Scripts\activate          # Windows (Linux, macOS : source .venv/bin/activate)
pip install -r requirements.txt
pip install imageio-ffmpeg      # exports MP4, si ffmpeg n'est pas dans le PATH
python -m pytest -q tests/
```

## Commandes principales

Tout passe par `python main.py <commande>` ; `python main.py <commande> --help` donne les options.

```
python main.py debug-physics                     # bancs d'essai du moteur
python main.py debug-creature                    # créature en vue debug
python main.py benchmark --pop 1000              # temps d'évaluation d'une génération
python main.py train --seed 0 --generations 200 --pop 1000     # évolution (reprend un run existant)
python main.py graphs --seed 0                   # courbes et histogrammes d'un run
python main.py population --seed 2 --gen 200     # vue de la population, tri animé
python main.py replay --seed 2 --gen 200 --rank 1                # le champion dans la jungle
python main.py analyze --seed 2 --gen 200 --rank 1 --slow        # muscles et forces
python main.py compare --seed 2 --gens 0 23 100 200              # fantômes de plusieurs générations
python main.py replay --seed 2 --gen 200 --rank 1 --export-video out/replay.mp4
python main.py joints --seed 2 --gen 200 --top 50 --crossings --tail    # angles, croisements, queue
```

Outils du duel de la v2 (`docs/SPEC_V2_GECKO.md`) :

```
python main.py genome --schema                   # format du génome JSON, bornes, conventions
python main.py essai genome.json --manche 2 --partie duel/m2/P1 --hypothese "…"   # un essai, son rapport
python main.py verifier-partie duel/m2/P1        # rejeu officiel d'une partie (sur le runner)
python main.py replay --seed 2 --gen 200 --rank 1 --export-etats out/etats/champion.json   # états pour le rendu
```

Les runs (`runs/`), les exports (`out/`) et le cache du décor (`cache/`) restent hors git. Un run de 200 générations
prend de 15 à 60 minutes selon la machine.

## Reproductibilité

La dynamique est chaotique : un écart d'un bit sur un angle change le destin d'une créature. Un run se rejoue donc
au bit près **sur la machine où il a été entraîné** :
- **Linux** : runner GitHub ubuntu-24.04, Python 3.11 et les versions épinglées dans `requirements.txt` ;
- **sous Windows**, la bibliothèque mathématique diffère : les rejeux de runs Linux s'écartent de quelques millimètres
  à quelques dizaines de centimètres.

Les entraînements, les rejeux vérifiés, les tests de rejeu et les mesures passent donc par le workflow GitHub Actions
`.github/workflows/train.yml`, lancé à la main. Ses modes : `train`, `reproductibilite`, `pytest` et `analyse`.

## Documents

- `docs/CODEBH_GRIMPE_SPEC.md` : la description détaillée de la vidéo, point de départ du projet ;
- `docs/PASSATION.md` : l'état du projet de A à Z, les décisions et les règles de travail ;
- `docs/BILAN_V1.md` : le bilan de la v1, les écarts restants avec la vidéo et la suite ;
- `docs/SPEC_V2_GECKO.md` : la spécification de la v2, le duel LLM contre évolution ;
- `docs/chantier_*.md` : les rapports de chaque chantier (butées articulaires, butées du corps, projection propre).

## Licences

- Les polices Questrial et Nunito Sans sont sous licence SIL Open Font License (`assets/fonts/`).
- Les captures de la vidéo de Code BH présentes dans `docs/reference/` lui appartiennent. Elles ont servi de
  référence de mesure pendant le développement.
