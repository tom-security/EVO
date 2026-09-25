"""Commande `joints` (chantier B) : angles articulaires réels des créatures entraînées.

Avant B2, le moteur n'avait aucune butée d'angle entre deux os ; depuis, il applique config.JOINT_LIMITS_DEG
aux runs entraînés avec JOINT_LIMITS (les runs plus anciens se rejouent sans). Cet audit rejoue des créatures
d'un run (moteur scalaire, config du run, hauteur vérifiée au bit près), relève à chaque sous-pas l'angle
anatomique des 8 articulations musclées et le compare aux butées : diagnostic de B1
(docs/chantier_b_diagnostic.md), avant/après de B2 ; --energy ajoute les sauts d'énergie aux butées.

Conventions (vue de dessus sur le mur, gauche et droite en miroir, ordre des articulations de creature.JOINTS) :
- épaule, hanche : α = angle de l'humérus (du fémur) depuis l'axe latéral du corps, prolongement de la
  clavicule (du demi-bassin) ; + = protraction (vers la tête), − = rétraction (vers la queue) ; ±90° = os
  parallèle à la colonne : au-delà, il passe du côté de l'axe du corps.
- coude, genou : β = flexion (0 = membre tendu) ; + = pli naturel, celui du repos (avant-bras tourné vers la
  tête, tibia tourné vers la queue) ; − = pli à l'envers.
Ce sont les φ du contrôleur (Creature.joint_phi) à une constante près, l'angle de repos (rest_angles()).
Les angles sont déroulés dans le temps : un tour complet d'une articulation se voit (max − min > 360°).
"""
import json
import os
import time

import numpy as np

import config
from evo import creature as cr
from evo import evolution as ev
from evo import skeleton as sk

KINDS = cr.JOINT_TYPES       # ("épaule", "coude", "hanche", "genou")
# (côté, épaule, coude, main, hanche, genou, pied) : côté −1 à gauche, +1 à droite (mesure en miroir)
_SIDES = ((-1, sk.L_SHOULDER, sk.L_ELBOW, sk.L_HAND, sk.L_HIP, sk.L_KNEE, sk.L_FOOT),
          (+1, sk.R_SHOULDER, sk.R_ELBOW, sk.R_HAND, sk.R_HIP, sk.R_KNEE, sk.R_FOOT))
LIMB_POINTS = ("coude", "main", "genou", "pied")
# Ceintures : angles colonne–clavicule et colonne–demi-bassin, figés par les BRACES (§2.2).
_GIRDLES = ((sk.L_SHOULDER, sk.NECK, sk.PELVIS), (sk.R_SHOULDER, sk.NECK, sk.PELVIS),
            (sk.L_HIP, sk.PELVIS, sk.NECK), (sk.R_HIP, sk.PELVIS, sk.NECK))
HEIGHT_TOLERANCE = 1e-9      # hauteur rejouée contre hauteur stockée (m), comme Replay
# Au-delà d'une butée = de plus de 1e-6° : en dessous, c'est l'arrondi flottant d'un angle posé sur la borne (une
# cible de génome ramenée sur la butée par une mutation, une articulation au contact).
ANGLE_TOLERANCE_DEG = 1e-6


def _signed(u, v):
    """Angle signé (rad) de u vers v, sur le dernier axe."""
    return np.arctan2(u[..., 0] * v[..., 1] - u[..., 1] * v[..., 0], np.sum(u * v, axis=-1))


def _series(pos):
    P = np.asarray(pos, dtype=float)
    return (P[None], True) if P.ndim == 2 else (P, False)


def rest_angles():
    """Angle anatomique (°) de chaque type d'articulation dans la posture de repos (config.REST_POSE_DEG)."""
    return cr.anatomical_rest_deg()


def rest_offsets():
    """(8,) angle anatomique − φ (°), dans l'ordre de creature.JOINTS."""
    rest = rest_angles()
    return np.array([rest[k] for _ in range(2) for k in KINDS])


def target_range():
    """Plage actuelle des cibles du génome (repos ± TARGET_RANGE_DEG), en angles anatomiques (°)."""
    return {k: (r - config.TARGET_RANGE_DEG, r + config.TARGET_RANGE_DEG) for k, r in rest_angles().items()}


def anatomical_angles(pos):
    """pos : (T, P, 2) positions successives, ou (P, 2) → (T, 8) (ou (8,)) angles anatomiques (°), déroulés."""
    P, single = _series(pos)
    neck, pelvis = P[:, sk.NECK], P[:, sk.PELVIS]
    cols = []
    for s, SH, EL, HA, HI, KN, FO in _SIDES:
        sh, el, ha, hi, kn, fo = (P[:, k] for k in (SH, EL, HA, HI, KN, FO))
        cols += [s * _signed(sh - neck, el - sh), s * _signed(el - sh, ha - el),
                 s * _signed(hi - pelvis, kn - hi), -s * _signed(kn - hi, fo - kn)]
    A = np.degrees(np.unwrap(np.stack(cols, axis=1), axis=0))
    return A[0] if single else A


