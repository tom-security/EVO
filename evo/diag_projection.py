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
from evo import skeleton as sk
from evo import tail_audit as ta

H = config.DT / config.SUBSTEPS
VARIANTS = ("tel_quel", "vitesse_proj", "dissipatif", "passes120")
PASSES = 120
# Butées de queue (candidat (d) du chantier D), substituées à la création de la créature :
# - cone        : celles de la v1 (12 points de queue vus du bassin, dans un cône de ±TAIL_CONE_DEG) ;
# - courbure<β> : un cône de ±β sur le premier segment seulement (NECK, PELVIS, TAIL_0), puis une butée de courbure
#   à chaque jonction (TAIL_{k−1}, TAIL_k, TAIL_{k+1}), angle à ±β de l'alignement. Le pivot est toujours à distance
#   fixe de ses deux voisins : pas de singularité au sommet du cône.
TAILS = {"cone": None, "courbure5": 5.0, "courbure2.5": 2.5, "courbure1": 1.0}
# Sens de parcours des butées de queue dans les passes du solveur : « ordre » (celui du moteur) ou « alterne »
# (racine → bout aux passes paires, bout → racine aux impaires ; evo/diag_alterne.py).
ORDERS = ("ordre", "alterne")
# Enfoncement des butées de queue (°, ≥ 0) : histogramme par grimpe, pour un p95 sur tous les sous-pas d'un groupe.
PEN_EDGES = np.concatenate([np.arange(0.0, 2.0001, 0.05), [3.0, 5.0, 10.0, 20.0, 45.0, 90.0, 180.0]])
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


def curvature_body_limits(beta_deg):
    """Version (d) de creature.body_limits : pieds inchangés, cône de ±β sur le premier segment, courbure ±β ailleurs."""
    original = cr.body_limits

    def body_limits(n_tail=None):
        trip, sign, lo, hi = original(n_tail)
        n = len(trip) - 2
        b = math.radians(beta_deg)
        tail = sk.TAIL_START
        new = [(sk.NECK, sk.PELVIS, tail)]
        new += [((sk.PELVIS if k == 0 else tail + k - 1), tail + k, tail + k + 1) for k in range(n - 1)]
        trip = np.concatenate([trip[:2], np.array(new, dtype=np.int64)])
        lo = np.concatenate([lo[:2], np.full(n, math.pi - b)])
        hi = np.concatenate([hi[:2], np.full(n, math.pi + b)])
        return trip, np.concatenate([sign[:2], np.ones(n)]), lo, hi
    return body_limits


@contextlib.contextmanager
def tail_limits(kind):
    """Substitue les butées de queue `kind` (TAILS) à la création des créatures, le temps du bloc."""
    if kind not in TAILS:
        raise ValueError(f"butées de queue inconnues : {kind} ({', '.join(TAILS)})")
    original = cr.body_limits
    try:
        if TAILS[kind] is not None:
            cr.body_limits = curvature_body_limits(TAILS[kind])
        yield
    finally:
        cr.body_limits = original


@contextlib.contextmanager
def solver_order(kind):
    """Substitue les noyaux à sens de parcours alterné (kind="alterne") le temps du bloc."""
    if kind not in ORDERS:
        raise ValueError(f"ordre inconnu : {kind} ({', '.join(ORDERS)})")
    originals = (physics._link_velocities_numba, physics._project_links_numba)
    try:
        if kind == "alterne":
            from evo import diag_alterne
            physics._link_velocities_numba = diag_alterne.link_velocities_alterne
            physics._project_links_numba = diag_alterne.project_links_alterne
        yield
    finally:
        physics._link_velocities_numba, physics._project_links_numba = originals


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


APEX_M = 0.05          # point de queue (hors le premier) à moins de 5 cm du bassin : sommet du cône
JUMP_DEG = 20.0        # « saut » : un point de queue dont l'angle vu du bassin varie de plus de 20° en un sous-pas
STRETCH_PRE = 0.002    # liens étirés de plus de 0,2 % avant la projection : résolution en vitesse non convergée


def split(name):
    """« projection[:queue] » → (projection, queue) ; queue par défaut : cone (v1). Le sens de parcours éventuel
    (« :alterne ») est lu par split3."""
    proj, tail, _ = split3(name)
    return proj, tail


