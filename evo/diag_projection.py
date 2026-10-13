"""Commande `diag-projection` (diagnostic du chantier D, lecture seule) : rejoue des créatures avec le moteur tel quel
puis avec des variantes de la stabilisation, substituées le temps de la mesure seulement. Le moteur du dépôt n'est pas
modifié ; à la sortie de chaque mesure, `physics.project_links` et `config.N_ITER` retrouvent leur valeur.

Variantes (candidats du chantier D) :
- `tel_quel`     : le moteur ;
- `vitesse_proj` (a) : toute correction de position de la projection est reportée sur la vitesse, v += Δp/h ;
- `dissipatif`   (b) : même report, multiplié par un facteur unique α ∈ [0, 1], le plus grand qui n'augmente pas
  l'énergie cinétique : avec Δv = Δp/h, B = Σ m·v·Δv et A = Σ m·|Δv|², α = min(1, −2B/A) si B < 0, sinon 0. La
  correction ne peut que retirer de l'énergie cinétique, jamais en ajouter ;
- `passes120`    (c) : résolution en vitesse renforcée, 120 passes de Gauss-Seidel au lieu de N_ITER (30), sur les
  liens, les butées et le sol.

La variante change la dynamique : sa hauteur n'a pas à égaler la hauteur stockée ; celle du moteur tel quel, si
(contrôle au bit près).
"""
import contextlib
import math
import time

import numpy as np

import config
from evo import audit
from evo import creature as cr
from evo import evolution as ev
from evo import physics

H = config.DT / config.SUBSTEPS
VARIANTS = ("tel_quel", "vitesse_proj", "dissipatif", "passes120")
PASSES = 120
# Dernier sous-pas : report sur la vitesse (énergie cinétique ajoutée, facteur α), et ce que la résolution en vitesse a
# laissé à la projection (relevé juste avant elle, en lecture seule, y compris avec le moteur tel quel) : marge
# minimale des butées de queue (rad, < 0 = franchie), étirement maximal des liens, correction de position maximale.
LAST = {"ke_vitesse": 0.0, "alpha": 1.0, "pre_marge_queue": 0.0, "pre_lien": 0.0, "dp_max": 0.0}


def _recorder(project):
    """Enveloppe de lecture : relève l'état avant la projection et la correction qu'elle fait, sans rien changer."""
    def recorded(world):
        before = world.pos.copy()
        if len(world.limit_lo) > len(cr.JOINTS) + 2:
            LAST["pre_marge_queue"] = float(world.limit_violation()[len(cr.JOINTS) + 2:].min())
        else:
            LAST["pre_marge_queue"] = 0.0
        LAST["pre_lien"] = float((np.abs(world.link_lengths() - world.rest) / world.rest).max())
        project(world)
        LAST["dp_max"] = float(np.abs(world.pos - before).max())
    return recorded


def _velocity_update(original, dissipative):
    def project(world):
        before = world.pos.copy()
        original(world)
        dv = (world.pos - before) / H
        m = world.mass[:, None]
        if dissipative:
            b = float(np.sum(m * world.vel * dv))
            a = float(np.sum(m * dv * dv))
            alpha = min(1.0, -2.0 * b / a) if (b < 0.0 and a > 0.0) else 0.0
        else:
            alpha = 1.0
        ke0 = float(0.5 * np.sum(m * world.vel ** 2))
        world.vel += alpha * dv
        LAST["ke_vitesse"] = float(0.5 * np.sum(m * world.vel ** 2)) - ke0
        LAST["alpha"] = alpha
    return project


@contextlib.contextmanager
def variant(name, record=False):
    """Substitue la variante `name` le temps du bloc, puis rend le moteur tel quel. record : relève aussi, en lecture
    seule, l'état avant chaque projection (LAST), y compris avec le moteur tel quel."""
    if name not in VARIANTS:
        raise ValueError(f"variante inconnue : {name} ({', '.join(VARIANTS)})")
    original, n_iter = physics.project_links, config.N_ITER
    LAST.update(ke_vitesse=0.0, alpha=1.0, pre_marge_queue=0.0, pre_lien=0.0, dp_max=0.0)
    try:
        project = original
        if name == "vitesse_proj":
            project = _velocity_update(original, dissipative=False)
        elif name == "dissipatif":
            project = _velocity_update(original, dissipative=True)
        elif name == "passes120":
            config.N_ITER = PASSES
        physics.project_links = _recorder(project) if record else project
        yield
    finally:
        physics.project_links, config.N_ITER = original, n_iter
        LAST.update(ke_vitesse=0.0, alpha=1.0, pre_marge_queue=0.0, pre_lien=0.0, dp_max=0.0)


