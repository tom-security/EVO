"""Commande `morpho` (chantier C2) : morphologie de la population au fil des générations.

Facteur moyen de chaque os (longueur ÷ longueur de référence × BODY_SCALE, borné à LENGTH_FACTOR_RANGE) aux
générations demandées, lu dans les npz (aucun rejeu : le résultat ne dépend pas de la machine). Avec --compare,
le second run est superposé (pointillés). Constat de B2 à suivre : lézard « trapu », colonne et fémur à la borne
basse, demi-bassin près de la borne haute.
"""
import csv
import os

import numpy as np

import config
from evo import creature as cr
from evo import evolution as ev

GENERATIONS = (0, 10, 25, 50, 100, 150, 200)
BONE_LABELS = {"spine": "colonne", "clavicle": "clavicule", "humerus": "humérus", "forearm": "avant-bras",
               "pelvis": "demi-bassin", "femur": "fémur", "tibia": "tibia"}
BONE_COLORS = ("#9CEC6C", "#54E4DC", "#F4D35E", "#F4546C", "#C38CF4", "#F49A54", "#8CB4F4")


def factors(run_dir, gens=GENERATIONS):
    """{génération: (7,) facteur moyen de chaque os} pour les générations sauvegardées parmi `gens`."""
    ev.use_run_config(run_dir)
    ref = cr.reference_lengths()
    saved = set(ev.saved_generations(run_dir))
    out = {}
    for g in gens:
        if g in saved:
            pop, _, _, _ = ev.load_generation(run_dir, g)
            out[g] = (pop.lengths / ref).mean(axis=0)
    return out


def table_lines(label, table):
    head = f"  {label:28s} gén. " + " ".join(f"{BONE_LABELS[b]:>11s}" for b in cr.BONE_NAMES)
    lines = [head]
    for g, f in table.items():
        lines.append(f"  {'':28s} {g:4d} " + " ".join(f"{v:11.3f}" for v in f))
    return lines


def chart(tables, title, size=(1280, 720)):
    """Une courbe par os (couleur), un style par run : trait plein pour le premier, pointillés pour le second."""
    import pygame

    from evo import charts as ch

    surface = pygame.Surface(size)
    surface.fill(ch._c(ch.BG))
    fonts = ch._fonts()
    w, h = size
    labels = list(tables)
    ch._text(surface, fonts["title"], title, (24, 18))
    ch._text(surface, fonts["small"], f"Trait plein : {labels[0]}"
             + (f". Pointillés : {labels[1]}." if len(labels) > 1 else ".")
             + f" Bornes du génome : {config.LENGTH_FACTOR_RANGE[0]:g} et {config.LENGTH_FACTOR_RANGE[1]:g}.",
             (24, 52), ch.TEXT_DIM)
    x_max = max(max(t) for t in tables.values() if t)
    lo, hi = config.LENGTH_FACTOR_RANGE
    panel = ch._Panel(surface, fonts, (16, 84, w - 32, h - 100), max(x_max, 30), lo - 0.05, hi + 0.05,
                      "Facteur moyen de longueur de chaque os (longueur ÷ référence)")
    for v in (lo, hi):
        y = panel.y(v)
        pygame.draw.line(surface, ch._c(ch.NEUTRAL), (panel.plot.left, y), (panel.plot.right, y), 1)
    for k, bone in enumerate(cr.BONE_NAMES):
        for run, (label, table) in enumerate(tables.items()):
            gens = list(table)
            values = [table[g][k] for g in gens]
            pts = (panel.line if run == 0 else panel.dashed)(gens, values, BONE_COLORS[k], 2)
            if run == 0:
                panel.end_label(pts, BONE_LABELS[bone])
    ch._text(surface, fonts["small"], "génération", (w - 40, h - 14), ch.TEXT_DIM, "bottomright")
    return surface


def export(run_dir, compare=None, out_dir=None, gens=GENERATIONS, log=print):
    """Tableau (log), CSV et PNG ; renvoie les chemins écrits."""
    import pygame

    tables = {run_dir: factors(run_dir, gens)}
    if compare:
        tables[compare] = factors(compare, gens)
    lines = ["facteur moyen de longueur des os (longueur ÷ référence ; bornes "
             f"{config.LENGTH_FACTOR_RANGE[0]:g} – {config.LENGTH_FACTOR_RANGE[1]:g})"]
    for label, table in tables.items():
        lines += table_lines(label, table)
    if log:
        for line in lines:
            log(line)
    out_dir = out_dir or os.path.join(run_dir, "graphes")
    os.makedirs(out_dir, exist_ok=True)
    seed = os.path.basename(os.path.normpath(run_dir))
    csv_path = os.path.join(out_dir, f"morphologie_s{seed}.csv")
    with open(csv_path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["run", "gen"] + list(cr.BONE_NAMES))
        for label, table in tables.items():
            for g, f in table.items():
                writer.writerow([label, g] + [f"{v:.6f}" for v in f])
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pygame.display.init()
    png_path = os.path.join(out_dir, f"morphologie_s{seed}.png")
    pygame.image.save(chart(tables, f"Graine {seed} : morphologie de la population"), png_path)
    return [csv_path, png_path]
