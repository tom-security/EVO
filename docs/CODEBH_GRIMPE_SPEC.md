# SPEC COMPLÈTE : reproduire « J'ai codé l'évolution de créatures qui grimpent » (Code BH)

> **Pour Claude Code.** Ce document décrit de façon exhaustive la simulation de la vidéo YouTube de Code BH
> (https://www.youtube.com/watch?v=PiWgzThhF9M, 17:58, publiée le 4 oct. 2025), pour la reproduire à l'identique :
> moteur physique, créatures, algorithme évolutif, rendu, HUD, graphes, résultats attendus.
>
> Sources : transcription intégrale de la vidéo + analyse image par image (~70 frames) + couleurs mesurées
> pixel par pixel sur les frames 1280×720 (quantification ±4 sur chaque canal).
>
> **Légende de fiabilité, à respecter :**
> - **[VU]** : dit explicitement dans la vidéo ou visible à l'écran. À reproduire tel quel.
> - **[DÉDUIT]** : pas montré explicitement, mais cohérent avec ce qui est montré (valeurs du HUD, graphes...). Point de départ raisonnable.
> - **[CHOIX]** : non montré ; choix d'implémentation proposé. Claude Code peut adapter, mais doit le signaler.
>
> Code BH ne montre **pas** son code source et ne donne **pas** ses constantes exactes. Tout ce qui est [DÉDUIT]/[CHOIX]
> doit être exposé dans un fichier de config pour qu'on puisse calibrer contre les résultats de référence (section 9).

---

## 0. Vue d'ensemble

Le programme a 3 couches, construites dans cet ordre [VU] (slide « Plan du code » = pyramide à 3 étages) :

1. **Moteur physique** (base) : points, gravité, fixation, liens rigides, contractions, masses.
2. **Créatures** : squelette de lézard fixe + muscles + contrôleur à horloge et poses cibles.
3. **Sélection naturelle** : population de 1000, simulation de 10 s, sélection des 500 meilleures, reproduction asexuée avec mutations.

Vue caméra [VU] : **vue de face sur un tronc d'arbre vertical**. Le lézard est vu **de dessus/de dos** (comme un gecko sur un mur),
la gravité tire **vers le bas de l'écran**. La simulation est donc **2D dans le plan du mur**. Il n'y a pas de profondeur :
le lézard est toujours plaqué contre le tronc, et il ne tient que par les pattes qu'il « fixe ».

Stack cible [CHOIX] : **Python 3.11+, numpy, numba (fortement recommandé), pygame** pour le rendu, **matplotlib** optionnel
pour exporter les graphes (mais les graphes à l'écran doivent être dessinés en pygame dans le style décrit en §7).
Le moteur physique est **fait maison** [VU], pas de pymunk/Box2D : sa méthode de résolution des liens fait partie de la vidéo.

---

## 1. Moteur physique [VU sauf mention]

### 1.1 Point
- Un point = position `(x, y)` + vitesse `(vx, vy)` + masse `m` + booléen `held` (fixé au mur).
- Intégration en deux étapes à chaque pas [VU] :
  1. On décide de la vitesse (forces → vitesse).
  2. On ajoute la vitesse à la position.
- Sans force, la vitesse est constante et le point va en ligne droite [VU].
- Schéma = **Euler semi-implicite** (vitesse d'abord, position ensuite).

### 1.2 Gravité `Gravity()`
- À chaque pas, on ajoute `g·dt` à la composante verticale de la vitesse, vers le bas [VU].
- `g = 9.81 m/s²` [CHOIX] (l'unité est le mètre, puisque le HUD affiche des « m »).

### 1.3 Fixation `Hold()`
- Fixer un point = **mettre sa vitesse à zéro** (et la garder à zéro) tant qu'il est fixé [VU]. C'est ce qui permet de s'accrocher au mur.
- Implémentation [CHOIX] : un point fixé a une **masse inverse = 0** pour le solveur de liens (masse infinie). Sa vitesse est forcée à 0 avant et après la résolution.
- Seules les **4 extrémités des pattes** (mains/pieds) peuvent être fixées [VU].
- Fixer n'est possible que si le point est sur le mur (sur le tronc) [DÉDUIT]. Au sol, une créature tombée reste au sol.

### 1.4 Liens rigides `Link()`, le cœur du moteur
Code BH explique **pourquoi il n'utilise PAS de ressorts** [VU] :
- Méthode naïve (utilisée dans sa vidéo « créatures aquatiques ») : si deux points liés s'éloignent trop, on applique une force pour les rapprocher (et inversement). Problème : la correction arrive *après* l'écart, donc le lien est **élastique** (visible au ralenti). Dans l'eau c'est OK (frottements élevés, peu de grosses forces). En grimpe, un bras élastique qui s'allonge quand on tire dessus, c'est inacceptable.

Méthode retenue [VU] :
1. **Corriger les vitesses AVANT que les points s'éloignent.** Pour chaque lien, on regarde la vitesse relative des deux points le long de l'axe du lien, et on applique des impulsions opposées pour l'annuler (on « aligne leurs vitesses »). Suffisant pour 2 points.
2. **À partir de 3 points**, corriger le lien B fausse le lien A qu'on vient de corriger. Solution : **répéter la passe sur tous les liens plusieurs fois**. Chaque passe réduit fortement l'erreur, jusqu'à ce qu'elle devienne négligeable.
3. Justification donnée : chaque passe est l'application d'une même fonction de ℝⁿ dans ℝⁿ, **lipschitzienne et contractante** sur un domaine, donc les itérations successives convergent vers la solution physique qui respecte la longueur constante de tous les liens. À partir de 3 points il n'existe pas de solution exacte en général, d'où l'approximation itérative.

→ C'est un **solveur à impulsions séquentielles / Gauss-Seidel au niveau des vitesses**. Implémentation exacte [CHOIX] :

```
pour chaque pas de temps dt :
    # 1. forces externes -> vitesses
    v += g * dt                                  (points non fixés)
    v += F_muscles / m * dt                      (voir 1.5)
    v[held] = 0

    # 2. résolution des liens (N_ITER passes)
    répéter N_ITER fois (ex. 20 à 40) :
        pour chaque lien (i, j, L0) :
            d   = p_j - p_i ; dist = |d| ; n = d / dist
            vrel = dot(v_j - v_i, n)
            # terme de stabilisation (Baumgarte) pour tuer la dérive de position :
            C    = dist - L0
            bias = BETA * C / dt                 (BETA ≈ 0.1 à 0.2)
            w    = w_i + w_j                     (w = 1/m, 0 si fixé)
            si w == 0 : continuer
            lambda = -(vrel + bias) / w
            v_i -= lambda * w_i * n
            v_j += lambda * w_j * n

    # 3. intégration position
    p += v * dt

    # 4. (optionnel mais recommandé) projection de position : 1 à 3 passes qui
    #    corrigent directement p pour ramener chaque lien à L0 (pondéré par w).
```

- Pas de temps [CHOIX] : `dt = 1/60 s` avec **4 à 8 sous-pas** (donc dt_physique = 1/240 à 1/480 s). Simulation de **10 s** par créature [VU].
- **Critère de validation** : au ralenti, aucune élasticité visible. L'erreur relative de longueur doit rester < 1 % même quand toute la créature pend par une seule main.

### 1.5 Contraction d'articulation `Contract()`
- Une articulation = 3 points (A – pivot P – B), c'est-à-dire deux os qui se rejoignent. Contracter = appliquer une petite force qui ferme ou ouvre l'angle [VU].
- On respecte la **3ᵉ loi de Newton** : la somme des forces est nulle [VU]. Sur le schéma (t = 4:32), le pivot est poussé d'un côté et les deux extrémités de l'autre, vers l'intérieur.
- Implémentation [CHOIX] : pour un couple τ :
  - Sur A : force perpendiculaire à (A−P), de norme τ/|A−P|.
  - Sur B : force perpendiculaire à (B−P), de norme τ/|B−P|, en sens de rotation opposé.
  - Sur P : `-(F_A + F_B)`, pour que la somme soit nulle.
- Chaque articulation a sa propre force max. **Elle peut être forte dans un sens et faible dans l'autre** [VU] : deux paramètres par articulation, `S_plus` (fermeture) et `S_minus` (ouverture). Chaque sens correspond à un muscle nommé (voir §2.3).

### 1.6 Longueurs et masses
- Les liens peuvent avoir des longueurs différentes [VU].
- **La masse de chaque point dépend des liens auxquels il est attaché**, pour que les membres longs soient plus lourds [VU].
- Règle exacte, lue sur le schéma (t ≈ 4:50) [VU] : **masse d'un point = somme des demi-longueurs des os qui y sont attachés.** Exemple montré : un point relié à un os de 3.0 (moitié 1.5) et à un os de 1.0 (moitié 0.5) a une masse de 2.0. Un point relié à un os de 3.0 et à un os de 2.0 a une masse de 2.5. Une extrémité reliée à un seul os de 1.0 a une masse de 0.5.
- Le schéma colore chaque demi-os de la couleur du point qui « porte » cette moitié.

### 1.7 Sol et mur [DÉDUIT]
- **Mur** : le tronc, une bande verticale au centre de l'écran. Les points non fixés glissent librement dessus : aucune friction en plan, puisqu'on est en vue de face.
- **Sol** : une ligne horizontale en bas. Les points ne passent pas en dessous (collision + friction forte). Une créature qui tombe finit « couchée par terre ».
- Hauteur de départ : la créature commence **≈ 8 m au-dessus du sol** [DÉDUIT]. Une créature au sol affiche entre −7.8 m et −9 m, et l'histogramme commence à −10.
- Score de hauteur = **déplacement vertical d'un point de référence** (centre du torse / centre de masse [CHOIX]) par rapport à sa position initiale. Il vaut −0.1 m à t = 0.5 s pour une créature qui s'est à peine affaissée.

### 1.8 Récap des fonctions (slide t ≈ 4:40) [VU]
`Movement();  Gravity();  Hold();  Link();  Contract();` plus la gestion des longueurs et masses.

---

## 2. La créature

### 2.1 Pourquoi une structure imposée [VU]
Les créatures aquatiques du vivant ont des formes très variées (beaucoup de stratégies valides). Chez les grimpeurs,
presque tout le monde a la même structure, quelle que soit l'échelle : **un tronc et des pattes**. Grimper est donc beaucoup plus contraint.
→ On **impose la topologie**. Seuls évoluent le **comportement**, la **force des muscles** et la **longueur des os**.

### 2.2 Squelette [VU] (schéma « Structure », t ≈ 6:00–6:15)
Vue de face, symétrique :

```
            (L_hand)                       (R_hand)
                \                           /
          avant-bras (radius-cubitus)   avant-bras
                  \                       /
                (L_elbow)            (R_elbow)
                    \                   /
                   humérus          humérus
                      \               /
              (L_sh)--clavicule--(NECK)--clavicule--(R_sh)
                                   |
                           colonne vertébrale
                                   |
              (L_hip)---bassin---(PELVIS)---bassin---(R_hip)
                      /                       \
                    fémur                    fémur
                    /                           \
               (L_knee)                      (R_knee)
                  /                               \
              tibia-péroné                   tibia-péroné
                /                                   \
           (L_foot)                               (R_foot)
```

- **Points** (14) : NECK, L/R_shoulder, L/R_elbow, L/R_hand, PELVIS, L/R_hip, L/R_knee, L/R_foot.
- **Os** (13) : colonne (NECK–PELVIS), 2 clavicules, 2 humérus, 2 avant-bras, 2 demi-bassins, 2 fémurs, 2 tibias.
- Les clavicules et le bassin sont de « petits segments pour gagner en largeur » [VU].
- **Rigidité des ceintures** [CHOIX] : les angles colonne/clavicule et colonne/bassin sont rigides. Ajouter des liens diagonaux invisibles (par ex. L_sh–R_sh, L_sh–PELVIS, R_sh–PELVIS, et l'équivalent au bassin), ou bien des articulations très raides non musclées.
- **Tête** [VU visuel] : au-dessus de NECK (vers le haut de l'écran), purement visuelle, portée par un point supplémentaire HEAD relié rigidement à NECK et aux épaules [CHOIX].
- **Queue** [VU] : ajoutée « pour qu'elle ressemble moins à un humain et plus à un lézard ». Sur la vue debug, c'est une **chaîne de petits points** qui part du PELVIS et pend/traîne de façon passive (t ≈ 7:25). [CHOIX] : 10 à 14 segments, masse faible, pas de muscles, longueur totale ≈ 1.2 × la colonne. **Exclure la queue du calcul de masse musculaire.**
- Orientation au repos : bras levés vers le haut et l'extérieur, jambes vers le bas et l'extérieur (posture de gecko sur un mur).

### 2.3 Muscles = articulations actionnées [VU] (analogie anatomique montrée à t ≈ 6:28)
4 articulations par côté × 2 sens = **8 muscles nommés par côté** :

| Articulation | Sens « + » (muscle) | Sens « − » (muscle) |
|---|---|---|
| Épaule (clavicule–humérus) | **Deltoïde** (lève le bras) | **Grand dorsal** (tire le bras vers le bas / le corps vers le haut) |
| Coude (humérus–avant-bras) | **Biceps** (flexion) | **Triceps** (extension) |
| Hanche (bassin–fémur) | **Fléchisseurs de hanche** (lèvent la jambe) | **Fessiers** (poussent la jambe vers l'arrière, portent le poids) |
| Genou (fémur–tibia) | **Ischios** (flexion) | **Quadriceps** (extension) |

- Chaque muscle a une **force max propre** qui évolue [VU]. La force est plafonnée : il existe une « force maximale que permet le programme » [VU], et on affiche la force évoluée en % de ce plafond.
- **Symétrie gauche/droite des forces et longueurs** [DÉDUIT] : l'analyse finale donne une seule valeur par muscle (« deltoïde 22 % »). Proposer un flag config `SYMMETRIC_MORPHOLOGY = True`.
- **Masse musculaire totale** = somme des forces max de tous les muscles [DÉDUIT]. Échelle du graphe : axe 0–25. Valeurs observées : ≈ 13 en génération 0, 7.1 à 14.2 selon les individus.
  - Calibration [CHOIX] : 16 muscles (8 × 2 côtés), force max de chacun tirée uniformément dans [0, 1.6] à la génération 0 → moyenne ≈ 12.8 ≈ 13.2 observé. Plafond par muscle `S_MAX = 1.6` (unités internes converties en couple par un facteur `TORQUE_SCALE` à calibrer).

### 2.4 Contrôleur : horloge + poses cibles [VU]
- Chaque créature a une **horloge interne** qui tourne à une certaine vitesse [VU]. Le HUD affiche la **période** de l'horloge en secondes : 1.3 s, 4.2 s, 4.4 s, 1.9 s en génération 0 ; 4.9 s en génération 23 ; **0.6 s** en génération 200.
  - Init [DÉDUIT] : période uniforme dans [0.5 s, 5.0 s] (moyenne génération 0 ≈ 2.9 s sur le graphe). Borne basse [CHOIX] : 0.3 s.
- Chaque créature a une **liste de positions (poses) qu'elle cherche à atteindre, une par intervalle de temps** du cycle [VU].
- **Chaque pose inclut aussi le choix de tenir ou non le mur avec chaque patte** [VU] : 4 booléens.
- La créature **calcule seule quels muscles contracter** pour atteindre la pose [VU].
  - Implémentation [CHOIX] : contrôleur PD par articulation.
    `τ = clamp( Kp·(θ_cible − θ) − Kd·ω , −S_minus , +S_plus )`
    Ici `S_plus` et `S_minus` sont les forces max évoluées des deux muscles antagonistes. Le clamp asymétrique est ce qui rend la force du muscle significative.
  - `θ` = angle signé à l'articulation (mesuré de façon miroir à gauche et à droite pour que les poses soient comparables).
- Nombre de poses par cycle [CHOIX] : **K = 4** par défaut (configurable 3–8). Phase = `(t mod T) / T`, pose courante = `floor(phase·K)`.
  - Transition [CHOIX] : la cible d'angle change instantanément (le PD lisse le mouvement). Le flag hold s'applique au début de l'intervalle.
- Au changement de pose, une patte qui passe à « tenir » est fixée **à sa position courante**. Une patte qui passe à « lâcher » est libérée.

### 2.5 Génome [VU pour la liste des variables]
« Chaque créature est entièrement définie par **ses dimensions, ses muscles, sa vitesse d'horloge et sa liste de positions** » :
- **Longueurs d'os** : colonne, clavicule, humérus, avant-bras, demi-bassin, fémur, tibia (7 valeurs si symétrique).
- **Forces musculaires** : 8 valeurs si symétrique (ou 16).
- **Période d'horloge** : 1 valeur.
- **Poses** : K × (8 angles cibles [4 articulations × 2 côtés] + 4 booléens hold).

Plages d'init [CHOIX] : longueurs de référence (en m) : colonne 0.45, clavicule 0.12, humérus 0.22, avant-bras 0.20, demi-bassin 0.10, fémur 0.24, tibia 0.20, chacune ×[0.6, 1.4]. Angles cibles uniformes dans la plage articulaire (par ex. ±90° autour du repos). Hold aléatoire p = 0.5.

---

## 3. Sélection naturelle [VU]

### 3.1 Boucle
1. Génération 0 : **1000 créatures aléatoires**.
2. Chacune est **simulée 10 s**, indépendamment (pas d'interaction entre créatures).
3. On les **trie** de la meilleure à la pire.
4. On **élimine la moitié du bas** et on garde les **500 meilleures**.
5. Chacune des 500 produit **1 enfant** = copie + mutations (reproduction **asexuée**, choisie « par souci d'élégance et de minimalisme »).
6. Nouvelle population = 500 parents survivants + 500 enfants = 1000. On recommence.

### 3.2 Critère de sélection (fitness) [VU]
- Ce n'est **pas** juste « qui grimpe le plus haut ». Dans la nature, la pression de sélection agit contre ceux qui dépensent trop de calories, et les animaux plus gros ou plus forts ont besoin de plus d'énergie.
- → **Score = hauteur grimpée − pénalité(énergie dépensée) − pénalité(masse musculaire)**. À hauteur égale, la créature qui dépense le moins d'énergie et qui a le moins de muscles gagne [VU].
- La hauteur est la **valeur finale à t = 10 s** [VU : « à la fin des 10 secondes, elle a fait un total de −5.7 m »].
- Énergie [CHOIX] : `E = Σ_t Σ_articulations |τ|·dt` (ou `|τ·ω|·dt`, à tester). Valeurs HUD observées sur 10 s : 0.5 (immobile), 4.9, 14.1, 25.3, 33.2, 32.5 (champion gén. 200). Calibrer `TORQUE_SCALE` et la définition de E pour tomber dans cette plage.
- Coefficients [CHOIX, à calibrer] : `score = h − 0.02·E − 0.05·M`. Contraintes de calibration :
  - Rester immobile (h ≈ 0, E ≈ 0.5) doit battre tomber (h ≈ −8).
  - Le champion de la génération 200 (h ≈ 36, E ≈ 32, M ≈ 13) doit garder un score très positif.
  - La pénalité doit être **assez forte pour produire la phase « flemmarde »** des générations 1 à 10 (voir §9). Sinon, on ne reproduit pas la dynamique de la vidéo.
- Le HUD, lui, affiche la **hauteur brute** (et pas le score).

### 3.3 Mutations [VU]
- Petits changements aléatoires de : **longueur d'os, taille de muscle, vitesse d'horloge, positions cibles** [VU]. Les icônes de la slide sont : flèches d'agrandissement (os), muscle (force), horloge (horloge), triangle (poses).
- **Grosses mutations possibles mais rares** [VU] : l'enfant ressemble en général beaucoup au parent, mais peut parfois s'en éloigner. La slide montre une distribution **en cloche avec une longue queue**.
- Implémentation [CHOIX] :
  - Chaque gène est muté avec une probabilité `P_MUT = 0.1`.
  - Amplitude : gaussienne σ = 5 % de la plage du gène ; avec une probabilité `P_BIG = 0.05`, amplitude ×10 (ou tirage Cauchy tronqué).
  - Les booléens hold sont inversés avec une probabilité `P_FLIP = 0.03`.
  - Toutes les valeurs sont clampées dans leurs bornes.

### 3.4 Remarques
- Aucun croisement, aucune spéciation, aucun élitisme spécial (les 500 meilleures survivent telles quelles, ce qui est déjà élitiste).
- **200 générations** au total dans la vidéo [VU]. Il refuse d'aller plus loin, même si la courbe n'a pas fini de converger.

---

## 4. Performance [CHOIX]
1000 créatures × 10 s × 60 Hz × sous-pas × itérations de liens, c'est lourd en Python pur. Obligatoire :
- **Batcher toute la population dans des tableaux numpy** `(N_creatures, N_points, 2)`. La topologie est identique pour tous, seules les longueurs changent.
- Boucle du solveur compilée avec **numba** (`@njit(parallel=True)`, `prange` sur les créatures).
- Mode headless pour l'évaluation. Le rendu ne sert qu'aux replays (meilleure, pire, créature choisie).
- Objectif : < 10 s par génération sur un PC de bureau.
- Déterminisme : graine RNG par génération ; sauvegarde du génome complet de toute la population à chaque génération (1000 × ~60 floats, trivial) pour pouvoir **rejouer n'importe quelle créature de n'importe quelle génération**. C'est indispensable pour les écrans des §6–7.

---

## 5. Direction artistique : style « Code BH » (jungle)

### 5.1 Principes [VU]
- **Flat design vectoriel low-poly** : aplats de couleur, **aucun contour noir**, aucune texture, aucun dégradé à part le ciel.
- Illusion de volume par **facettes triangulaires de teintes proches** (tronc, rochers, canopées) et par **objets en deux tons** (lézard : moitié gauche claire, moitié droite foncée, séparées par l'axe de la colonne).
- **Perspective atmosphérique** : plus un plan est loin, plus il est clair, désaturé et proche de la couleur du ciel.
- Lumière venant **de la gauche** : le bord gauche du tronc est plus clair, le droit plus sombre.
- Code BH a dessiné ses assets dans **Adobe Illustrator**, à partir d'un dossier d'inspiration (recherche « jungle vector », références Donkey Kong Country), puis les a exportés pour l'écran [VU]. Pour nous [CHOIX] : **génération procédurale** des formes (triangulation low-poly avec graine) **ou** assets SVG pré-dessinés et rasterisés au démarrage. Les deux doivent respecter la palette ci-dessous.

### 5.2 Palette mesurée (hex, précision ±4) [VU]

**Ciel (dégradé vertical, 3 arrêts)**
| Rôle | Hex |
|---|---|
| Haut du ciel | `#9CC484` |
| Milieu | `#C4CC8C` |
| Horizon (lueur) | `#DCD494` / `#E4D49C` |
| Nuages : traits horizontaux plats | `#FCF4D4` |

**Arrière-plans (du plus loin au plus proche)**
| Couche | Hex |
|---|---|
| L1 : silhouettes très lointaines | `#A4BC8C` (vert pâle) |
| L2 : silhouettes lointaines (arbres, palmiers, collines) | `#848C5C` (kaki) / `#7C8C5C` |
| L3 : palmiers et fougères mi-proches | `#34442C`, `#3C4C2C`, `#344424` (vert très sombre) + `#8C9C2C`, `#647C24` (feuilles éclairées) |
| Troncs de palmiers | brun `#74442C` ; tête de palmier `#8C4C2C` / `#9C5434` |

**Tronc principal (le mur d'escalade), facettes low-poly**
`#6C3C2C`, `#74442C`, `#7C442C`, `#844C2C`, `#8C4C2C`, `#944C2C`, `#945434`, `#9C5434` (les plus claires à gauche).
Branches latérales : `#74442C` avec facettes `#844C2C`.

**Canopées low-poly au premier plan**
| Rôle | Hex |
|---|---|
| Base | `#A4B41C` |
| Facettes éclairées | `#C4D41C` / `#C4D424` |
| Dessous / ombre | `#6C7C14`, `#5C6C24`, `#4C5424` |
| Lianes pendantes | `#6C7C14` (rectangles fins) |

**Sol**
| Rôle | Hex |
|---|---|
| Herbe (bande supérieure, bord dentelé) | `#748404`, `#8C9C04` |
| Terre (bande inférieure, bord low-poly) | `#74442C`, `#6C3C24` |
| Petits rochers low-poly | facettes `#9C5434` / `#744424` / `#C47C4C` |
| Touffes d'herbe et fougères | `#748404`, `#A4B41C`, `#34442C` |

**Lézard**
| Rôle | Hex |
|---|---|
| Corps, moitié claire (gauche) | `#5CAC24` |
| Corps, moitié foncée (droite) | `#4CA40C` |
| Ombres des membres / plis | `#448C2C` / `#3C8C2C` |
| Doigts (rayons clairs) | `#D4FC7C` |
| Coussinets au bout des doigts (cercles) | vert moyen `#5C9C3C` [≈] |
| Yeux | `#040404` (demi-disques noirs de chaque côté de la tête) |

**Surcouche anatomique (mode analyse)**
| Rôle | Hex |
|---|---|
| Muscle au repos | `#FC5464` / `#FC5C6C` (≈ 85 % d'opacité) |
| Muscle contracté | `#FC0434` / `#FC1444` (plus saturé) |
| Os et articulations | `#FCECD4` / `#F4ECDC` (crème) ; articulations = disques de la même couleur |

**UI / slides**
| Rôle | Hex |
|---|---|
| Fond des slides / écrans d'analyse | `#1C1C1C` au centre → `#141414` aux bords (vignette radiale) avec des zones `#242424` |
| Fond debug physique | `#040414` (bleu nuit presque noir) + grille fine `#5C5C6C` (≈ 1 carreau = 1 m) |
| Fond des schémas pédagogiques | `#F8F8F8` / `#FCFCFC` |
| Point (schémas) | `#D41424` (rouge) ; os `#3C3A4C` (gris-violet foncé) ; flèches de vitesse `#1CC41C` (vert vif) ; gravité en flèches `#F49C1C` (orange) |
| Courbe « horloge » | cyan `#54E4DC` |
| Courbe « distance » | vert clair `#9CEC6C` [≈] |
| Courbe « masse musculaire » | rose-rouge `#F4546C` [≈] |
| Barres d'histogramme | vert clair `#94F474` [≈] |
| Badges HUD | fond `#2C242C` à ~85 % d'opacité, coins arrondis, texte blanc `#FCFCFC` |
| Icône énergie (éclair) | jaune `#F4D41C` [≈] |
| Icône horloge | cyan `#54E4DC` |
| Icône muscle | rose-rouge `#FC5464` |
| Écran de fin (teaser volcan) | `#640404`, `#5C0C3C`, `#AC2C2C`, `#CC3C54`, `#FC5C5C` + silhouettes `#540C34` |

### 5.3 Typographie [VU / ≈]
- Titres des slides (« Moteur physique », « Structure », « Sélection ») : **sans-serif géométrique demi-gras**, blanc, centré en haut. Ça ressemble à *Avenir Next Demi Bold*. Alternative libre : **Nunito Sans SemiBold** ou **Montserrat SemiBold**.
- Titres de génération (« Génération 0 », « Génération 148 ») : **sans-serif géométrique light**, très grande. Ça ressemble à *Century Gothic / Avant Garde*. Alternative libre : **Questrial** ou **Didact Gothic**. Sous-titre plus petit (« Le commencement », « Horloge très rapide »).
- HUD et labels : même famille, en regular.
- Noms de fonctions sur la slide récap : **monospace** (`Movement();`).

### 5.4 Le lézard, rendu détaillé (vue de dessus) [VU]
Ordre de dessin (de l'arrière vers l'avant) :
1. **Queue** : polygone lisse qui suit la chaîne de points de la queue, large au bassin (≈ largeur du bassin) et effilé jusqu'à une pointe fine. Deux tons séparés par la ligne médiane.
2. **Pattes** : pour chaque os de membre, une **capsule** (trait épais à bouts ronds) verte (`#5CAC24` à gauche, `#4CA40C` à droite). L'humérus et le fémur sont plus épais que l'avant-bras et le tibia (≈ 70 %). Pas de contour.
3. **Mains et pieds** : 5 doigts en éventail, des **rayons courts clairs `#D4FC7C`** qui partent du point d'extrémité, avec un **disque vert au bout de chaque doigt**. Taille du disque ≈ 30 % de la largeur de l'avant-bras.
4. **Torse** : forme ovoïde qui enveloppe NECK→PELVIS, plus large au niveau des épaules et des hanches. **Moitié gauche `#5CAC24`, moitié droite `#4CA40C`**, séparation nette sur l'axe de la colonne.
5. **Tête** : ogive arrondie au-dessus de NECK, un peu plus étroite que les épaules, même découpe en deux tons. **Deux yeux noirs** en demi-disques qui dépassent légèrement des bords de la tête, vers l'arrière de celle-ci.
6. (Mode analyse) **Surcouche muscles + os** : voir §5.5.

Les formes suivent la physique à chaque frame : aucun sprite figé, tout est recalculé depuis les positions des points.

Taille à l'écran [DÉDUIT] : de la tête au bout de la queue, le lézard fait ≈ 1/6 de la hauteur de l'écran en vue normale. En plan d'analyse, la caméra zoome jusqu'à ce qu'il occupe ≈ 90 % de la hauteur.

### 5.5 Surcouche anatomique (mode analyse et slides) [VU]
- Os = traits crème `#FCECD4`, articulations = petits disques crème. Le point NECK et le point PELVIS sont plus gros.
- Muscles = **formes courbes (fuseaux et triangles) ancrées aux insertions**, en rose-rouge :
  - **Grand dorsal** : grand triangle / « V » de la colonne jusqu'aux deux épaules (partie haute du torse).
  - **Deltoïdes** : ovales sur chaque épaule.
  - **Biceps / triceps** : fuseaux de part et d'autre de l'humérus.
  - **Fessiers + fléchisseurs de hanche** : triangle inversé du bassin vers la colonne, plus des fuseaux sur la hanche.
  - **Quadriceps / ischios** : fuseaux de part et d'autre du fémur.
- **Épaisseur du fuseau ∝ force max évoluée du muscle** [VU : « pour avoir des informations sur la force de chaque articulation »].
- **Couleur et intensité ∝ contraction instantanée** [VU : « informations sur la contraction »]. Les muscles actifs passent de `#FC5464` à `#FC0434`.
- Labels d'analyse : **pourcentage en blanc** (« 22% ») relié au muscle par un **trait blanc fin** [VU].

### 5.6 Le décor (scène jungle) [VU], ordre des couches et parallaxe
| # | Couche | Contenu | Parallaxe [CHOIX] |
|---|---|---|---|
| 0 | Ciel | dégradé 3 arrêts + 2–3 traits de nuages crème | 0.0 |
| 1 | Très lointain | silhouettes `#A4BC8C` : arbres, palmiers, collines | 0.1 |
| 2 | Lointain | silhouettes `#848C5C` : gros arbres à canopée arrondie, palmiers, un peu de relief | 0.25 |
| 3 | Mi-proche | palmiers aux feuilles découpées (triangles `#34442C` / `#8C9C2C`), fougères, arbres latéraux bruns à canopée low-poly `#A4B41C` avec lianes | 0.5 |
| 4 | **Tronc principal** | bande verticale centrale (≈ 25–30 % de la largeur de l'écran), facettes low-poly brunes, légère base évasée au sol, branches qui partent en diagonale | 1.0 (plan de la créature) |
| 5 | Créature | le lézard | 1.0 |
| 6 | Premier plan | canopées low-poly jaune-vert qui **passent devant le lézard** quand la caméra monte (occlusion voulue), lianes | 1.2 |
| 7 | Sol | herbe dentelée + terre, rochers low-poly, touffes d'herbe et fougères au pied du tronc | 1.0 |

- **Caméra** : cadrage fixe au départ (sol visible en bas, lézard vers le milieu). Ensuite elle **suit la créature verticalement** (lerp doux) quand elle monte.
- **Repères de hauteur** : tous les 10 m, une **ligne blanche fine horizontale qui traverse le tronc**, avec le label « 10 m », « 20 m », « 30 m » en blanc à gauche [VU].
- **Hauteur de décor** : générer le tronc et les canopées en procédural sur **≥ 45 m** (le champion monte à 36 m).

---

## 6. HUD de simulation [VU] (t ≈ 10:14 et suivantes)

Disposition sur une frame 1280×720 :

**En haut à gauche : 3 badges empilés** (petits rectangles arrondis `#2C242C` ~85 %, icône + valeur blanche) :
1. 🕒 icône horloge cyan → **période d'horloge** : « 1.3 s »
2. ⚡ éclair jaune → **énergie dépensée cumulée** : « 33.2 »
3. 💪 icône muscle rose-rouge → **masse musculaire totale** : « 13.8 »

**En haut à droite : texte blanc aligné à droite, 3 lignes, regular** :
- « Génération: 0 »
- « Créature: 1 » pendant l'évaluation, ou « Classement: #1 » / « Classement: #1000 » pendant les replays après tri
- « Temps: 6.5 s » (chrono de 0 à 10 s)

**Étiquette de hauteur, qui suit le lézard** : un badge sombre arrondi placé **à gauche du tronc, à la hauteur du lézard**, avec une **pointe triangulaire tournée vers la droite** (vers la créature). Il contient une **icône triple chevron vert vers le haut** et la valeur « −4.9 m » / « 23.1 m ».

**Cartons de génération** : au début de chaque génération montrée, un voile sombre sur la scène, « Génération N » en grand (light, blanc, centré) et un sous-titre optionnel (« Le commencement », « Horloge très rapide »).

**Accéléré** : une icône ⏩ (deux triangles blancs) en bas à gauche quand on passe plusieurs générations d'un coup.

---

## 7. Écrans d'analyse (à reproduire) [VU]

### 7.1 Vue population
- Fond `#1C1C1C` avec vignette.
- **Les 1000 créatures en miniature dans une grille de 40 colonnes × 25 lignes**, chacune dans sa pose finale (petites silhouettes vertes).
- Animation 1 : les colonnes apparaissent de gauche à droite pendant l'évaluation.
- Animation 2 : **tri animé**. Chaque miniature glisse de sa place vers son rang (1 = en haut à gauche, lecture en lignes).
- Animation 3 : **les 500 du bas disparaissent**, puis les enfants apparaissent.

### 7.2 Histogramme de la distribution de hauteur
- Panneau sombre, grille gris foncé, graduations en petit texte blanc.
- **Axe X de −10.0 à 40.0 m, pas de 5 ; barres de 1 m.** Les valeurs < −10 vont dans la première barre.
- **Axe Y de 0 à 500.**
- Barres vert clair.
- Une flèche blanche peut pointer un pic (≈ 450 créatures au sol en génération 0).

### 7.3 Graphes d'évolution (sur les générations)
- Axe X = génération (0 → 200) ; grille gris clair sur fond sombre `#1C1C1C`.
- Courbes :
  - **Période d'horloge moyenne** (cyan), axe 0–5.0.
  - **Distance moyenne** (vert), sur le même graphe à l'échelle ÷10 [DÉDUIT : la courbe verte va de ≈ 0.4 à 3.8 alors que les meilleurs font 36 m].
  - **Masse musculaire moyenne** (rose-rouge), axe 0–25.0.
- Des **bandes verticales colorées** mettent en évidence des phases : vert translucide « réduction rapide » sur les chutes de l'horloge, bleu translucide « perfectionnement », etc., avec le label en petit au-dessus.
- En incrustation pendant les replays, **2 petits panneaux empilés à gauche** (muscle en haut, horloge en bas) dans un cadre **semi-transparent avec flou d'arrière-plan** (effet verre dépoli sur la jungle). En pygame : flouter la région du fond (downscale/upscale) puis superposer un rectangle arrondi sombre à ~60 %.

### 7.4 Mode analyse biomécanique
- La caméra zoome sur le champion au milieu du tronc (le décor reste visible sur les bords).
- La surcouche muscles + os (§5.5) s'anime en temps réel.
- Les % des muscles s'affichent un par un avec un trait de rappel.
- Option ralenti ×0.25.

### 7.5 Comparaison de générations
Plusieurs meilleures créatures de générations différentes superposées en **fantômes semi-transparents** sur la même scène, avec le label « Génération 200 » sur la plus avancée [VU à t ≈ 16:48, détail exact non montré].

### 7.6 Vue debug physique
Fond `#040414` et grille fine (≈ 1 m). La créature est affichée en « écorché » (os crème + muscles rose-rouge), sans décor. On y voit la queue sous forme de chaîne de points [VU].

---

## 8. Mode d'emploi du programme (CLI) [CHOIX]
```
python main.py train --generations 200 --pop 1000 --seed 42
python main.py replay --gen 200 --rank 1          # meilleure créature
python main.py replay --gen 200 --rank 1000       # pire créature
python main.py population --gen 0                  # vue grille + tri animé
python main.py histogram --gen 0
python main.py graphs                              # courbes horloge / distance / muscle
python main.py analyze --gen 200 --rank 1          # zoom biomécanique + %
python main.py compare --gens 0 23 100 200
python main.py debug-physics                       # bancs d'essai du moteur (§10.1)
```
Tout le paramétrage est dans `config.py` (dt, sous-pas, itérations, g, bornes de gènes, taux de mutation, coefficients de fitness, palette, polices).
Sauvegardes : `runs/<seed>/gen_XXXX.npz` (génomes + scores + stats), `runs/<seed>/stats.csv`.

---

## 9. Résultats de référence (pour calibrer) [VU]
La simulation est « correcte » si elle reproduit **qualitativement** cette trajectoire :

| Génération | Observation dans la vidéo |
|---|---|
| **0** | Créatures aléatoires. La n°1 bouge beaucoup les bras mais ne tient qu'avec les pieds, et finit à **−5.7 m**. La n°2 descend en rappel, tête en haut, puis se couche sur le côté. **≈ 450/1000 au sol** à 10 s. Le reste est étalé de −9 à ~+1 m, avec un petit groupe autour de 0. **La meilleure ne grimpe pas** : elle reste sur place en dépensant peu (énergie 0.5, −0.1 m). Les pires dépensent énormément et finissent au sol. |
| **1** | Peu de différence, mais les vraiment nulles diminuent (≈ 200 au sol) et le pic autour de 0 grossit. La meilleure a **moins de muscles** qu'en génération 0. |
| **1 → 10** | **Piège de la flemme** : la masse musculaire moyenne chute de ≈ 13.2 à **≈ 7.3 (génération ~11)**, et la période d'horloge **augmente** (les créatures ralentissent) de ≈ 2.9 à ≈ 4.5 s. En génération 10, la meilleure ne fait rien. |
| **12** | Première créature qui grimpe un peu : **≈ +1 m**. |
| **~20** | La masse musculaire remonte à ≈ 9.7 (il faut des muscles pour grimper). |
| **23** | La meilleure passe **2 m en 10 s** (2.3 m ; période 4.9 s ; énergie 4.9 ; muscle 8.0). Elle se **tracte surtout avec le haut du corps** (beaucoup de bras et de dorsaux). |
| **~45–75** | La période plafonne à ≈ 4.7–4.9 s. La masse musculaire est stable autour de 9. |
| **~80–85** | **Première chute brutale de la période : ≈ 4.6 → 1.9 s** (une créature plus rapide remplace la population). La distance monte. |
| **~85–140** | Plateau de la période à ≈ 1.9 s. La masse musculaire baisse vers ≈ 8 (gén. 100) puis remonte à ≈ 11.3 (gén. 140), quand la grimpe rapide exige plus de force. |
| **~140–150** | **Deuxième chute : ≈ 1.9 → 1.0 s.** |
| **148** | Carton « Génération 148 — Horloge très rapide ». |
| **150–200** | Décroissance lente de la période jusqu'à **≈ 0.6 s**. La distance moyenne continue de monter. La masse musculaire se perfectionne à la baisse (≈ 10.5). |
| **200** | La meilleure grimpe de façon coordonnée jusqu'à **36 m en 10 s** (23.1 m à t = 6.4 s ; période 0.6 s ; énergie 32.5 ; muscle 13.5). La majorité grimpe **entre 30 et 35 m**. **Il reste une petite fraction au sol** (≈ 30 créatures dans la barre −10). La pire (#1000) est presque normale mais **fixe ses mains moins souvent**, et ça suffit à la déséquilibrer. |

**Biomécanique du champion de la génération 200** [VU] :
- **Haut du corps, 2 phases** :
  1. Activation du **deltoïde** pour lever le bras.
  2. **Main fixée** au mur, grosse activation du **grand dorsal** pour se tirer, avec le **biceps** qui assiste en flexion.
- Forces évoluées (en % du max autorisé) :
  - **Deltoïde 22 %** (il lève juste un bras léger).
  - **Grand dorsal 76 %**, **biceps 57 %** (ils soulèvent toute la créature).
- **Bas du corps**, même schéma :
  - **Fléchisseur de hanche faible** (≈ 31 %, il lève la jambe).
  - **Fessier plus fort** (il porte le poids).
- **Démarche** : les pattes **alternent en diagonale** (main gauche avec pied droit), ce qui garde toujours au moins une patte fixée de chaque côté pour la stabilité.
- Conclusion de la vidéo : ces proportions et cette stratégie ressemblent au vivant, donc le simulateur est proche des contraintes réelles.

**Leçons clés à retrouver** :
- Les comportements simples s'optimisent d'abord. Les mutations « flemmardes » (ralentir l'horloge, réduire les muscles, rester accroché) sont simples et nombreuses. Les mutations « grimper efficacement » sont complexes et rares.
- **La vitesse d'horloge est la variable qui guide le plus l'évolution** : elle avance par plateaux et chutes brutales, et elle suit directement la distance.
- La masse musculaire suit un cycle **découverte → perfectionnement** : elle monte quand un nouveau mode de grimpe apparaît, puis elle baisse quand la technique s'affine.
- Grimper est **fragile** : une petite mutation (moins de prises de main) suffit à tout faire rater.

---

## 10. Plan d'implémentation pour Claude Code

Travailler **phase par phase**, avec validation visuelle à chaque étape. Ne pas passer à la suite tant que les critères ne sont pas remplis.

### Phase 1 : moteur physique + bancs d'essai (`debug-physics`)
Reproduire les démos de la vidéo sur fond `#F8F8F8` (points rouges `#D41424`, os `#3C3A4C`, flèches de vitesse vertes) :
1. Un point en mouvement rectiligne.
2. Un point soumis à la gravité (parabole).
3. Un point fixé.
4. Deux points liés qui tombent : longueur constante, aucune élasticité au ralenti.
5. Chaîne de 3+ points : montrer l'erreur de longueur après 1, 2, 5, 20 itérations. Elle doit converger.
6. Articulation qui se contracte : somme des forces nulle (vérifiée numériquement).
7. Masses = somme des demi-longueurs, avec l'affichage coloré du §1.6.
8. **Pendule humain** : squelette complet suspendu par une main pendant 10 s → erreur de longueur < 1 %, aucune explosion numérique.

### Phase 2 : créature + contrôleur
- Topologie §2.2, muscles §2.3, contrôleur PD §2.4.
- Vue debug `#040414` avec grille, écorché os + muscles.
- Test : une créature avec des poses écrites à la main (diagonale : main G + pied D fixés, puis inversion) doit monter un peu. C'est la preuve que la grimpe est possible avec ce moteur.

### Phase 3 : évolution headless
- Population vectorisée numpy/numba, fitness §3.2, sélection/mutation §3.1–3.3.
- Log `stats.csv` : pour chaque génération, moyenne/médiane/max/min de la hauteur, de la période d'horloge moyenne et de la masse musculaire moyenne ; histogramme 1 m de −10 à 40.
- **Calibrer les coefficients de fitness et `TORQUE_SCALE`** jusqu'à retrouver qualitativement le §9 : phase flemmarde de 1 à 10, première grimpe vers 10–25, chutes d'horloge par paliers, gros gain à 200 générations. Documenter les valeurs retenues.

### Phase 4 : rendu jungle
- Décor §5.6 avec la palette §5.2, low-poly procédural, parallaxe, premier plan qui occulte, repères de hauteur.
- Lézard §5.4 qui suit la physique.
- **Validation** : capture côte à côte avec les frames de référence (t = 8:02, 10:20, 13:55, 14:35 de la vidéo). La palette, la lumière venant de la gauche, les deux tons du lézard et les facettes du tronc doivent correspondre.

### Phase 5 : HUD + écrans d'analyse
HUD §6, population §7.1, histogramme §7.2, graphes §7.3, analyse biomécanique §7.4, comparaison §7.5.

### Phase 6 : polish
- Cartons de génération, lerp de caméra, ralenti, export PNG/MP4 (pygame → frames → ffmpeg).
- Option : écran de fin « teaser » en palette rouge volcan (§5.2), pour préparer la suite multi-environnements.

---

## 11. Checklist finale « identique à Code BH »
- [ ] Liens rigides par correction de vitesse itérée, sans élasticité.
- [ ] Masse = somme des demi-longueurs d'os.
- [ ] Muscles asymétriques (force différente dans chaque sens), 8 muscles nommés par côté.
- [ ] Contrôleur = horloge + K poses (angles + prise/lâcher de chaque patte).
- [ ] Génome = longueurs d'os + forces musculaires + horloge + poses.
- [ ] 1000 créatures, 10 s, top 500, 1 enfant chacun, mutations petites + rares grosses.
- [ ] Fitness = hauteur finale − énergie − masse musculaire.
- [ ] Phase flemmarde observée au début, puis grimpe, puis chutes d'horloge par paliers.
- [ ] Scène jungle low-poly, palette §5.2, lézard vert en deux tons vu de dessus avec doigts en étoile et yeux noirs.
- [ ] HUD : 3 badges (horloge / énergie / muscle) + Génération/Classement/Temps + étiquette de hauteur.
- [ ] Vue population 40×25 avec tri animé, histogramme −10→40 m, courbes cyan/vert/rouge.
- [ ] Mode analyse avec muscles en surcouche et pourcentages.

---

*Note : Code BH a publié une suite, « J'ai codé des créatures qui s'adaptent aux éléments », qui ajoute plusieurs environnements et des espèces. Elle n'est pas couverte ici.*