def _new_creature(genome):
    c = cr.Creature(genome)
    if config.N_ITER != c.world.n_iter:     # World lit config.N_ITER à sa création ; passes120 s'applique ici aussi
        c.world.n_iter = config.N_ITER
    return c


def measure(genome, name="tel_quel"):
    """Rejeu audité (evo/audit.py) d'une grimpe avec la variante `name` : énergie créée hors muscles, queue, butées."""
    with variant(name):
        c = _new_creature(genome)
        c.tail_links = np.array([n == "tail" for n in c.skel.link_names])
        ledger = {k: 0.0 for stage in audit.STAGES for k in (stage, stage + "+")}
        ledger.update({"total": 0.0, "schema_gravite": 0.0, "hors_muscles+": 0.0, "max_speed": 0.0,
                       "max_torso_speed": 0.0, "max_length_error": 0.0, "max_tail_error": 0.0, "max_height": -np.inf})
        ledger.update({k: 0.0 for k in audit.LIMIT_KEYS})
        groups = cr.limit_groups(len(c.world.limit_lo)) if len(c.world.limit_lo) else {}
        over5 = exits = 0
        worst_exit = 0.0
        fall = None
        for n in range(int(round(config.SIM_DURATION / H))):
            audit.audited_substep(c, H, ledger)
            w = c.world
            over5 += (np.abs(w.link_lengths() - w.rest) / w.rest)[c.tail_links].max() > 0.05
            if "queue" in groups:
                m = w.limit_violation()[groups["queue"]].min()
                if m < -math.radians(0.5):
                    exits += 1
                    worst_exit = max(worst_exit, -math.degrees(m))
            if c.fallen and fall is None:
                fall = (n + 1) * H
    weight = float(c.world.mass.sum() * config.G)
    return {"cree_J": float(ledger["hors_muscles+"]), "cree_m": float(ledger["hors_muscles+"]) / weight,
            "queue_max": float(ledger["max_tail_error"]), "queue_plus_5_s": over5 * H,
            "sorties_cone": exits, "sortie_max_deg": worst_exit, "os_corps_max": float(ledger["max_length_error"]),
            "hauteur": c.height(), "tombee_a": fall, "vitesse_max": float(ledger["max_speed"])}


def compare(run_dir, gen, index, variants=VARIANTS, log=print):
    """Une créature, toutes les variantes ; la hauteur du moteur tel quel est vérifiée au bit près."""
    ev.use_run_config(run_dir)
    pop, res, _, _ = ev.load_generation(run_dir, gen)
    stored = float(res["height"][index])
    genome = pop.genome(index)
    out = {name: measure(genome, name) for name in variants}
    identical = "tel_quel" not in out or abs(out["tel_quel"]["hauteur"] - stored) <= 1e-9
    if log:
        log(f"diag-projection — {run_dir}, gén. {gen}, n°{index} : hauteur stockée {stored:+.3f} m ; moteur tel quel "
            + ("identique" if identical else "ÉCART"))
        for name, m in out.items():
            log(f"  {name:12s} : créé {m['cree_J']:.2f} J ({100 * m['cree_m']:.2f} cm) ; queue max {100 * m['queue_max']:.1f} %, "
                f"> 5 % pendant {1000 * m['queue_plus_5_s']:.0f} ms ; sorties de cône {m['sorties_cone']} sous-pas "
                f"(max {m['sortie_max_deg']:.0f}°) ; os du corps {100 * m['os_corps_max']:.2f} % ; vitesse max "
                f"{m['vitesse_max']:.1f} m/s ; hauteur {m['hauteur']:+.2f} m ; "
                + (f"tombée à {m['tombee_a']:.2f} s" if m["tombee_a"] else "jamais tombée"))
    return {**out, "identique": identical, "hauteur_stockee": stored}


