"""Commande `essai` (v2, docs/SPEC_V2_GECKO.md) : un génome JSON écrit à la main, simulé 10 s, avec son rapport d'essai
et son fichier d'états ; et la vérification d'une partie sur la plateforme officielle (`verifier-partie`).

Un essai :
1. vérifie le génome (evo/genome_json.py) : un génome invalide ne compte pas comme un essai ;
2. le simule au moteur scalaire (evo/etats.py) en observant les prises, la chute et les articulations ;
3. recoupe le résultat avec l'évaluateur batché, au bit près (sinon erreur) ;
4. écrit rapport.txt (le texte que lit le joueur), resultat.json, etats.json et une copie du génome.

Dans une partie (`--partie DIR`) : les essais sont numérotés (essai_001, …), rien n'est jamais écrasé, l'hypothèse est
écrite dans le carnet de bord avant la simulation, un seul génome par appel, et le budget est tenu (annoncé :
DUEL_BUDGET_ANNONCE ; prolongation jusqu'à DUEL_BUDGET_MAX).

Plateforme (config.DUEL_PLATEFORME_OFFICIELLE) : un essai joué ailleurs est noté non officiel ; `verifier-partie`, lancé
sur la plateforme officielle (le runner : mode `verification` du workflow), rejoue tous les essais d'une partie et donne
les chiffres officiels, l'empreinte et l'écart par essai ; `--integrer` reporte ces chiffres dans la partie.
"""
import csv
import datetime
import glob
import hashlib
import json
import os
import re
import shutil

import numpy as np

import config
from evo import batch
from evo import creature as cr
from evo import etats
from evo import genome_json as gj
from evo import joint_audit as ja

FORMAT_RESULTAT = "gecko-resultat-1"
FORMAT_PARTIE = "gecko-partie-1"
ESSAI_RE = re.compile(r"^essai_(\d{3})$")
MARQUE_ECART = "Écart avec la plateforme officielle : "
ARTICULATIONS = [(f"{name} {side}", kind) for side in ("G", "D") for name, kind in
                 (("épaule", "épaule"), ("coude", "coude"), ("hanche", "hanche"), ("genou", "genou"))]
_LETTRE = {"épaule": "α", "coude": "β", "hanche": "α", "genou": "β"}


class EssaiRefuse(RuntimeError):
    """Essai refusé avant toute simulation (budget épuisé, partie d'une autre manche, essai déjà écrit…)."""


def _n(x, fmt="+.2f"):
    return format(x, fmt).replace(".", ",").replace("-", "−")


def _pct(x):
    return f"{100 * x:.1f}".replace(".", ",") + " %"


def _maintenant():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Simulation observée
# ---------------------------------------------------------------------------
class CreatureObservee(cr.Creature):
    """Créature du moteur qui note, au début de chaque pose, ce que devient chaque prise demandée. Lecture seule : la
    simulation est celle de Creature (le recoupement avec l'évaluateur batché le vérifie à chaque essai)."""

    def __init__(self, genome):
        super().__init__(genome)
        self.evenements = []    # (pose, t, [(statut, dépassement du bord du tronc en m)] × 4 pattes)

    def apply_holds(self, pose):
        super().apply_holds(pose)
        statuts = []
        for limb, want in zip(cr.LIMBS, self.genome.holds[pose]):
            x = self.world.pos[limb][0]
            if not want:
                statuts.append(("libre", 0.0))
            elif self.fallen:
                statuts.append(("tombée", 0.0))
            elif not self.on_trunk(self.world.pos[limb]):
                statuts.append(("hors du tronc", abs(x - config.TRUNK_X) - config.TRUNK_WIDTH / 2))
            else:
                statuts.append(("tenue", 0.0))
        self.evenements.append((int(pose), float(self.t), statuts))


