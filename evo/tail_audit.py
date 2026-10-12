"""Mesures de la queue et des butées du corps (chantier C2) : `joints --tail` et `joints --fallen`.

--tail (sur les grimpes que choisit `joints`, à chaque sous-pas) :
- erreur de longueur de chacun des os de la queue : max, p95, temps au-delà de 1 % et de 5 %, os le plus touché ;
- oscillation numérique contre la butée du cône : δ_k = écart signé (°) de chaque point de queue à l'axe, vu du
  bassin ; alternance au sous-pas n quand les pas δ(n+1) − δ(n) et δ(n) − δ(n−1) sont de signes opposés et dépassent
  tous deux TAIL_CHATTER_MIN_DEG, comptée pendant le contact (|δ| ≥ TAIL_CONE_DEG − TAIL_CHATTER_CONTACT_DEG) ;
- posture : écart maximal à l'axe (médiane, p95), part du temps collée au bord du cône, courbure (écart entre le
  premier et le dernier point) ;
- pénétration des butées par groupe (articulations, pieds, queue) et erreur des os du corps ;
- verdict du critère de repli (config.TAIL_FALLBACK_*, TAIL_CHATTER_*), sur le groupe des meilleures.
--fallen : toutes les créatures tombées d'une génération, rejouées avec l'audit d'énergie (evo/audit.py) : énergie
créée hors muscles et erreur de longueur de la queue, contre les seuils d'audit (AUDIT_MAX_CREATED_HEIGHT,
AUDIT_MAX_TAIL_ERROR).
"""
import math
import time

import numpy as np

import config
from evo import creature as cr
from evo import evolution as ev
from evo import skeleton as sk

ON_BOUND_DEG = 0.1    # « collée au bord du cône » : à moins de 0.1° de τ


def tail_links(creature):
    """Indices des liens de la queue (os PELVIS → TAIL_0 → … → TAIL_11), dans l'ordre de la chaîne."""
    return np.array([k for k, name in enumerate(creature.skel.link_names) if name == "tail"])


def signed_tail_angles(pos):
    """(T, n) écart signé (°) de chaque point de queue à l'axe, vu du bassin (0 = dans le prolongement de la colonne)."""
    P = np.asarray(pos, dtype=float)
    pelvis = P[:, sk.PELVIS]
    back = pelvis - P[:, sk.NECK]
    r = P[:, sk.TAIL_START:] - pelvis[:, None, :]
    u = back[:, None, :]
    return np.degrees(np.arctan2(u[..., 0] * r[..., 1] - u[..., 1] * r[..., 0], np.sum(u * r, axis=-1)))


def chatter(delta, tau_deg, min_step_deg=None, contact_deg=None):
    """Oscillation numérique contre le bord du cône, sur δ (T, n) en degrés.

    Renvoie (part des sous-pas de contact où δ alterne, nombre de sous-pas de contact, amplitude médiane des
    alternances en °). Un mouvement physique ne change de sens qu'à ses rebroussements ; une oscillation numérique
    change de sens presque à chaque sous-pas.
    """
    min_step = config.TAIL_CHATTER_MIN_DEG if min_step_deg is None else min_step_deg
    contact = config.TAIL_CHATTER_CONTACT_DEG if contact_deg is None else contact_deg
    d = np.diff(delta, axis=0)                                  # d[n] = δ(n+1) − δ(n)
    before, after = d[:-1], d[1:]                               # pas avant et après le sous-pas n (1..T−2)
    alt = (before * after < 0) & (np.abs(before) > min_step) & (np.abs(after) > min_step)
    in_contact = np.abs(delta[1:-1]) >= tau_deg - contact
    n_contact = int(in_contact.sum())
    hits = alt & in_contact
    share = float(hits.sum() / n_contact) if n_contact else 0.0
    amp = float(np.median(np.abs(after[hits]))) if hits.any() else 0.0
    return share, n_contact, amp