def population(run_dir, gen, group, variants=VARIANTS, top=50, log=print):
    """Toutes les créatures tombées (group="tombees") ou les `top` meilleures (group="meilleures") d'une génération,
    avec chaque variante : énergie créée, queue, sorties de cône, hauteur contre la hauteur stockée."""
    ev.use_run_config(run_dir)
    pop, res, _, _ = ev.load_generation(run_dir, gen)
    if group == "tombees":
        picks = [int(i) for i in np.flatnonzero(res["fallen"])]
    elif group == "meilleures":
        picks = [int(i) for i in ev.ranking(res["score"])[:top]]
    else:
        raise ValueError("group : tombees ou meilleures")
    t0 = time.perf_counter()
    rows = {name: [] for name in variants}
    identical = True
    for i in picks:
        genome = pop.genome(i)
        for name in variants:
            m = measure(genome, name)
            m["indice"] = i
            m["dh"] = m["hauteur"] - float(res["height"][i])
            rows[name].append(m)
            if name == "tel_quel":
                identical &= abs(m["dh"]) <= 1e-9
    summary = {name: summarize(r) for name, r in rows.items()}
    result = {"run": run_dir, "gen": gen, "groupe": group, "n": len(picks), "identique": identical,
              "variantes": summary, "creatures": rows, "secondes": time.perf_counter() - t0}
    if log:
        for line in population_lines(result):
            log(line)
    return result


def summarize(rows):
    if not rows:
        return {"n": 0}
    cm = np.array([r["cree_m"] for r in rows]) * 100
    q = np.array([r["queue_max"] for r in rows]) * 100
    ex = np.array([r["sorties_cone"] for r in rows])
    dh = np.array([r["dh"] for r in rows])
    worst = rows[int(cm.argmax())]["indice"]
    return {"n": len(rows), "cree_total_J": float(sum(r["cree_J"] for r in rows)), "cree_max_cm": float(cm.max()),
            "cree_plus_5cm": int((cm > 100 * config.AUDIT_MAX_CREATED_HEIGHT).sum()), "pire": worst,
            "queue_max": float(q.max()), "queue_plus_5": int((q > 100 * config.AUDIT_MAX_TAIL_ERROR).sum()),
            "sorties_grimpes": int((ex > 0).sum()), "sorties_total": int(ex.sum()),
            "sortie_max_deg": float(max(r["sortie_max_deg"] for r in rows)),
            "dh_mediane": float(np.median(dh)), "dh_min": float(dh.min()), "dh_max": float(dh.max()),
            "tombees": int(sum(r["tombee_a"] is not None for r in rows))}


def population_lines(r):
    lines = [f"diag-projection — {r['run']}, gén. {r['gen']}, {r['groupe']} : {r['n']} créatures ; moteur tel quel "
             + ("identique au run" if r["identique"] else "ÉCART") + f" ; {r['secondes']:.0f} s"]
    for name, s in r["variantes"].items():
        if not s.get("n"):
            continue
        lines.append(f"  {name:12s} : énergie créée total {s['cree_total_J']:.1f} J, max {s['cree_max_cm']:.2f} cm "
                     f"(n°{s['pire']}), > 5 cm : {s['cree_plus_5cm']} ; queue max {s['queue_max']:.1f} %, > 5 % : "
                     f"{s['queue_plus_5']} ; sorties de cône : {s['sorties_grimpes']} grimpes, {s['sorties_total']} "
                     f"sous-pas, max {s['sortie_max_deg']:.0f}° ; Δh contre le run : médiane {s['dh_mediane']:+.2f} m, "
                     f"min {s['dh_min']:+.2f}, max {s['dh_max']:+.2f} ; tombées {s['tombees']}")
    return lines


def benchmark(run_dir, gen, n=6, rounds=3, variants=VARIANTS, log=print):
    """Coût relatif du moteur scalaire avec chaque variante : `n` meilleures créatures rejouées (sans audit), en
    alternance sur `rounds` tours ; temps médian par variante et rapport au moteur tel quel."""
    ev.use_run_config(run_dir)
    pop, res, _, _ = ev.load_generation(run_dir, gen)
    genomes = [pop.genome(int(i)) for i in ev.ranking(res["score"])[:n]]
    times = {name: [] for name in variants}
    steps = int(round(config.SIM_DURATION / H))
    for name in variants:   # compilation numba hors chronomètre
        with variant(name):
            c = _new_creature(genomes[0])
            for _ in range(10):
                c.substep(H)
    for _ in range(rounds):
        for name in variants:
            with variant(name):
                t0 = time.perf_counter()
                for g in genomes:
                    c = _new_creature(g)
                    for _ in range(steps):
                        c.substep(H)
                times[name].append(time.perf_counter() - t0)
    med = {name: float(np.median(t)) for name, t in times.items()}
    if log:
        base = med.get("tel_quel")
        log(f"diag-projection benchmark — {run_dir}, gén. {gen}, {n} créatures × {rounds} tours (moteur scalaire)")
        for name, t in med.items():
            log(f"  {name:12s} : {t:.2f} s" + (f" (×{t / base:.2f})" if base else "")
                + " ; tours : " + ", ".join(f"{x:.2f}" for x in times[name]))
    return {"secondes": med, "tours": times}