def executer(genome):
    """Simule un génome : (créature finale, images du fichier d'états, mesures par sous-pas)."""
    c = CreatureObservee(genome)
    n_points = len(c.world.pos)
    pos = [c.world.pos.copy()]
    held = [c.world.held.copy()]
    chute = {}

    def rappel(cc):
        pos.append(cc.world.pos.copy())
        held.append(cc.world.held.copy())
        if cc.fallen and not chute:
            ys = cc.world.pos[cc.body_points, 1]
            touch = np.nonzero(ys <= config.GROUND_Y + config.FALL_CONTACT_EPS)[0]
            chute.update(t=cc.t, points=[etats.point_noms(n_points)[int(cc.body_points[k])] for k in touch])

    c, imgs = etats.simuler(genome, creature=c, rappel=rappel)
    return c, imgs, {"pos": np.array(pos), "held": np.array(held), "chute": chute or None}


def recouper(genome, c):
    """Recoupe la simulation scalaire avec l'évaluateur batché : hauteurs, énergie et chute identiques au bit près."""
    res = batch.evaluate([genome], duration=config.SIM_DURATION)
    pairs = {"hauteur à 10 s": (res["height"][0], c.height()), "hauteur accrochée": (res["hang_height"][0], c.hang_height()),
             "énergie": (res["energy"][0], c.energy)}
    bad = [f"{k} : batché {a!r}, scalaire {b!r}" for k, (a, b) in pairs.items() if a != b]
    if bool(res["fallen"][0]) != c.fallen:
        bad.append("chute différente")
    if bad:
        raise RuntimeError("moteur scalaire et évaluateur batché divergent : " + " ; ".join(bad))


def mesures(genome, c, imgs, obs):
    """Mesures du rapport d'essai (sections 2 à 6), en types JSON."""
    # 2. trajectoire : hauteur du torse aux multiples de DUEL_TRAJECTOIRE_PAS_S
    step = int(round(config.DUEL_TRAJECTOIRE_PAS_S / config.DT))
    trajectoire = [[float(imgs["t"][f]), float(imgs["hauteur"][f])] for f in range(0, len(imgs["t"]), step)]
    # 4. prises : par pose et par patte, nombre de fois où la pose a été jouée et devenir de chaque prise demandée
    prises = []
    for k in range(genome.n_poses):
        ev = [e for e in c.evenements if e[0] == k]
        pattes = []
        for l, name in enumerate(etats.PRISE_NOMS):
            st = [e[2][l] for e in ev]
            pattes.append({"patte": name, "demandee": bool(genome.holds[k, l]),
                           "tenue": sum(s == "tenue" for s, _ in st),
                           "hors_du_tronc": sum(s == "hors du tronc" for s, _ in st),
                           "tombee": sum(s == "tombée" for s, _ in st),
                           "depassement_max_m": max([d for s, d in st if s == "hors du tronc"], default=0.0)})
        prises.append({"pose": k + 1, "jouee": len(ev), "pattes": pattes})
    # 5. articulations : angle anatomique parcouru et part du temps à moins de JOINT_LIMIT_MARGIN_DEG d'une butée
    angles = ja.anatomical_angles(obs["pos"][1:])
    marge = config.JOINT_LIMIT_MARGIN_DEG
    articulations = []
    for j, (name, kind) in enumerate(ARTICULATIONS):
        lo, hi = config.JOINT_LIMITS_DEG[kind]
        a = angles[:, j]
        articulations.append({"articulation": name, "angle": _LETTRE[kind], "butees": [lo, hi],
                              "min": float(a.min()), "max": float(a.max()),
                              "en_butee": float(np.mean((a <= lo + marge) | (a >= hi - marge)))})
    # 6. corps : main ou pied de l'autre côté de l'axe bassin–cou, jambe qui croise la queue en vue de dessus
    lat, _, _ = ja.axis_positions(obs["pos"][1:])
    cote = {f"{p} {s}": float(np.mean(lat[:, i, j] < 0))
            for p, j in (("main", 1), ("pied", 3)) for i, s in enumerate(("G", "D"))}
    crossed, held_count = ja.leg_tail_crossings(obs["pos"][1:], obs["held"][1:])
    n = len(obs["pos"]) - 1
    corps = {"autre_cote_de_l_axe": float(np.mean(np.any(lat[:, :, [1, 3]] < 0, axis=(1, 2)))),
             "autre_cote_par_patte": cote,
             "jambe_sur_queue": crossed / n / 2,
             "jambe_sur_queue_pied_tenu": held_count / crossed if crossed else None}
    return {"trajectoire": trajectoire, "chute": obs["chute"], "prises": prises, "articulations": articulations,
            "corps": corps}


