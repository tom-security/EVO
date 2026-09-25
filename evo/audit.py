"""Audit d'énergie d'une créature : quel mécanisme ajoute ou retire de l'énergie ?

On rejoue `Creature.substep` étape par étape (mêmes fonctions, même ordre que
`physics.substep`) et on mesure la variation d'énergie mécanique E = cinétique +
potentielle à chaque étape. Seuls les muscles ont le droit d'en ajouter.

- Étapes « vitesse » (changent l'énergie cinétique) : gravité, muscles (Contract),
  Hold, liens + contacts sol (Link, dont le biais de Baumgarte), second Hold.
- Étapes « position » (changent l'énergie potentielle) : Movement, projection des liens
  + remontée au niveau du sol.
La gravité étant conservative, « gravité + Movement » ne fait que l'erreur de schéma
(Euler semi-implicite) ; on l'isole en recalculant ce qu'aurait donné Movement sans les
autres étapes de vitesse.

Butées articulaires (B2) : l'énergie créée hors muscles de chaque sous-pas est aussi classée selon
l'état des butées — sous-pas où au moins une butée s'engage (entre dans le solveur), sous-pas où des
butées restent actives, sous-pas sans butée — avec le maximum et la somme de chaque classe : un saut au
moment où une butée s'engage se voit même si le bilan sur 10 s est bon.
"""
import numpy as np

import config
from evo import creature as cr
from evo import physics
from evo import skeleton as sk

STAGES = ("gravite", "muscles", "hold", "liens_contacts", "hold2", "mouvement", "projection_sol")
# énergie créée hors muscles d'un sous-pas selon l'état des butées (max et somme, J)
LIMIT_CLASSES = ("engagement", "contact", "libre")
LIMIT_KEYS = (("butees_engagements", "butees_sous_pas_engagement", "engagement_liens_ke_max",
               "engagement_projection_pe_max")
              + tuple(f"saut_{k}_{m}" for k in LIMIT_CLASSES for m in ("max", "somme")))


def _ke(w):
    return w.kinetic_energy()


def _pe(w):
    return w.potential_energy()


def audited_substep(c, h, ledger):
    """Même calcul que Creature.substep, avec la variation d'énergie de chaque étape."""
    w = c.world
    pose = c.current_pose()
    if pose != c.pose_index:
        c.apply_holds(pose)
        c.pose_index = pose
    c.control(pose)

    def stage(name, fn, energy):
        before = energy(w)
        fn()
        delta = energy(w) - before
        ledger[name] += delta
        ledger[name + "+"] += max(delta, 0.0)
        return delta

    e0 = _ke(w) + _pe(w)
    stage("gravite", lambda: physics.gravity(w, h), _ke)
    muscles = stage("muscles", lambda: physics.contract(w, h), _ke)
    if w.damping > 0.0:
        w.vel *= max(0.0, 1.0 - w.damping * h)
    stage("hold", lambda: physics.hold(w), _ke)
    links = stage("liens_contacts", lambda: physics.link(w, h), _ke)
    stage("hold2", lambda: physics.hold(w), _ke)
    stage("mouvement", lambda: physics.movement(w, h), _pe)
    projection = stage("projection_sol", lambda: physics.project_links(w), _pe)
    w.t += h
    # Part purement « schéma de la gravité » : ΔKE(gravité) + ΔPE(Movement) si seule la
    # gravité avait agi = −½·m·g²·h² par point libre (toujours négative).
    free = ~w.held
    ledger["schema_gravite"] += float(np.sum(-0.5 * w.mass[free] * (w.g * h) ** 2))
    residual = (_ke(w) + _pe(w)) - e0
    ledger["total"] += residual
    # Énergie apparue sans les muscles pendant ce sous-pas (0 si le sous-pas en a perdu).
    created = max(residual - muscles, 0.0)
    ledger["hors_muscles+"] += created
    # ... classée selon les butées : engagement (une butée entre dans le solveur), contact maintenu, libre
    active = w.limit_active
    previous = getattr(c, "limit_previous", None)
    engaged = int(np.sum(active & ~previous)) if previous is not None else int(np.sum(active))
    c.limit_previous = active.copy()
    kind = "engagement" if engaged else ("contact" if active.any() else "libre")
    ledger[f"saut_{kind}_max"] = max(ledger[f"saut_{kind}_max"], created)
    ledger[f"saut_{kind}_somme"] += created
    if engaged:
        ledger["butees_engagements"] += engaged
        ledger["butees_sous_pas_engagement"] += 1
        ledger["engagement_liens_ke_max"] = max(ledger["engagement_liens_ke_max"], links)
        ledger["engagement_projection_pe_max"] = max(ledger["engagement_projection_pe_max"], projection)

    if config.ENERGY_MODE == "power":
        raise NotImplementedError("audit écrit pour ENERGY_MODE = 'torque'")
    c.effort += float(np.sum(np.abs(c.activation))) * h
    if not c.fallen and np.any(w.pos[c.body_points, 1] <= config.GROUND_Y + config.FALL_CONTACT_EPS):
        c.fallen = True
        if config.FALL_DISABLES_HOLD:
            w.held[:] = False
    c.t += h
    # Plausibilité : vitesses max (points du corps, torse) et erreur de longueur max.
    speeds = np.hypot(w.vel[c.body_points, 0], w.vel[c.body_points, 1])
    ledger["max_speed"] = max(ledger["max_speed"], float(speeds.max()))
    torso = 0.5 * (w.vel[sk.NECK] + w.vel[sk.PELVIS])
    ledger["max_torso_speed"] = max(ledger["max_torso_speed"], float(np.hypot(*torso)))
    err = np.abs(w.link_lengths() - w.rest) / w.rest
    tail = c.tail_links
    ledger["max_length_error"] = max(ledger["max_length_error"], float(err[~tail].max()))
    ledger["max_tail_error"] = max(ledger["max_tail_error"], float(err[tail].max()))
    ledger["max_height"] = max(ledger["max_height"], c.height())