def limit_penetration(pos, world):
    """Pénétration maximale (°) de chaque groupe de butées sur la grimpe (0 si jamais au-delà)."""
    P = np.asarray(pos, dtype=float)
    a, p, b = world.limit_joints.T
    if len(a) == 0:
        return {}
    ra, rb = P[:, a] - P[:, p], P[:, b] - P[:, p]
    theta = np.arctan2(ra[..., 0] * rb[..., 1] - ra[..., 1] * rb[..., 0], np.sum(ra * rb, axis=-1))
    mid, half = 0.5 * (world.limit_lo + world.limit_hi), 0.5 * (world.limit_hi - world.limit_lo)
    delta = (world.limit_sign * theta - mid + math.pi) % (2.0 * math.pi) - math.pi
    c = half - np.abs(delta)                                    # distance à la borne la plus proche (> 0 dans la plage)
    return {name: float(max(0.0, -np.degrees(c[:, idx].min())))
            for name, idx in cr.limit_groups(len(a)).items()}


def length_errors(pos, world, links):
    """(T, len(links)) erreur relative de longueur des liens `links` à chaque sous-pas."""
    P = np.asarray(pos, dtype=float)
    i, j = world.links[links, 0], world.links[links, 1]
    return np.abs(np.hypot(*(P[:, j] - P[:, i]).transpose(2, 0, 1)) - world.rest[links]) / world.rest[links]


def tail_measures(pos, creature):
    """Mesures de la queue d'une grimpe enregistrée à chaque sous-pas (joint_audit.record)."""
    h = config.DT / config.SUBSTEPS
    tau = config.TAIL_CONE_DEG
    w = creature.world
    tl = tail_links(creature)
    err = length_errors(pos, w, tl)
    worst = err.max(axis=1)
    body = np.setdiff1d(np.arange(len(w.links)), tl)
    delta = signed_tail_angles(pos)
    dev = np.abs(delta).max(axis=1)
    share, n_contact, amp = chatter(delta, tau)
    return {
        "longueur_max": float(err.max()), "longueur_p95": float(np.percentile(worst, 95)),
        "temps_plus_1": float((worst > 0.01).sum() * h), "temps_plus_5": float((worst > 0.05).sum() * h),
        "os_le_plus_touche": int(err.max(axis=0).argmax()),
        "oscillation": share, "sous_pas_contact": n_contact, "oscillation_amplitude": amp,
        "ecart_median": float(np.median(dev)), "ecart_p95": float(np.percentile(dev, 95)),
        "collee": float(np.mean(dev >= tau - ON_BOUND_DEG)),
        "courbure_mediane": float(np.median(np.abs(delta[:, -1] - delta[:, 0]))),
        "penetration_deg": limit_penetration(pos, w),
        "os_corps_max": float(length_errors(pos, w, body).max()),
    }


def tail_group(rows):
    """Agrège les mesures de queue d'un groupe de grimpes, avec les deux tests du critère de repli."""
    q = [r["queue"] for r in rows]
    long_time = config.TAIL_FALLBACK_TIME * config.SIM_DURATION
    stretched = np.mean([m["temps_plus_1"] > long_time for m in q]) if q else 0.0
    chattering = np.mean([m["oscillation"] > config.TAIL_CHATTER_MAX for m in q]) if q else 0.0
    pen = {}
    for m in q:
        for k, v in m["penetration_deg"].items():
            pen[k] = max(pen.get(k, 0.0), v)
    return {
        "n": len(q),
        "longueur_max": max((m["longueur_max"] for m in q), default=0.0),
        "longueur_p95_mediane": float(np.median([m["longueur_p95"] for m in q])) if q else 0.0,
        "grimpes_etirees": float(stretched),
        "oscillation_mediane": float(np.median([m["oscillation"] for m in q])) if q else 0.0,
        "oscillation_max": max((m["oscillation"] for m in q), default=0.0),
        "grimpes_oscillantes": float(chattering),
        "amplitude_mediane": float(np.median([m["oscillation_amplitude"] for m in q])) if q else 0.0,
        "ecart_median": float(np.median([m["ecart_median"] for m in q])) if q else 0.0,
        "ecart_p95": float(np.median([m["ecart_p95"] for m in q])) if q else 0.0,
        "collee": float(np.median([m["collee"] for m in q])) if q else 0.0,
        "courbure_mediane": float(np.median([m["courbure_mediane"] for m in q])) if q else 0.0,
        "penetration_deg": pen,
        "os_corps_max": max((m["os_corps_max"] for m in q), default=0.0),
        "repli_longueur": bool(stretched > config.TAIL_FALLBACK_SHARE),
        "repli_oscillation": bool(chattering > config.TAIL_FALLBACK_SHARE),
    }