# ---------------------------------------------------------------------------
# Rapport d'essai
# ---------------------------------------------------------------------------
def ligne_ecart(verif):
    """Ligne du rapport sur l'écart avec la plateforme officielle (None : pas encore vérifié)."""
    if verif is None:
        return MARQUE_ECART + "pas encore connu (vérification de la partie à venir)."
    if verif.get("identique"):
        return MARQUE_ECART + f"aucun ({verif['libelle']} : résultat et états identiques au bit près)."
    r = verif["resultat"]
    return (MARQUE_ECART + f"hauteur accrochée {_n(verif['ecart_hauteur_accrochee'], '+.3f')} m "
            f"({verif['libelle']} : {_n(r['hauteur_accrochee'], '+.3f')} m), hauteur à 10 s "
            f"{_n(verif['ecart_hauteur_10s'], '+.3f')} m, énergie {_n(verif['ecart_energie'], '+.3f')}"
            + (", chute différente" if verif.get("chute_differente") else "") + " ; états différents.")


def rapport(entete_essai, resultat, mes, plat, verif=None):
    """Texte du rapport d'essai, toujours dans le même ordre (spec v2, « Le rapport d'essai »)."""
    r = resultat
    L = [f"Rapport d'essai : {entete_essai}"]
    if plat["officielle"]:
        L.append(f"Plateforme : {plat['libelle']}, officielle.")
    else:
        L.append(f"Plateforme : {plat['libelle']}, non officielle ; les chiffres officiels viennent du rejeu de la "
                 f"partie sur la plateforme officielle ({etats.LIBELLES_PLATEFORME.get(plat['plateforme_officielle'], plat['plateforme_officielle'])}).")
        L.append(ligne_ecart(verif))
    L += ["", "1. Résultat"]
    if r["jamais_accrochee"]:
        L.append(f"- Hauteur accrochée : {_n(r['hauteur_accrochee'])} m (jamais accrochée : hauteur à 10 s)")
    else:
        L.append(f"- Hauteur accrochée : {_n(r['hauteur_accrochee'])} m (dernière prise tenue à "
                 f"{_n(r['instant_derniere_prise'], '.2f')} s)")
    L += [f"- Hauteur à 10 s : {_n(r['hauteur_10s'])} m",
          f"- Énergie dépensée sur 10 s : {_n(r['energie'], '.2f')}",
          f"- Masse musculaire : {_n(r['masse_musculaire'], '.2f')}",
          "", "2. Trajectoire (hauteur du centre du torse, m)"]
    traj = mes["trajectoire"]
    for i in range(0, len(traj), 7):
        L.append("   " + " | ".join(f"{_n(t, '.1f')} s : {_n(h)}" for t, h in traj[i:i + 7]))
    L += ["", "3. Chute"]
    ch = mes["chute"]
    L.append(f"- À {_n(ch['t'], '.2f')} s : {', '.join(ch['points'])} touche le sol." if ch else "- Pas de chute.")
    L += ["", "4. Prises (au début de chaque pose : tenue, échouée hors du tronc, ou impossible après la chute)"]
    for p in mes["prises"]:
        if not p["jouee"]:
            L.append(f"- Pose {p['pose']} : jamais jouée.")
            continue
        parts = []
        for q in p["pattes"]:
            if not q["demandee"]:
                parts.append(f"{q['patte']} libre")
                continue
            s = f"{q['patte']} tenue {q['tenue']}/{p['jouee']}"
            if q["hors_du_tronc"]:
                s += (f", hors du tronc {q['hors_du_tronc']}/{p['jouee']} (jusqu'à "
                      f"{_n(q['depassement_max_m'], '.2f')} m au-delà du bord)")
            if q["tombee"]:
                s += f", impossible (tombé) {q['tombee']}/{p['jouee']}"
            parts.append(s)
        L.append(f"- Pose {p['pose']} (jouée {p['jouee']} fois) : " + " ; ".join(parts) + ".")
    L += ["", f"5. Articulations (angle anatomique parcouru, en degrés ; part du temps à moins de "
              f"{config.JOINT_LIMIT_MARGIN_DEG:g}° d'une butée)"]
    for a in mes["articulations"]:
        lo, hi = a["butees"]
        L.append(f"- {a['articulation']} ({a['angle']}, butées {_n(lo, 'g')} / {_n(hi, 'g')}) : "
                 f"{_n(a['min'], '+.1f')} à {_n(a['max'], '+.1f')} ; en butée {_pct(a['en_butee'])}")
    co = mes["corps"]
    L += ["", "6. Corps"]
    L.append(f"- Main ou pied de l'autre côté de l'axe du corps : {_pct(co['autre_cote_de_l_axe'])} du temps ("
             + ", ".join(f"{k} {_pct(v)}" for k, v in co["autre_cote_par_patte"].items()) + ").")
    s = f"- Jambe qui croise la queue (vue de dessus) : {_pct(co['jambe_sur_queue'])} du temps par jambe"
    if co["jambe_sur_queue_pied_tenu"] is not None:
        s += f", dont pied tenu {_pct(co['jambe_sur_queue_pied_tenu'])}"
    L.append(s + ".")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------------------
