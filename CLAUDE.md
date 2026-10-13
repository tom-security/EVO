Lis docs/CODEBH_GRIMPE_SPEC.md avant toute modification.
Les images de référence sont dans docs/reference/ : chaque nom donne le numéro, le sujet et l'instant
de la vidéo (ex. 21_schema_contraction_newton_t4m32s.png = « t = 4:32 » dans la spec).
Avance phase par phase (section 10), et ne passe à la phase suivante qu'après validation.
Tout ce qui est marqué [CHOIX] ou [DÉDUIT] va dans config.py.

État du projet, décisions et règles détaillées : docs/PASSATION.md (à lire en entier en arrivant), puis
docs/BILAN_V1.md. La v1 (reproduction de la vidéo de Code BH) est gelée ; la suite est la v2 (duel LLM contre
évolution).

Règles essentielles :
- Tout en français : code, commentaires, commits, rapports, échanges.
- Cycle de travail : plan, validation de l'utilisateur, exécution de ce qui a été validé, rapport chiffré (avec les
  valeurs de référence et les écarts à la vidéo), puis arrêt. Jamais d'étape suivante sans accord explicite.
- Ne pas toucher à ce qui est validé (PASSATION §10) sans demande explicite ; les écarts connus restent en liste (§11).
- Toute nouveauté physique passe derrière un drapeau de config.py dont l'absence dans le config.json d'un run redonne
  l'ancien comportement (evolution.LEGACY_DEFAULTS) ; elle est ajoutée aux trois implémentations (numba scalaire,
  référence Python, évaluateur batché) avec un test d'égalité au bit près. Aucune constante de config.py n'est
  supprimée ni renommée : les config.json des runs les rejouent.
- Reproductibilité : un run ne se rejoue au bit près que sur le runner GitHub ubuntu-24.04 (versions épinglées dans
  requirements.txt), pas sous Windows. Entraînements, rejeux, mesures de runs et écrans passent par
  .github/workflows/train.yml (modes train, reproductibilite, pytest, analyse ; PASSATION §3.5).
- Les captures de la vidéo (docs/reference/) ne sortent jamais dans les artefacts publics du workflow ; les planches
  avec la vidéo se font sur le PC.
- Git : nouvelle branche par chantier ; git push -u origin <branche> ; jamais --force, jamais de réécriture
  d'historique, aucune suppression de branche ou de run sans accord ; pas de pull request sans demande ; rien n'est
  fusionné sur main sans décision de l'utilisateur.
- Les runs (runs/), les exports (out/), le cache (cache/) et les artefacts rapatriés (artefacts/) restent hors git.