def midline_distances(pos):
    """(T, 2, 4) distance (m) du coude, de la main, du genou et du pied à l'axe de la colonne, positive du côté
    du membre : négative, le point est passé de l'autre côté du corps."""
    P, single = _series(pos)
    pelvis = P[:, sk.PELVIS]
    e = P[:, sk.NECK] - pelvis
    e = e / np.linalg.norm(e, axis=1)[:, None]
    out = np.empty((len(P), 2, len(LIMB_POINTS)))
    for i, (s, SH, EL, HA, HI, KN, FO) in enumerate(_SIDES):
        for j, k in enumerate((EL, HA, KN, FO)):
            r = P[:, k] - pelvis
            out[:, i, j] = -s * (e[:, 0] * r[:, 1] - e[:, 1] * r[:, 0])
    return out[0] if single else out


def _segments_cross(p1, p2, p3, p4):
    def orient(a, b, c):
        return (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0])
    return (orient(p3, p4, p1) * orient(p3, p4, p2) < 0) & (orient(p1, p2, p3) * orient(p1, p2, p4) < 0)


def limb_crossings(pos):
    """(même côté, gauche/droite) : part des instants où un segment de membre en croise un autre, bras contre
    jambe du même côté, ou membre gauche contre membre droit. Le modèle n'a pas de collision entre segments."""
    P, _ = _series(pos)
    limbs = {}
    for name, (s, SH, EL, HA, HI, KN, FO) in zip("GD", _SIDES):
        limbs[name + "bras"] = ((SH, EL), (EL, HA))
        limbs[name + "jambe"] = ((HI, KN), (KN, FO))

    def cross(a, b):
        hit = np.zeros(len(P), bool)
        for i, j in limbs[a]:
            for k, m in limbs[b]:
                hit |= _segments_cross(P[:, i], P[:, j], P[:, k], P[:, m])
        return hit

    same = cross("Gbras", "Gjambe") | cross("Dbras", "Djambe")
    left_right = (cross("Gbras", "Dbras") | cross("Gjambe", "Djambe")
                  | cross("Gbras", "Djambe") | cross("Dbras", "Gjambe"))
    return float(same.mean()), float(left_right.mean())


def girdle_drift(pos):
    """Écart maximal (°) des angles des ceintures à leur valeur initiale (0 si les BRACES les tiennent)."""
    P, _ = _series(pos)
    drift = 0.0
    for a, p, b in _GIRDLES:
        x = np.degrees(np.unwrap(_signed(P[:, a] - P[:, p], P[:, b] - P[:, p])))
        drift = max(drift, float(np.max(np.abs(x - x[0]))))
    return drift


def tail_swing(pos):
    """(min, max) (°) de l'angle entre la colonne et le premier segment de queue, déroulé : la queue est libre."""
    P, _ = _series(pos)
    pelvis = P[:, sk.PELVIS]
    x = np.degrees(np.unwrap(_signed(P[:, sk.NECK] - pelvis, P[:, sk.TAIL_START] - pelvis)))
    return float(x.min()), float(x.max())


def joint_stats(angles):
    """Par type d'articulation, sur une ou plusieurs grimpes (liste de (T, 8)), côtés gauche et droit réunis :
    extrêmes, percentiles 1–99 %, part du temps hors butées (sous le min, au-dessus du max), excès médian quand
    on est hors butées (au-delà de ANGLE_TOLERANCE_DEG), pénétration max, part du temps à plus de 0.5° et de 10°
    au-delà, part des grimpes avec un tour complet."""
    out = {}
    for t, kind in enumerate(KINDS):
        lo, hi = config.JOINT_LIMITS_DEG[kind]
        per = [a[:, [t, 4 + t]] for a in angles]
        x = np.concatenate([a.ravel() for a in per])
        excess = np.where(x < lo, lo - x, np.where(x > hi, x - hi, 0.0))
        beyond = excess > ANGLE_TOLERANCE_DEG
        lo, hi = lo - ANGLE_TOLERANCE_DEG, hi + ANGLE_TOLERANCE_DEG
        out[kind] = {
            "min": float(x.min()), "max": float(x.max()),
            "p1": float(np.percentile(x, 1)), "p99": float(np.percentile(x, 99)),
            "hors_butees": float(beyond.mean()), "sous_min": float((x < lo).mean()),
            "au_dessus_max": float((x > hi).mean()),
            "exces_median": float(np.median(excess[beyond])) if beyond.any() else 0.0,
            "exces_max": float(excess.max()),
            "plus_de_05": float((excess > 0.5).mean()),   # au-delà du critère de pénétration de B2
            "plus_de_10": float((excess > 10.0).mean()),
            "tour_complet": float(np.mean([np.any(np.ptp(a, axis=0) > 360.0) for a in per])),
        }
    return out


