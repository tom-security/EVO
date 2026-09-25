# Polices (SIL Open Font License 1.1)

Alternatives libres du §5.3 de la spec, téléchargées depuis le dépôt GitHub `google/fonts`
(branche `main`, le 2026-09-24).

| Fichier | Source | Usage |
|---|---|---|
| `Questrial-Regular.ttf` | `ofl/questrial/Questrial-Regular.ttf` | HUD, cartons de génération, repères de hauteur (alternative à Century Gothic / Avant Garde) |
| `NunitoSans-SemiBold.ttf` | instance statique de `ofl/nunitosans/NunitoSans[YTLC,opsz,wdth,wght].ttf` | titres des slides (alternative à Avenir Next Demi Bold) |

Licences : `Questrial-OFL.txt`, `NunitoSans-OFL.txt` (aucun nom de police réservé).

Nunito Sans n'est plus publiée qu'en police variable, que pygame ne sait pas instancier ;
l'instance SemiBold a été extraite avec fontTools (`fontTools.varLib.instancer`), axes à leur
valeur par défaut sauf `wght = 600` :

```
instancer.instantiateVariableFont(TTFont("NunitoSans[YTLC,opsz,wdth,wght].ttf"),
                                  {"wght": 600, "wdth": 100, "opsz": 12, "YTLC": 500},
                                  updateFontNames=True)
```

SHA-256 :
- `Questrial-Regular.ttf` 0ee7f2debabb13773fd38468b31820e11fca202a8f98c4d80b6ffcb796899b6f
- police variable Nunito Sans d'origine f934d7142fb4784bf828da485b7dcbd90c0c80d514e9d49a5da0ed3a1ae2491d
- `NunitoSans-SemiBold.ttf` 78eb68c74c60aa493496a338774af7b04a826f319bd8aa16966599bcf65f8acc
