"""Courbes du duel (v2, docs/SPEC_V2_GECKO.md, « Mesures et livrables ») : meilleure hauteur accrochée en fonction du
nombre de lézards testés, pour l'évolution (runs existants, recalculés) et pour le hasard pur.

- Évolution (`courbe_evolution`) : chaque génome évalué par le run est réévalué par l'évaluateur batché, dans l'ordre
  où le run les a évalués : les N créatures de la génération 0 (indices 0 à N − 1), puis, à chaque génération, ses
  enfants (`is_child`, indices N/2 à N − 1) ; les survivantes ne sont pas réévaluées par le run, elles ne comptent pas.
  Garde-fou : hauteur à 10 s et énergie réévaluées identiques au bit près aux valeurs stockées, sinon erreur (même
  machine que l'entraînement : le runner). La hauteur accrochée est la seule grandeur nouvelle.
- Hasard pur (`hasard`) : n génomes tirés par le générateur de la génération 0 de l'évolution
  (`creature.random_genome`, `default_rng([graine, 0])`), graines config.HASARD_GRAINES, distinctes de celles des runs ;
  manche 1 : corps figé (config.FROZEN_BODY), manche 2 : corps libre.
- Sorties : <nom>_paliers.csv (une ligne à chaque nouveau record : évaluations, meilleure hauteur accrochée, génération,
  indice), <nom>_evaluations.npz (toutes les évaluations) et <nom>_resume.json.
"""
import csv
import json
import os
import time

import numpy as np

import config
from evo import batch
from evo import creature as cr
from evo import evolution as ev


def _sortie(sortie, nom, gens, idx, hang, height, energy, hung, extra, log):
    """Écrit paliers, évaluations et résumé ; renvoie le résumé."""
    os.makedirs(sortie, exist_ok=True)
    best = np.maximum.accumulate(hang)
    new = np.flatnonzero(np.r_[True, best[1:] > best[:-1]])
    with open(os.path.join(sortie, f"{nom}_paliers.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["evaluations", "meilleure_hauteur_accrochee", "generation", "indice"])
        for k in new:
            w.writerow([int(k) + 1, repr(float(best[k])), int(gens[k]), int(idx[k])])
        if new[-1] != len(hang) - 1:                         # dernière évaluation : fin de la courbe
            w.writerow([len(hang), repr(float(best[-1])), int(gens[-1]), int(idx[-1])])
    np.savez_compressed(os.path.join(sortie, f"{nom}_evaluations.npz"), generation=gens, indice=idx,
                        hauteur_accrochee=hang, hauteur_10s=height, energie=energy, accrochee=hung)
    k = int(np.argmax(hang))                                 # premier atteint en cas d'égalité
    resume = {"nom": nom, "evaluations": int(len(hang)), "meilleure_hauteur_accrochee": float(hang[k]),
              "atteinte_a_l_evaluation": k + 1, "generation": int(gens[k]), "indice": int(idx[k]),
              "energie_du_meilleur": float(energy[k]), "hauteur_10s_du_meilleur": float(height[k]),
              "jamais_accrochees": int(np.sum(~hung)),
              "hauteur_accrochee_differente": int(np.sum(hang != height)),
              "paliers": [[int(i) + 1, float(best[i])] for i in new]}
    resume.update(extra)
    with open(os.path.join(sortie, f"{nom}_resume.json"), "w", encoding="utf-8") as fh:
        json.dump(resume, fh, ensure_ascii=False, indent=1)
    log(f"{nom} : {len(hang)} évaluations, meilleure hauteur accrochée {hang[k]:+.3f} m à l'évaluation {k + 1} "
        f"(gén. {gens[k]}, n°{idx[k]}) → {sortie}")
    return resume


def courbe_evolution(run_dir, sortie, nom=None, log=print):
    """Courbe d'un run d'évolution existant (voir le module) ; erreur si une réévaluation n'est pas identique."""
    nom = nom or os.path.normpath(run_dir).replace(os.sep, "_").replace("/", "_")
    ev.use_run_config(run_dir)
    gens_saved = ev.saved_generations(run_dir)
    out = {k: [] for k in ("gen", "idx", "hang", "height", "energy", "hung")}
    t0 = time.perf_counter()
    for gen in gens_saved:
        pop, res, lineage, _ = ev.load_generation(run_dir, gen)
        idx = np.arange(len(pop)) if gen == 0 else np.flatnonzero(lineage["is_child"])
        r = batch.evaluate(pop.take(idx).to_genomes(), duration=config.SIM_DURATION)
        for key, stored in (("height", res["height"][idx]), ("energy", res["energy"][idx])):
            if not np.array_equal(r[key], stored):
                bad = int(np.sum(r[key] != stored))
                raise RuntimeError(f"{run_dir}, gén. {gen} : {bad} réévaluations de « {key} » ne sont pas identiques "
                                   f"au run (rejeu non identique au bit près)")
        out["gen"].append(np.full(len(idx), gen))
        out["idx"].append(idx)
        for key, src in (("hang", "hang_height"), ("height", "height"), ("energy", "energy"), ("hung", "hung")):
            out[key].append(r[src])
        if gen % 20 == 0:
            log(f"  {run_dir} gén. {gen} : {sum(len(a) for a in out['idx'])} évaluations, "
                f"{time.perf_counter() - t0:.0f} s")
    arr = {k: np.concatenate(v) for k, v in out.items()}
    extra = {"source": "evolution", "run": os.path.normpath(run_dir).replace(os.sep, "/"),
             "generations": len(gens_saved) - 1, "reevaluations_identiques": True,
             "frozen_body": bool(config.FROZEN_BODY), "secondes": round(time.perf_counter() - t0, 1)}
    return _sortie(sortie, nom, arr["gen"], arr["idx"], arr["hang"], arr["height"], arr["energy"], arr["hung"], extra,
                   log)


def tirage_hasard(manche, tirage, n=None):
    """Les n génomes du tirage (liste de creature.Genome), corps figé en manche 1."""
    n = config.HASARD_ESSAIS if n is None else n
    graine = config.HASARD_GRAINES[tirage]
    frozen = config.FROZEN_BODY
    try:
        config.FROZEN_BODY = manche == 1
        rng = np.random.default_rng([graine, 0])             # comme la génération 0 d'un run (evolution.train)
        return [cr.random_genome(rng) for _ in range(n)], graine
    finally:
        config.FROZEN_BODY = frozen


def hasard(manche, tirage, sortie, n=None, log=print):
    """Courbe du hasard pur : un tirage de n génomes aléatoires, évalués dans l'ordre du tirage."""
    genomes, graine = tirage_hasard(manche, tirage, n)
    t0 = time.perf_counter()
    r = batch.evaluate(genomes, duration=config.SIM_DURATION)
    idx = np.arange(len(genomes))
    nom = f"hasard_m{manche}_t{tirage}"
    extra = {"source": "hasard", "manche": manche, "tirage": tirage, "graine": graine,
             "frozen_body": manche == 1, "secondes": round(time.perf_counter() - t0, 1)}
    return _sortie(sortie, nom, np.zeros(len(idx), int), idx, r["hang_height"], r["height"], r["energy"], r["hung"],
                   extra, log)