def _on_bound(x, lo, hi):
    return (np.abs(x - lo) <= ANGLE_TOLERANCE_DEG) | (np.abs(x - hi) <= ANGLE_TOLERANCE_DEG)


def targets_out_of_bounds(pop, on_bound=False):
    """Part des cibles du génome (toute la population, K poses × 2 côtés) hors des butées, par type ;
    on_bound : part des cibles posées sur une butée (à ANGLE_TOLERANCE_DEG près)."""
    T = np.degrees(pop.targets) + rest_offsets()          # (N, K, 8) en angles anatomiques
    out = {}
    for t, kind in enumerate(KINDS):
        lo, hi = config.JOINT_LIMITS_DEG[kind]
        x = T[:, :, [t, 4 + t]]
        hit = _on_bound(x, lo, hi) if on_bound else ((x < lo - ANGLE_TOLERANCE_DEG) | (x > hi + ANGLE_TOLERANCE_DEG))
        out[kind] = float(np.mean(hit))
    return out


def use_run_config(run_dir):
    """Config du run (comme Replay) : mêmes constantes qu'à l'entraînement."""
    ev.use_run_config(run_dir)


def record(genome):
    """Rejoue `genome` SIM_DURATION s avec le moteur scalaire : positions à chaque sous-pas, créature finale."""
    c = cr.Creature(genome)
    h = config.DT / config.SUBSTEPS
    n = int(round(config.SIM_DURATION / h))
    P = np.empty((n + 1, len(c.world.pos), 2))
    P[0] = c.world.pos
    for k in range(1, n + 1):
        c.substep(h)
        P[k] = c.world.pos
    return P, c


def energy_at_limits(genome):
    """Audit d'énergie (evo/audit.py) de la grimpe : énergie créée hors muscles par sous-pas, selon que des
    butées s'y engagent, restent actives ou non (max et somme, J), et son équivalent hauteur (m)."""
    from evo import audit  # import tardif : rejeu étape par étape, plus lent

    c, ledger = audit.audit(genome, duration=config.SIM_DURATION)
    weight = float(c.world.mass.sum() * config.G)
    out = {k: float(ledger[k]) for k in audit.LIMIT_KEYS}
    out.update(cree_hors_muscles=float(ledger["hors_muscles+"]), poids=weight,
               saut_engagement_max_m=float(ledger["saut_engagement_max"]) / weight,
               liens_contacts_hausses=float(ledger["liens_contacts+"]),
               projection=float(ledger["projection_sol"]), projection_hausses=float(ledger["projection_sol+"]))
    return out


def audit_creature(genome, stored_height=None):
    """(ligne de mesures, angles (T, 8)) d'une grimpe complète."""
    P, c = record(genome)
    A = anatomical_angles(P)
    mid = midline_distances(P)
    same, left_right = limb_crossings(P)
    row = {
        "hauteur": c.height(), "au_sol": bool(c.fallen),
        "identique": stored_height is None or abs(c.height() - stored_height) <= HEIGHT_TOLERANCE,
        "articulations": joint_stats([A]),
        "axe_traverse": {p: float(np.mean(mid[:, :, j] < 0)) for j, p in enumerate(LIMB_POINTS)},
        "croisements": {"meme_cote": same, "gauche_droite": left_right},
        "ceintures_deg": girdle_drift(P), "queue_deg": tail_swing(P),
    }
    return row, A