def split3(name):
    """« projection[:queue[:ordre]] » → (projection, queue, ordre) ; défauts : cone, ordre (le moteur)."""
    parts = name.split(":")
    proj = parts[0]
    tail = parts[1] if len(parts) > 1 and parts[1] else "cone"
    order = parts[2] if len(parts) > 2 and parts[2] else "ordre"
    if proj not in VARIANTS or tail not in TAILS or order not in ORDERS or len(parts) > 3:
        raise ValueError(f"variante inconnue : {name} (projection : {', '.join(VARIANTS)} ; queue : {', '.join(TAILS)} ; "
                         f"ordre : {', '.join(ORDERS)})")
    return proj, tail, order


@contextlib.contextmanager
def configuration(name, record=False):
    """Toute la variante « projection[:queue[:ordre]] », le temps du bloc. L'ordre des solveurs est substitué en
    premier, pour que le report sur la vitesse de la projection enveloppe la projection alternée."""
    proj, tail, order = split3(name)
    with solver_order(order), tail_limits(tail), variant(proj, record=record):
        yield


def measure(genome, name="tel_quel"):
    """Rejeu audité (evo/audit.py) d'une grimpe avec la variante `name` (« projection[:queue] ») : énergie créée hors
    muscles, queue (étirement, pénétration des butées, sauts d'angle, approche du sommet, posture), convergence."""
    with configuration(name, record=True):
        c = _new_creature(genome)
        c.tail_links = np.array([n == "tail" for n in c.skel.link_names])
        ledger = {k: 0.0 for stage in audit.STAGES for k in (stage, stage + "+")}
        ledger.update({"total": 0.0, "schema_gravite": 0.0, "hors_muscles+": 0.0, "max_speed": 0.0,
                       "max_torso_speed": 0.0, "max_length_error": 0.0, "max_tail_error": 0.0, "max_height": -np.inf})
        ledger.update({k: 0.0 for k in audit.LIMIT_KEYS})
        groups = cr.limit_groups(len(c.world.limit_lo)) if len(c.world.limit_lo) else {}
        over5 = exits = apex = jumps = stretched = 0
        worst_exit = pre_max = 0.0
        pen = []
        fall = None
        prev = None
        dev, bend = [], []
        for n in range(int(round(config.SIM_DURATION / H))):
            audit.audited_substep(c, H, ledger)
            w = c.world
            over5 += (np.abs(w.link_lengths() - w.rest) / w.rest)[c.tail_links].max() > 0.05
            if "queue" in groups:
                m = w.limit_violation()[groups["queue"]].min()
                pen.append(max(0.0, -math.degrees(m)))
                if m < -math.radians(0.5):
                    exits += 1
                    worst_exit = max(worst_exit, -math.degrees(m))
            delta = ta.signed_tail_angles(w.pos[None])[0]
            if prev is not None and np.abs((delta - prev + 180.0) % 360.0 - 180.0).max() > JUMP_DEG:
                jumps += 1
            prev = delta
            dev.append(float(np.abs(delta).max()))
            bend.append(float(abs(delta[-1] - delta[0])))
            apex += np.hypot(*(w.pos[sk.TAIL_START + 1:] - w.pos[sk.PELVIS]).T).min() < APEX_M
            pre_max = max(pre_max, LAST["pre_lien"])
            stretched += LAST["pre_lien"] > STRETCH_PRE
            if c.fallen and fall is None:
                fall = (n + 1) * H
    weight = float(c.world.mass.sum() * config.G)
    return {"cree_J": float(ledger["hors_muscles+"]), "cree_m": float(ledger["hors_muscles+"]) / weight,
            "queue_max": float(ledger["max_tail_error"]), "queue_plus_5_s": over5 * H,
            "sorties_cone": exits, "sortie_max_deg": worst_exit, "os_corps_max": float(ledger["max_length_error"]),
            "hauteur": c.height(), "tombee_a": fall, "vitesse_max": float(ledger["max_speed"]),
            "sauts_queue": jumps, "sommet_s": apex * H, "avant_proj_lien_max": pre_max,
            "avant_proj_etire_s": stretched * H, "ecart_median_deg": float(np.median(dev)),
            "ecart_p95_deg": float(np.percentile(dev, 95)), "courbure_mediane_deg": float(np.median(bend)),
            "enfoncement_p95_deg": float(np.percentile(pen, 95)) if pen else 0.0,
            "enfoncement_hist": np.histogram(np.clip(pen, 0.0, 179.999), PEN_EDGES)[0].tolist() if pen else []}