def tail_lines(g, verdict=True):
    """Lignes du rapport `--tail` d'un groupe (tail_group)."""
    pen = ", ".join(f"{k} {v:.3f}°" for k, v in g["penetration_deg"].items()) or "aucune butée"
    lines = [
        f"    queue, longueur des os : max {g['longueur_max']:.2%}, p95 médian {g['longueur_p95_mediane']:.3%} ; "
        f"grimpes au-delà de 1 % plus de {config.TAIL_FALLBACK_TIME:.0%} du temps : {g['grimpes_etirees']:.0%}",
        f"    queue, oscillation contre le cône (±{config.TAIL_CONE_DEG:g}°) : médiane {g['oscillation_mediane']:.1%} des "
        f"sous-pas de contact, max {g['oscillation_max']:.1%}, amplitude médiane {g['amplitude_mediane']:.3f}° ; "
        f"grimpes au-delà de {config.TAIL_CHATTER_MAX:.0%} : {g['grimpes_oscillantes']:.0%}",
        f"    queue, posture : écart max à l'axe médian {g['ecart_median']:.1f}°, p95 {g['ecart_p95']:.1f}° ; collée au bord "
        f"{g['collee']:.0%} du temps ; courbure médiane {g['courbure_mediane']:.1f}°",
        f"    pénétration max des butées : {pen} ; os du corps : erreur max {g['os_corps_max']:.2%}",
    ]
    if verdict:
        lines.append("    " + verdict_line(g))
    return lines


def verdict_line(g):
    """« critère de repli : … → garder τ | repli à 30° » pour un groupe (celui des meilleures)."""
    fall_back = g["repli_longueur"] or g["repli_oscillation"]
    return (f"critère de repli : longueur {g['grimpes_etirees']:.0%} des grimpes étirées "
            f"(seuil {config.TAIL_FALLBACK_SHARE:.0%}) ; oscillation {g['grimpes_oscillantes']:.0%} des grimpes "
            f"(seuil {config.TAIL_FALLBACK_SHARE:.0%}) → "
            + ("repli à 30°" if fall_back else f"garder {config.TAIL_CONE_DEG:g}°"))


# ---------------------------------------------------------------------------
# Créatures tombées (décision 4 de Tom, C2)
# ---------------------------------------------------------------------------
def fallen_creature(genome):
    """Audit d'énergie d'une grimpe complète, avec l'erreur de longueur de la queue à chaque sous-pas."""
    from evo import audit

    h = config.DT / config.SUBSTEPS
    c = cr.Creature(genome)
    c.tail_links = np.array([name == "tail" for name in c.skel.link_names])
    ledger = {k: 0.0 for name in audit.STAGES for k in (name, name + "+")}
    ledger.update({"total": 0.0, "schema_gravite": 0.0, "hors_muscles+": 0.0, "max_speed": 0.0,
                   "max_torso_speed": 0.0, "max_length_error": 0.0, "max_tail_error": 0.0, "max_height": -np.inf})
    ledger.update({k: 0.0 for k in audit.LIMIT_KEYS})
    over1 = over5 = 0
    for _ in range(int(round(config.SIM_DURATION / h))):
        audit.audited_substep(c, h, ledger)
        w = c.world
        err = np.abs(w.link_lengths()[c.tail_links] - w.rest[c.tail_links]) / w.rest[c.tail_links]
        worst = err.max()
        over1 += worst > 0.01
        over5 += worst > 0.05
    weight = float(c.world.mass.sum() * config.G)
    return c, {"cree_J": float(ledger["hors_muscles+"]), "cree_m": float(ledger["hors_muscles+"]) / weight,
               "queue_max": float(ledger["max_tail_error"]), "queue_temps_plus_1": over1 * h,
               "queue_temps_plus_5": over5 * h, "os_corps_max": float(ledger["max_length_error"])}