def audit(genome, duration=10.0, start_height=None):
    """Rejoue `genome` et renvoie (créature, bilan d'énergie en J)."""
    h = config.DT / config.SUBSTEPS
    c = cr.Creature(genome, start_height=start_height)
    c.tail_links = np.array([name == "tail" for name in c.skel.link_names])
    ledger = {k: 0.0 for name in STAGES for k in (name, name + "+")}
    ledger.update({"total": 0.0, "schema_gravite": 0.0, "hors_muscles+": 0.0, "max_speed": 0.0,
                   "max_torso_speed": 0.0, "max_length_error": 0.0, "max_tail_error": 0.0,
                   "max_height": -np.inf})
    ledger.update({k: 0.0 for k in LIMIT_KEYS})
    e_start = _ke(c.world) + _pe(c.world)
    for _ in range(int(round(duration / h))):
        audited_substep(c, h, ledger)
    ledger["E_debut"] = e_start
    ledger["E_fin"] = _ke(c.world) + _pe(c.world)
    # Les étapes de vitesse modifient aussi ce que Movement convertit en énergie potentielle :
    # le bilan « hors muscles » est donc total − muscles, comparé à l'erreur du schéma de gravité.
    ledger["hors_muscles"] = ledger["total"] - ledger["muscles"]
    return c, ledger


def report(genome, label, start_height=None):
    c, L = audit(genome, start_height=start_height)
    lines = [f"{label} : hauteur {c.height():+.2f} m à 10 s, au sol : {'oui' if c.fallen else 'non'}, "
             f"énergie musculaire (HUD) {c.energy:.1f}",
             f"  E mécanique : {L['E_debut']:.1f} J → {L['E_fin']:.1f} J  (Δ = {L['total']:+.1f} J)",
             f"  apport des muscles (ΔKE de Contract)      : {L['muscles']:+10.1f} J",
             f"  bilan hors muscles (total − muscles)      : {L['hors_muscles']:+10.1f} J",
             f"  énergie apparue hors muscles (Σ des sous-pas où total > muscles) : {L['hors_muscles+']:.4f} J",
             "  détail par étape (somme / somme des hausses seules) :"]
    for name in STAGES:
        lines.append(f"    {name:<16} {L[name]:+10.2f} J   hausses {L[name + '+']:9.3f} J")
    lines.append(f"  erreur du schéma de gravité (−½·m·g²·h² par sous-pas) : {L['schema_gravite']:+.3f} J")
    lines.append(f"  butées : {int(L['butees_engagements'])} engagements ; énergie créée hors muscles par sous-pas "
                 + ", ".join(f"{k} max {L[f'saut_{k}_max']:.2e} J (somme {L[f'saut_{k}_somme']:.2e})"
                             for k in LIMIT_CLASSES))
    return c, L, lines