def pooled_percentile(rows, q=95.0):
    """Percentile de l'enfoncement des butées de queue sur tous les sous-pas d'un groupe de grimpes, lu dans les
    histogrammes (borne haute de la classe qui le contient)."""
    hists = [r["enfoncement_hist"] for r in rows if r.get("enfoncement_hist")]
    if not hists:
        return 0.0
    total = np.sum(hists, axis=0)
    cum = np.cumsum(total) / total.sum()
    k = int(np.searchsorted(cum, q / 100.0))
    return float(PEN_EDGES[min(k + 1, len(PEN_EDGES) - 1)])


def compare(run_dir, gen, index, variants=VARIANTS, log=print):
    """Une créature, toutes les variantes ; la hauteur du moteur tel quel est vérifiée au bit près."""
    ev.use_run_config(run_dir)
    pop, res, _, _ = ev.load_generation(run_dir, gen)
    stored = float(res["height"][index])
    genome = pop.genome(index)
    out = {name: measure(genome, name) for name in variants}
    identical = "tel_quel" not in out or abs(out["tel_quel"]["hauteur"] - stored) <= 1e-9
    if log:
        for name, m in out.items():
            log(f"  {name:22s} : sauts de queue {m['sauts_queue']} ; sommet du cône {1000 * m['sommet_s']:.0f} ms ; "
                f"avant projection : liens jusqu'à {100 * m['avant_proj_lien_max']:.2f} %, au-delà de 0,2 % pendant "
                f"{1000 * m['avant_proj_etire_s']:.0f} ms ; posture : écart à l'axe médian {m['ecart_median_deg']:.1f}°, "
                f"p95 {m['ecart_p95_deg']:.1f}°, courbure médiane {m['courbure_mediane_deg']:.1f}°")
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
            if name in ("tel_quel", "tel_quel:cone"):
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
            "tombees": int(sum(r["tombee_a"] is not None for r in rows)),
            "sauts_grimpes": int(sum(r.get("sauts_queue", 0) > 0 for r in rows)),
            "sauts_total": int(sum(r.get("sauts_queue", 0) for r in rows)),
            "sommet_grimpes": int(sum(r.get("sommet_s", 0) > 0 for r in rows)),
            "avant_proj_lien_max": float(max(r.get("avant_proj_lien_max", 0) for r in rows)),
            "avant_proj_etire_s_moyen": float(np.mean([r.get("avant_proj_etire_s", 0) for r in rows])),
            "ecart_median_deg": float(np.median([r.get("ecart_median_deg", 0) for r in rows])),
            "ecart_p95_deg": float(np.median([r.get("ecart_p95_deg", 0) for r in rows])),
            "courbure_mediane_deg": float(np.median([r.get("courbure_mediane_deg", 0) for r in rows])),
            "enfoncement_p95_deg": pooled_percentile(rows), "enfoncement_max_deg": float(max(r["sortie_max_deg"] for r in rows))}