def audit(run_dir, gen=None, top=1, sample=0, energy=False, log=print):
    """Rejoue les `top` meilleures créatures d'une génération (et `sample` tirées au hasard) et mesure leurs angles ;
    energy : audit d'énergie de chacune en plus (sauts au moment où une butée s'engage)."""
    use_run_config(run_dir)
    gens = ev.saved_generations(run_dir)
    if not gens:
        raise FileNotFoundError(f"aucune génération sauvegardée dans {run_dir}")
    gen = gens[-1] if gen is None else gen
    pop, res, _, _ = ev.load_generation(run_dir, gen)
    order = ev.ranking(res["score"])
    rank_of = np.empty(len(order), dtype=int)
    rank_of[order] = np.arange(1, len(order) + 1)
    picks = {"meilleures": [int(i) for i in order[:top]]}
    if sample:
        rng = np.random.default_rng(0)
        picks["hasard"] = [int(i) for i in rng.choice(len(order), size=min(sample, len(order)), replace=False)]
    t0 = time.perf_counter()
    rows, groups = [], {}
    for group, indices in picks.items():
        angles = []
        for i in indices:
            row, A = audit_creature(pop.genome(i), float(res["height"][i]))
            row.update(groupe=group, indice=i, rang=int(rank_of[i]))
            if energy:
                row["energie"] = energy_at_limits(pop.genome(i))
            rows.append(row)
            angles.append(A)
        groups[group] = {"n": len(indices), "articulations": joint_stats(angles),
                         "au_sol": float(np.mean([r["au_sol"] for r in rows if r["groupe"] == group]))}
    result = {
        "run": run_dir, "graine": os.path.basename(os.path.normpath(run_dir)), "gen": gen,
        "butees_deg": {k: list(v) for k, v in config.JOINT_LIMITS_DEG.items()},
        "butees_moteur": bool(config.JOINT_LIMITS),
        "repos_deg": rest_angles(), "plage_cibles_deg": target_range(),
        "creatures": rows, "groupes": groups, "cibles_hors_butees": targets_out_of_bounds(pop),
        "cibles_sur_butee": targets_out_of_bounds(pop, on_bound=True),
        "identique": all(r["identique"] for r in rows), "secondes": time.perf_counter() - t0,
    }
    if log:
        for line in report_lines(result):
            log(line)
    return result


def report_lines(result):
    """Tableau lisible : une ligne par créature, puis les groupes et les cibles du génome."""
    lims = ", ".join(f"{k} [{lo:+.0f}, {hi:+.0f}]" for k, (lo, hi) in result["butees_deg"].items())
    engine = "appliquées par le moteur" if result["butees_moteur"] else "non appliquées par le moteur (run d'avant B2)"
    lines = [f"angles articulaires — graine {result['graine']}, gén. {result['gen']} ; butées (°) : {lims}, {engine}",
             "  min..max (°), part du temps hors butées ; côtés gauche et droit réunis"]
    for r in result["creatures"]:
        cells = " | ".join(f"{k} {d['min']:+5.0f}..{d['max']:+5.0f} {d['hors_butees']:4.0%}"
                           + (" (tours)" if d["tour_complet"] else "")
                           for k, d in r["articulations"].items())
        axis = " ".join(f"{p} {v:.0%}" for p, v in r["axe_traverse"].items())
        status = "" if r["identique"] else " ÉCART DE HAUTEUR"
        if "energie" in r:
            e = r["energie"]
            status += (f" | énergie : {int(e['butees_engagements'])} engagements, saut max {e['saut_engagement_max']:.2e} J"
                       f" ({e['saut_engagement_max_m'] * 1000:.2f} mm), sans butée {e['saut_libre_max']:.2e} J,"
                       f" créé hors muscles {e['cree_hors_muscles']:.2e} J")
        lines.append(f"  {r['groupe']:10s} rang {r['rang']:4d} (n°{r['indice']}) h {r['hauteur']:+6.1f} m | {cells} | "
                     f"axe traversé : {axis} | croisements G/D {r['croisements']['gauche_droite']:.0%}{status}")
    for name, g in result["groupes"].items():
        cells = " | ".join(f"{k} {d['hors_butees']:4.0%} (sous {d['sous_min']:.0%}, au-dessus {d['au_dessus_max']:.0%}, "
                           f"excès médian {d['exces_median']:.0f}°, max {d['exces_max']:.2f}°, tours {d['tour_complet']:.0%})"
                           for k, d in g["articulations"].items())
        lines.append(f"  groupe {name} ({g['n']} créatures, au sol {g['au_sol']:.0%}) : {cells}")
    lines.append("  cibles du génome hors butées (toute la population) : "
                 + ", ".join(f"{k} {v:.0%}" for k, v in result["cibles_hors_butees"].items())
                 + " ; posées sur une butée : "
                 + ", ".join(f"{k} {v:.1%}" for k, v in result["cibles_sur_butee"].items()))
    lines.append(f"  {len(result['creatures'])} grimpes rejouées en {result['secondes']:.0f} s ; hauteurs "
                 + ("identiques au run" if result["identique"] else "DIFFÉRENTES du run"))
    return lines


def export(result, out_dir):
    """Écrit les mesures en JSON dans out_dir ; renvoie le chemin."""
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"angles_s{result['graine']}_g{result['gen']}.json")
    with open(path, "w") as fh:
        json.dump(result, fh, indent=1, ensure_ascii=False)
    return path