# Un essai
# ---------------------------------------------------------------------------
def evaluer(genome, source, genome_data):
    """Simulation, recoupement, mesures : (résultat, mesures, plateforme, en-tête d'états, images)."""
    c, imgs, obs = executer(genome)
    recouper(genome, c)
    res = etats.resultat_creature(c)
    if obs["chute"]:
        res.update(instant_chute=obs["chute"]["t"], points_chute=obs["chute"]["points"])
    else:
        res.update(instant_chute=None, points_chute=[])
    mes = mesures(genome, c, imgs, obs)
    head = etats.entete(source, c, genome_json=genome_data, resultat=res)
    return res, mes, head, imgs


def _ecrire_json(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
        fh.write("\n")


def _numero(partie):
    nums = [int(m.group(1)) for d in os.listdir(partie) if (m := ESSAI_RE.match(d))]
    return max(nums, default=0) + 1


def _partie(partie, manche):
    """Crée ou relit partie.json ; vérifie la manche."""
    path = os.path.join(partie, "partie.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            info = json.load(fh)
        if info["manche"] != manche:
            raise EssaiRefuse(f"la partie {info['partie']} est de la manche {info['manche']}, pas de la manche {manche}")
        return info
    os.makedirs(partie, exist_ok=True)
    info = {"format": FORMAT_PARTIE, "partie": os.path.basename(os.path.normpath(partie)), "manche": manche,
            "creee": _maintenant(), "budget_annonce": config.DUEL_BUDGET_ANNONCE, "budget_max": config.DUEL_BUDGET_MAX}
    _ecrire_json(path, info)
    with open(os.path.join(partie, "carnet.md"), "w", encoding="utf-8") as fh:
        fh.write(f"# Carnet de bord : partie {info['partie']} (manche {manche})\n")
    return info


def _carnet(partie, texte):
    with open(os.path.join(partie, "carnet.md"), "a", encoding="utf-8") as fh:
        fh.write(texte)
        fh.flush()
        os.fsync(fh.fileno())


def jouer(genome_path, manche, partie=None, hypothese=None, sortie=None, log=print):
    """Un essai. Avec `partie` : numéroté, hypothèse obligatoire, écrit dans la partie ; sinon dans `sortie`.
    Renvoie le dossier de l'essai."""
    genome, data, raw = gj.charger(genome_path, manche)        # GenomeInvalide : aucun essai consommé
    if partie is not None:
        if not hypothese or not hypothese.strip():
            raise EssaiRefuse("une hypothèse (une ou deux phrases) est obligatoire avant chaque essai d'une partie")
        info = _partie(partie, manche)
        numero = _numero(partie)
        if numero > config.DUEL_BUDGET_MAX:
            raise EssaiRefuse(f"budget épuisé : {config.DUEL_BUDGET_MAX} essais déjà joués dans cette partie")
        dossier = os.path.join(partie, f"essai_{numero:03d}")
        os.makedirs(dossier)                                     # FileExistsError : jamais d'écrasement
        nom = info["partie"]
        entete_essai = f"partie {nom}, essai {numero} (manche {manche})"
        _carnet(partie, f"\n## Essai {numero:03d} ({_maintenant()})\n\nHypothèse : {hypothese.strip()}\n")
    else:
        numero, nom = None, None
        dossier = sortie or os.path.join("out", "essais", datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
        os.makedirs(dossier, exist_ok=True)
        entete_essai = f"essai hors partie (manche {manche})"
    with open(os.path.join(dossier, "genome.json"), "wb") as fh:
        fh.write(raw)
    source = {"type": "essai", "partie": nom, "essai": numero, "manche": manche}
    res, mes, head, imgs = evaluer(genome, source, data)
    fp = etats.ecrire(os.path.join(dossier, "etats.json"), head, imgs)
    resultat = {"format": FORMAT_RESULTAT, "partie": nom, "essai": numero, "manche": manche, "horodatage": _maintenant(),
                "genome_sha256": hashlib.sha256(raw).hexdigest(), "plateforme": head["plateforme"],
                "officiel": head["plateforme"]["officielle"], "commit": head["commit"], "resultat": res,
                "mesures": mes, "empreinte_etats": fp, "verification": None}
    _ecrire_json(os.path.join(dossier, "resultat.json"), resultat)
    texte = rapport(entete_essai, res, mes, head["plateforme"])
    with open(os.path.join(dossier, "rapport.txt"), "w", encoding="utf-8") as fh:
        fh.write(texte)
    if partie is not None:
        chute = f"chute à {_n(res['instant_chute'], '.2f')} s" if res["tombee"] else "pas de chute"
        _carnet(partie, f"\nRésultat : hauteur accrochée {_n(res['hauteur_accrochee'])} m ; hauteur à 10 s "
                        f"{_n(res['hauteur_10s'])} m ; énergie {_n(res['energie'], '.2f')} ; {chute}.\n")
    log(texte)
    if numero == config.DUEL_BUDGET_ANNONCE:
        log(f"Essai {numero} : budget annoncé atteint ; les essais suivants sont la prolongation "
            f"(jusqu'à {config.DUEL_BUDGET_MAX}).")
    return dossier


# ---------------------------------------------------------------------------
# Vérification d'une partie sur la plateforme officielle
# ---------------------------------------------------------------------------
def _essais(partie):
    return sorted(d for d in os.listdir(partie) if ESSAI_RE.match(d) and os.path.isdir(os.path.join(partie, d)))


def verifier_partie(partie, sortie, log=print):
    """Rejoue tous les essais d'une partie sur la plateforme courante ; écrit dans `sortie`/<partie>/ : pour chaque
    essai, resultat.json (avec le bloc « verification »), rapport.txt (ligne d'écart mise à jour), rapport_officiel.txt
    et etats_officiels.json ; puis verification.csv. Renvoie les lignes du tableau."""
    with open(os.path.join(partie, "partie.json"), encoding="utf-8") as fh:
        info = json.load(fh)
    plat = etats.plateforme()
    if not plat["officielle"]:
        log(f"ATTENTION : vérification sur {plat['libelle']}, qui n'est pas la plateforme officielle "
            f"({config.DUEL_PLATEFORME_OFFICIELLE}) : chiffres non officiels")
    out_root = os.path.join(sortie, info["partie"])
    rows = []
    for name in _essais(partie):
        src = os.path.join(partie, name)
        with open(os.path.join(src, "resultat.json"), encoding="utf-8") as fh:
            local = json.load(fh)
        genome, data, raw = gj.charger(os.path.join(src, "genome.json"), info["manche"])
        if hashlib.sha256(raw).hexdigest() != local["genome_sha256"]:
            raise RuntimeError(f"{name} : le génome ne correspond plus à son résultat (SHA-256)")
        source = {"type": "essai", "partie": info["partie"], "essai": local["essai"], "manche": info["manche"],
                  "verification": True}
        res, mes, head, imgs = evaluer(genome, source, data)
        dst = os.path.join(out_root, name)
        os.makedirs(dst, exist_ok=True)
        fp = etats.ecrire(os.path.join(dst, "etats_officiels.json"), head, imgs)
        lr = local["resultat"]
        verif = {"plateforme": plat, "libelle": plat["libelle"], "officielle": plat["officielle"],
                 "commit": head["commit"], "run_id": os.environ.get("GITHUB_RUN_ID"), "horodatage": _maintenant(),
                 "resultat": res, "empreinte_etats": fp, "identique": fp == local["empreinte_etats"],
                 "ecart_hauteur_accrochee": lr["hauteur_accrochee"] - res["hauteur_accrochee"],
                 "ecart_hauteur_10s": lr["hauteur_10s"] - res["hauteur_10s"],
                 "ecart_energie": lr["energie"] - res["energie"],
                 "chute_differente": lr["tombee"] != res["tombee"]}
        local["verification"] = verif
        _ecrire_json(os.path.join(dst, "resultat.json"), local)
        with open(os.path.join(src, "rapport.txt"), encoding="utf-8") as fh:
            texte = fh.read()
        texte = "\n".join(ligne_ecart(verif) if line.startswith(MARQUE_ECART) else line
                          for line in texte.split("\n"))
        with open(os.path.join(dst, "rapport.txt"), "w", encoding="utf-8") as fh:
            fh.write(texte)
        entete_essai = f"partie {info['partie']}, essai {local['essai']} (manche {info['manche']}), rejeu officiel"
        with open(os.path.join(dst, "rapport_officiel.txt"), "w", encoding="utf-8") as fh:
            fh.write(rapport(entete_essai, res, mes, plat))
        row = {"essai": local["essai"], "plateforme_essai": local["plateforme"]["id"], "plateforme_verification": plat["id"],
               "hauteur_accrochee_essai": lr["hauteur_accrochee"], "hauteur_accrochee_officielle": res["hauteur_accrochee"],
               "ecart_hauteur_accrochee": verif["ecart_hauteur_accrochee"],
               "jamais_accrochee": res["jamais_accrochee"],
               "hauteur_10s_officielle": res["hauteur_10s"], "ecart_hauteur_10s": verif["ecart_hauteur_10s"],
               "energie_officielle": res["energie"], "ecart_energie": verif["ecart_energie"],
               "chute_differente": verif["chute_differente"], "etats_identiques": verif["identique"],
               "empreinte_officielle": fp}
        rows.append(row)
        log(f"{name} : hauteur accrochée {_n(res['hauteur_accrochee'])} m (essai {_n(lr['hauteur_accrochee'])} m, "
            f"écart {_n(row['ecart_hauteur_accrochee'], '+.3g')} m) ; états {'identiques' if row['etats_identiques'] else 'différents'}")
    os.makedirs(out_root, exist_ok=True)
    with open(os.path.join(out_root, "verification.csv"), "w", newline="", encoding="utf-8") as fh:
        if rows:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    log(f"{len(rows)} essais vérifiés sur {plat['libelle']} → {out_root}")
    return rows


def integrer(artefact, partie, log=print):
    """Reporte dans la partie les fichiers d'une vérification (dossier `artefact` contenant <partie>/essai_NNN/) :
    resultat.json, rapport.txt, rapport_officiel.txt et etats_officiels.json, après contrôle du génome (SHA-256)."""
    with open(os.path.join(partie, "partie.json"), encoding="utf-8") as fh:
        info = json.load(fh)
    candidates = glob.glob(os.path.join(artefact, "**", info["partie"], "verification.csv"), recursive=True)
    if not candidates:
        raise FileNotFoundError(f"aucune vérification de la partie {info['partie']} dans {artefact}")
    root = os.path.dirname(candidates[0])
    n = 0
    for name in _essais(root):
        src, dst = os.path.join(root, name), os.path.join(partie, name)
        with open(os.path.join(src, "resultat.json"), encoding="utf-8") as fh:
            verified = json.load(fh)
        with open(os.path.join(dst, "genome.json"), "rb") as fh:
            if hashlib.sha256(fh.read()).hexdigest() != verified["genome_sha256"]:
                raise RuntimeError(f"{name} : le génome de la partie ne correspond pas à la vérification")
        for f in ("resultat.json", "rapport.txt", "rapport_officiel.txt", "etats_officiels.json"):
            shutil.copyfile(os.path.join(src, f), os.path.join(dst, f))
        n += 1
    shutil.copyfile(os.path.join(root, "verification.csv"), os.path.join(partie, "verification.csv"))
    log(f"{n} essais de la partie {info['partie']} mis à jour depuis {root}")
    return n
