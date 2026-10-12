"""Commande `trace` : rejeu pas à pas d'une créature d'un run, avec l'audit d'énergie (evo/audit.py) à chaque sous-pas.

Sert au diagnostic (en lecture seule, moteur inchangé) d'une énergie créée hors muscles ou d'une butée franchie :
qui (créature), quand (sous-pas, avant ou après la chute), par quelle étape (gravité, muscles, prises, liens et
contacts, mouvement, projection et sol), dans quel état (prises, points au sol, butées actives par groupe).
Écrit un CSV (une ligne par sous-pas) et rapporte un résumé ; la hauteur rejouée est vérifiée contre le run.
"""
import csv
import math
import os

import numpy as np

import config
from evo import audit
from evo import creature as cr
from evo import evolution as ev
from evo import skeleton as sk
from evo import tail_audit as ta

TOP = 8           # sous-pas les plus « créateurs » détaillés dans le résumé


def trace(run_dir, gen, index, log=print, out_dir=None):
    ev.use_run_config(run_dir)
    pop, res, _, _ = ev.load_generation(run_dir, gen)
    genome = pop.genome(index)
    h = config.DT / config.SUBSTEPS
    c = cr.Creature(genome)
    c.tail_links = np.array([name == "tail" for name in c.skel.link_names])
    ledger = {k: 0.0 for name in audit.STAGES for k in (name, name + "+")}
    ledger.update({"total": 0.0, "schema_gravite": 0.0, "hors_muscles+": 0.0, "max_speed": 0.0,
                   "max_torso_speed": 0.0, "max_length_error": 0.0, "max_tail_error": 0.0, "max_height": -np.inf})
    ledger.update({k: 0.0 for k in audit.LIMIT_KEYS})
    groups = cr.limit_groups(len(c.world.limit_lo)) if len(c.world.limit_lo) else {}
    weight = float(c.world.mass.sum() * config.G)
    rows = []
    fallen_at = None
    for n in range(int(round(config.SIM_DURATION / h))):
        before = dict(ledger)
        audit.audited_substep(c, h, ledger)
        w = c.world
        stage = {s: ledger[s] - before[s] for s in audit.STAGES}
        created = ledger["hors_muscles+"] - before["hors_muscles+"]
        if c.fallen and fallen_at is None:
            fallen_at = (n + 1) * h
        err = np.abs(w.link_lengths() - w.rest) / w.rest
        on_ground = w.pos[:, 1] <= config.GROUND_Y + 1e-6
        margins = w.limit_violation() if len(w.limit_lo) else np.zeros(0)
        delta = ta.signed_tail_angles(w.pos[None])[0]
        row = {"t": round((n + 1) * h, 6), "cree_J": created, **{f"d_{s}": v for s, v in stage.items()},
               "tenus": int(w.held.sum()), "tombee": int(c.fallen),
               "sol_corps": int(on_ground[:sk.TAIL_START].sum()), "sol_queue": int(on_ground[sk.TAIL_START:].sum()),
               "queue_ecart_max_deg": float(np.abs(delta).max()), "queue_os_max": float(err[c.tail_links].max()),
               "os_corps_max": float(err[~c.tail_links].max()), "hauteur": c.height()}
        for name, idx in groups.items():
            row[f"actives_{name}"] = int(w.limit_active[idx].sum())
            row[f"marge_min_{name}_deg"] = float(math.degrees(margins[idx].min()))
        rows.append(row)
    stored = float(res["height"][index])
    result = {"run": run_dir, "gen": gen, "indice": index, "poids": weight, "tombee_a": fallen_at,
              "hauteur": c.height(), "hauteur_stockee": stored, "identique": abs(c.height() - stored) <= 1e-9,
              "cree_J": float(ledger["hors_muscles+"]), "rows": rows}
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        seed = os.path.basename(os.path.normpath(run_dir))
        path = os.path.join(out_dir, f"trace_s{seed}_g{gen}_n{index}.csv")
        with open(path, "w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        result["csv"] = path
    if log:
        for line in summary_lines(result):
            log(line)
    return result


def summary_lines(r):
    rows = r["rows"]
    created = np.array([x["cree_J"] for x in rows])
    t = np.array([x["t"] for x in rows])
    w = r["poids"]
    fall = r["tombee_a"]
    lines = [f"trace — {r['run']}, gén. {r['gen']}, n°{r['indice']} : hauteur rejouée {r['hauteur']:+.9f} m, stockée "
             f"{r['hauteur_stockee']:+.9f} m → " + ("identique" if r["identique"] else "ÉCART")
             + (f" ; tombée à {fall:.3f} s" if fall else " ; jamais tombée"),
             f"  énergie créée hors muscles : {r['cree_J']:.3f} J ({100 * r['cree_J'] / w:.2f} cm) ; "
             f"sous-pas créateurs (> 1 mJ) : {int((created > 1e-3).sum())}"]
    if fall:
        lines.append(f"  avant la chute : {created[t <= fall].sum():.3f} J ; après : {created[t > fall].sum():.3f} J")
    bins = np.floor(t).astype(int)
    lines.append("  par seconde (J) : " + " ".join(f"{created[bins == b].sum():.2f}" for b in range(int(t[-1]) + 1)))
    stages = [s for s in audit.STAGES]
    big = created > 1e-3
    if big.any():
        pos = {s: sum(max(x[f"d_{s}"], 0.0) for x, b in zip(rows, big) if b) for s in stages}
        lines.append("  étapes qui ajoutent de l'énergie dans ces sous-pas (somme des hausses, J) : "
                     + ", ".join(f"{s} {v:.2f}" for s, v in pos.items() if v > 1e-6))
        keys = [k for k in rows[0] if k.startswith("actives_")]
        lines.append("  état moyen dans ces sous-pas : tenus {:.1f}, points du corps au sol {:.1f}, de la queue {:.1f}, "
                     .format(*(np.mean([x[k] for x, b in zip(rows, big) if b]) for k in ("tenus", "sol_corps", "sol_queue")))
                     + ", ".join(f"{k[8:]} actives {np.mean([x[k] for x, b in zip(rows, big) if b]):.1f}" for k in keys))
    for k in np.argsort(created)[::-1][:TOP]:
        x = rows[k]
        if x["cree_J"] <= 1e-6:
            break
        st = ", ".join(f"{s} {x[f'd_{s}']:+.3f}" for s in stages if abs(x[f"d_{s}"]) > 1e-4)
        act = ", ".join(f"{q[8:]} {x[q]}" for q in x if q.startswith("actives_"))
        lines.append(f"    t = {x['t']:.4f} s : créé {x['cree_J']:.4f} J | {st} | tenus {x['tenus']}, au sol corps "
                     f"{x['sol_corps']} queue {x['sol_queue']} | butées actives : {act} | queue écart max "
                     f"{x['queue_ecart_max_deg']:.1f}°, os de queue {100 * x['queue_os_max']:.2f} %")
    worst_tail = max(rows, key=lambda x: x["queue_ecart_max_deg"])
    lines.append(f"  queue : écart max à l'axe {worst_tail['queue_ecart_max_deg']:.1f}° à t = {worst_tail['t']:.4f} s "
                 f"(au sol : queue {worst_tail['sol_queue']}, corps {worst_tail['sol_corps']}) ; os de queue max "
                 f"{100 * max(x['queue_os_max'] for x in rows):.2f} %, os du corps max "
                 f"{100 * max(x['os_corps_max'] for x in rows):.2f} %")
    pen = {k[10:-4]: min(x[k] for x in rows) for k in rows[0] if k.startswith("marge_min_")}
    if pen:
        lines.append("  marge minimale des butées (°, < 0 = au-delà) : " + ", ".join(f"{k} {v:+.3f}" for k, v in pen.items()))
    if r.get("csv"):
        lines.append(f"  {r['csv']}")
    return lines