def fallen_audit(run_dir, gen, log=print):
    """Toutes les créatures tombées de la génération `gen` : énergie créée hors muscles et queue, contre les seuils
    d'audit. Hauteur rejouée vérifiée contre la hauteur stockée."""
    ev.use_run_config(run_dir)
    pop, res, _, _ = ev.load_generation(run_dir, gen)
    fallen = np.flatnonzero(res["fallen"])
    t0 = time.perf_counter()
    rows = []
    for i in fallen:
        c, m = fallen_creature(pop.genome(int(i)))
        m.update(indice=int(i), identique=abs(c.height() - float(res["height"][i])) <= 1e-9)
        rows.append(m)
    over_energy = [r for r in rows if r["cree_m"] > config.AUDIT_MAX_CREATED_HEIGHT]
    over_tail = [r for r in rows if r["queue_max"] > config.AUDIT_MAX_TAIL_ERROR]
    result = {"run": run_dir, "gen": gen, "n_tombees": len(rows), "n": len(res["fallen"]),
              "butees_corps": bool(config.JOINT_LIMITS and config.BODY_LIMITS), "cone_deg": config.TAIL_CONE_DEG,
              "creatures": rows, "identique": all(r["identique"] for r in rows),
              "depasse_energie": [r["indice"] for r in over_energy], "depasse_queue": [r["indice"] for r in over_tail],
              "secondes": time.perf_counter() - t0}
    if log:
        for line in fallen_lines(result):
            log(line)
    return result


def fallen_lines(r):
    rows = r["creatures"]
    head = (f"créatures tombées — {r['run']}, gén. {r['gen']} : {r['n_tombees']} sur {r['n']} ; butées du corps "
            + (f"actives (cône ±{r['cone_deg']:g}°)" if r["butees_corps"] else "absentes"))
    if not rows:
        return [head, "  aucune créature tombée"]
    e = np.array([x["cree_J"] for x in rows])
    em = np.array([x["cree_m"] for x in rows])
    q = np.array([x["queue_max"] for x in rows])
    t1 = np.array([x["queue_temps_plus_1"] for x in rows])
    t5 = np.array([x["queue_temps_plus_5"] for x in rows])
    lines = [
        head,
        f"  énergie créée hors muscles : total {e.sum():.2f} J, médiane {np.median(e):.3f} J, max {e.max():.3f} J "
        f"({em.max() * 100:.2f} cm, n°{rows[int(em.argmax())]['indice']}) ; seuil d'audit "
        f"{config.AUDIT_MAX_CREATED_HEIGHT * 100:.0f} cm : {len(r['depasse_energie'])} au-delà",
        f"  queue, longueur des os : max {q.max():.2%} (n°{rows[int(q.argmax())]['indice']}), médiane {np.median(q):.2%} ; "
        f"temps au-delà de 1 % : médiane {np.median(t1) * 1000:.0f} ms, max {t1.max() * 1000:.0f} ms ; au-delà de 5 % : "
        f"médiane {np.median(t5) * 1000:.0f} ms, max {t5.max() * 1000:.0f} ms ; seuil d'audit "
        f"{config.AUDIT_MAX_TAIL_ERROR:.0%} : {len(r['depasse_queue'])} au-delà",
        f"  os du corps : erreur max {max(x['os_corps_max'] for x in rows):.2%}",
        f"  {len(rows)} grimpes rejouées en {r['secondes']:.0f} s ; hauteurs "
        + ("identiques au run" if r["identique"] else "DIFFÉRENTES du run"),
    ]
    if r["depasse_energie"] or r["depasse_queue"]:
        lines.append("  ALERTE : seuil d'audit dépassé par une créature tombée")
    return lines
