"""Commande `diag-projection` (diagnostic du chantier D proposé, lecture seule) : rejoue une créature avec le moteur tel
quel puis avec la variante « vitesse_proj » (toute correction de position de la projection est reportée sur la vitesse,
v += Δp/h), substituée le temps de la commande seulement : le moteur du dépôt n'est pas modifié.

Compare l'énergie créée hors muscles, l'étirement de la queue et les sorties du cône de queue. La variante change la
dynamique : sa hauteur n'a pas à égaler la hauteur stockée ; celle du moteur tel quel, si (contrôle au bit près).
"""
import math

import numpy as np

import config
from evo import audit
from evo import creature as cr
from evo import evolution as ev
from evo import physics

H = config.DT / config.SUBSTEPS


def _project_velocity(original):
    def project(world):
        before = world.pos.copy()
        original(world)
        world.vel += (world.pos - before) / H
    return project


def measure(genome, variant=False):
    original = physics.project_links
    if variant:
        physics.project_links = _project_velocity(original)
    try:
        c = cr.Creature(genome)
        c.tail_links = np.array([n == "tail" for n in c.skel.link_names])
        ledger = {k: 0.0 for name in audit.STAGES for k in (name, name + "+")}
        ledger.update({"total": 0.0, "schema_gravite": 0.0, "hors_muscles+": 0.0, "max_speed": 0.0,
                       "max_torso_speed": 0.0, "max_length_error": 0.0, "max_tail_error": 0.0, "max_height": -np.inf})
        ledger.update({k: 0.0 for k in audit.LIMIT_KEYS})
        groups = cr.limit_groups(len(c.world.limit_lo)) if len(c.world.limit_lo) else {}
        over5 = exits = 0
        worst_exit = 0.0
        for _ in range(int(round(config.SIM_DURATION / H))):
            audit.audited_substep(c, H, ledger)
            w = c.world
            over5 += (np.abs(w.link_lengths() - w.rest) / w.rest)[c.tail_links].max() > 0.05
            if "queue" in groups:
                m = w.limit_violation()[groups["queue"]].min()
                if m < -math.radians(0.5):
                    exits += 1
                    worst_exit = max(worst_exit, -math.degrees(m))
    finally:
        physics.project_links = original
    weight = float(c.world.mass.sum() * config.G)
    return {"cree_J": float(ledger["hors_muscles+"]), "cree_m": float(ledger["hors_muscles+"]) / weight,
            "queue_max": float(ledger["max_tail_error"]), "queue_plus_5_s": over5 * H,
            "sorties_cone": exits, "sortie_max_deg": worst_exit, "os_corps_max": float(ledger["max_length_error"]),
            "hauteur": c.height(), "vitesse_max": float(ledger["max_speed"])}


def compare(run_dir, gen, index, log=print):
    ev.use_run_config(run_dir)
    pop, res, _, _ = ev.load_generation(run_dir, gen)
    stored = float(res["height"][index])
    genome = pop.genome(index)
    now, variant = measure(genome), measure(genome, variant=True)
    identical = abs(now["hauteur"] - stored) <= 1e-9
    if log:
        log(f"diag-projection — {run_dir}, gén. {gen}, n°{index} : hauteur stockée {stored:+.3f} m ; moteur tel quel "
            + ("identique" if identical else "ÉCART"))
        for name, m in (("tel quel", now), ("vitesse_proj", variant)):
            log(f"  {name:12s} : créé {m['cree_J']:.2f} J ({100 * m['cree_m']:.2f} cm) ; queue max {100 * m['queue_max']:.1f} %, "
                f"> 5 % pendant {1000 * m['queue_plus_5_s']:.0f} ms ; sorties de cône {m['sorties_cone']} sous-pas "
                f"(max {m['sortie_max_deg']:.0f}°) ; os du corps {100 * m['os_corps_max']:.2f} % ; vitesse max "
                f"{m['vitesse_max']:.1f} m/s ; hauteur {m['hauteur']:+.2f} m")
    return {"tel_quel": now, "vitesse_proj": variant, "identique": identical}