def population_lines(r):
    lines = [f"diag-projection — {r['run']}, gén. {r['gen']}, {r['groupe']} : {r['n']} créatures ; moteur tel quel "
             + ("identique au run" if r["identique"] else "ÉCART") + f" ; {r['secondes']:.0f} s"]
    for name, s in r["variantes"].items():
        if not s.get("n"):
            continue
        lines.append(f"  {name:22s} : énergie créée total {s['cree_total_J']:.1f} J, max {s['cree_max_cm']:.2f} cm "
                     f"(n°{s['pire']}), > 5 cm : {s['cree_plus_5cm']} ; queue max {s['queue_max']:.1f} %, > 5 % : "
                     f"{s['queue_plus_5']} ; pénétration des butées de queue : {s['sorties_grimpes']} grimpes, "
                     f"{s['sorties_total']} sous-pas, max {s['sortie_max_deg']:.0f}° ; sauts de queue : "
                     f"{s['sauts_grimpes']} grimpes, {s['sauts_total']} sous-pas ; sommet du cône : {s['sommet_grimpes']} "
                     f"grimpes ; Δh contre le run : médiane {s['dh_mediane']:+.2f} m, min {s['dh_min']:+.2f}, "
                     f"max {s['dh_max']:+.2f} ; tombées {s['tombees']}")
        lines.append(f"  {'':22s}   avant projection : liens jusqu'à {100 * s['avant_proj_lien_max']:.2f} %, au-delà de "
                     f"0,2 % en moyenne {1000 * s['avant_proj_etire_s_moyen']:.0f} ms par grimpe ; posture (médianes) : "
                     f"écart à l'axe {s['ecart_median_deg']:.1f}°, p95 {s['ecart_p95_deg']:.1f}°, courbure "
                     f"{s['courbure_mediane_deg']:.1f}° ; enfoncement des butées de queue : p95 ≤ "
                     f"{s['enfoncement_p95_deg']:.2f}°, max {s['enfoncement_max_deg']:.1f}°")
    return lines


def benchmark(run_dir, gen, n=6, rounds=3, variants=VARIANTS, log=print):
    """Coût relatif du moteur scalaire avec chaque variante (« projection[:queue] ») : `n` meilleures créatures
    rejouées (sans audit), en alternance sur `rounds` tours ; temps médian et rapport à la première variante."""
    ev.use_run_config(run_dir)
    pop, res, _, _ = ev.load_generation(run_dir, gen)
    genomes = [pop.genome(int(i)) for i in ev.ranking(res["score"])[:n]]
    times = {name: [] for name in variants}
    steps = int(round(config.SIM_DURATION / H))

    both = configuration

    for name in variants:   # compilation numba hors chronomètre
        with both(name):
            c = _new_creature(genomes[0])
            for _ in range(10):
                c.substep(H)
    for _ in range(rounds):
        for name in variants:
            with both(name):
                t0 = time.perf_counter()
                for g in genomes:
                    c = _new_creature(g)
                    for _ in range(steps):
                        c.substep(H)
                times[name].append(time.perf_counter() - t0)
    med = {name: float(np.median(t)) for name, t in times.items()}
    if log:
        base = med[variants[0]]
        log(f"diag-projection benchmark — {run_dir}, gén. {gen}, {n} créatures × {rounds} tours (moteur scalaire)")
        for name, t in med.items():
            log(f"  {name:22s} : {t:.2f} s (×{t / base:.2f}) ; tours : " + ", ".join(f"{x:.2f}" for x in times[name]))
    return {"secondes": med, "tours": times}


def benchmark_batch(run_dir, gen, tails=tuple(TAILS), rounds=3, log=print):
    """Coût relatif de l'évaluateur batché (celui de l'entraînement) avec chaque jeu de butées de queue : les 500 enfants
    de la génération, en alternance. Les variantes de projection n'existent pas dans le noyau batché (lecture seule)."""
    from evo import batch

    ev.use_run_config(run_dir)
    pop, _, _, _ = ev.load_generation(run_dir, gen)
    genomes = [pop.genome(i) for i in range(len(pop.period) // 2, len(pop.period))]
    packs = {}
    for kind in tails:
        with tail_limits(kind):
            packs[kind] = batch.pack(genomes)
    with tail_limits(tails[0]):
        batch.evaluate(genomes[:4])                                  # compilation numba hors chronomètre
    times = {kind: [] for kind in tails}
    for _ in range(rounds):
        for kind in tails:
            t0 = time.perf_counter()
            batch.evaluate(genomes, packed=packs[kind])
            times[kind].append(time.perf_counter() - t0)
    med = {kind: float(np.median(t)) for kind, t in times.items()}
    if log:
        base = med[tails[0]]
        log(f"diag-projection benchmark batché — {run_dir}, gén. {gen}, {len(genomes)} créatures × {rounds} tours")
        for kind, t in med.items():
            log(f"  {kind:12s} : {t:.2f} s (×{t / base:.2f}) ; tours : " + ", ".join(f"{x:.2f}" for x in times[kind]))
    return {"secondes": med, "tours": times}
