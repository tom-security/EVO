"""Graphes de calibration (phase 3b) : courbes d'évolution et histogrammes, en pygame.

Style du §7 (fond #1C1C1C, couleurs de courbes du §5.2) mais, pour la calibration, une
échelle par graphe : trois panneaux alignés sur les générations (période, hauteur, masse
musculaire) au lieu de la superposition « distance ÷10 » de la vidéo, qui reviendra en
phase 5. Les repères du §9 sont dessinés en cercles creux étiquetés.
"""
import os

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import numpy as np
import pygame

import config

BG = "#1C1C1C"
PANEL = "#242424"
GRID = "#383838"
TEXT = "#FCFCFC"
TEXT_DIM = "#A0A0A0"
CYAN = "#54E4DC"      # horloge
GREEN = "#9CEC6C"     # distance
PINK = "#F4546C"      # masse musculaire
BAR = "#94F474"       # histogramme
NEUTRAL = "#C8C8C8"   # seconde série (meilleure) et repères du §9

# Repères du §9 (génération, valeur, étiquette). La courbe « distance » de la vidéo (0.4 → 3.8,
# ÷10) correspond à la hauteur au-dessus du sol ; en hauteur HUD (départ = 0) : valeur×10 − START.
_DIST = lambda v: v * 10 - config.START_HEIGHT  # noqa: E731
REFERENCE = {
    "period": [(0, 2.9, "2.9 s"), (10, 4.5, "flemme : 4.5 s"), (60, 4.8, "plateau 4.7–4.9"),
               (85, 1.9, "chute → 1.9"), (140, 1.9, "plateau 1.9"), (150, 1.0, "chute → 1.0"),
               (200, 0.6, "0.6 s")],
    "height": [(0, _DIST(0.4), "moy. ≈ 0.4×10 − départ"), (12, 1.0, "1re grimpe +1 m"),
               (23, 2.3, "meilleure 2.3 m"), (200, 36.0, "meilleure 36 m"),
               (200, _DIST(3.8), "moy. ≈ 3.8×10 − départ")],
    "muscle": [(0, 13.2, "13.2"), (11, 7.3, "flemme : 7.3"), (20, 9.7, "9.7"), (100, 8.0, "8"),
               (140, 11.3, "11.3"), (200, 10.5, "10.5")],
}
# §9, génération 0 / 1 / 200 (pour les encarts d'histogramme)
REFERENCE_HIST = {0: "§9 gén. 0 : ≈ 450 au sol, reste de −9 à ~+1 m, la meilleure ne grimpe pas",
                  1: "§9 gén. 1 : ≈ 200 au sol, pic autour de 0 qui grossit",
                  200: "§9 gén. 200 : majorité entre 30 et 35 m, ≈ 30 au sol"}


def _c(hex_code):
    return pygame.Color(hex_code)


def _fonts():
    pygame.font.init()
    return {"title": pygame.font.SysFont(config.FONT_SANS, 26, bold=True),
            "label": pygame.font.SysFont(config.FONT_SANS, 18),
            "small": pygame.font.SysFont(config.FONT_SANS, 14),
            "mono": pygame.font.SysFont(config.FONT_MONO, 15)}


def _text(surface, font, s, pos, hex_code=TEXT, anchor="topleft"):
    img = font.render(s, True, _c(hex_code))
    rect = img.get_rect(**{anchor: (int(pos[0]), int(pos[1]))})
    surface.blit(img, rect)
    return rect


def _nice_step(span, target=5):
    raw = span / target
    mag = 10 ** np.floor(np.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        if raw <= m * mag:
            return m * mag
    return 10 * mag


class _Panel:
    def __init__(self, surface, fonts, rect, x_max, y_min, y_max, title):
        self.s, self.f, self.r = surface, fonts, pygame.Rect(rect)
        self.x_max, self.y_min, self.y_max = x_max, y_min, y_max
        self.plot = pygame.Rect(self.r.left + 64, self.r.top + 34, self.r.width - 84, self.r.height - 64)
        pygame.draw.rect(surface, _c(PANEL), self.r, border_radius=8)
        _text(surface, fonts["label"], title, (self.r.left + 16, self.r.top + 8))
        # grille horizontale + graduations
        step = _nice_step(y_max - y_min)
        v = np.ceil(y_min / step) * step
        while v <= y_max + 1e-9:
            y = self.y(v)
            pygame.draw.line(surface, _c(GRID), (self.plot.left, y), (self.plot.right, y), 1)
            _text(surface, fonts["small"], f"{v:g}", (self.plot.left - 8, y), TEXT_DIM, "midright")
            v += step
        xstep = _nice_step(x_max, 10)
        g = 0.0
        while g <= x_max + 1e-9:
            x = self.x(g)
            _text(surface, fonts["small"], f"{g:g}", (x, self.plot.bottom + 6), TEXT_DIM, "midtop")
            g += xstep

    def x(self, g):
        return self.plot.left + self.plot.width * g / max(self.x_max, 1)

    def y(self, v):
        v = min(max(v, self.y_min), self.y_max)
        return self.plot.bottom - self.plot.height * (v - self.y_min) / (self.y_max - self.y_min)

    def line(self, gens, values, hex_code, width=2):
        pts = [(self.x(g), self.y(v)) for g, v in zip(gens, values)]
        if len(pts) > 1:
            pygame.draw.lines(self.s, _c(hex_code), False, pts, width)
        return pts

    def end_label(self, pts, text):
        if pts:
            x, y = pts[-1]
            pygame.draw.circle(self.s, _c(PANEL), (int(x), int(y)), 6)
            _text(self.s, self.f["small"], text, (min(x + 8, self.plot.right - 4), y), TEXT, "midleft")

    def references(self, refs):
        for g, v, label in refs:
            if g > self.x_max or not (self.y_min <= v <= self.y_max):
                continue
            x, y = self.x(g), self.y(v)
            pygame.draw.circle(self.s, _c(PANEL), (int(x), int(y)), 7)
            pygame.draw.circle(self.s, _c(NEUTRAL), (int(x), int(y)), 5, 2)
            _text(self.s, self.f["small"], f"§9 {label}", (x + 8, y - 4), TEXT_DIM, "bottomleft")


def evolution_chart(rows, title, size=(1280, 1080), x_max=None):
    """Trois panneaux : période moyenne, hauteur (moyenne + meilleure), masse musculaire moyenne."""
    surface = pygame.Surface(size)
    surface.fill(_c(BG))
    fonts = _fonts()
    w, h = size
    gens = [r["gen"] for r in rows]
    x_max = x_max or max(max(gens), 30)
    _text(surface, fonts["title"], title, (24, 18))
    _text(surface, fonts["small"], "Cercles creux : repères du §9 (vidéo). Une échelle par graphe.",
          (24, 52), TEXT_DIM)
    panel_h = (h - 100) // 3
    top = 84

    period = [r["period_mean"] for r in rows]
    p = _Panel(surface, fonts, (16, top, w - 32, panel_h - 12), x_max, 0.0, max(5.0, max(period) * 1.05),
               "Période d'horloge moyenne (s)")
    p.references(REFERENCE["period"])
    p.end_label(p.line(gens, period, CYAN), f"{period[-1]:.2f} s")

    mean_h = [r["height_mean"] for r in rows]
    best_h = [r["best_height"] for r in rows]
    top_h = max(5.0, max(max(best_h), max(mean_h)) * 1.1)
    hp = _Panel(surface, fonts, (16, top + panel_h, w - 32, panel_h - 12), x_max, -10.0, top_h,
                "Hauteur à 10 s (m) : moyenne de la population et meilleure (score)")
    hp.references(REFERENCE["height"])
    hp.end_label(hp.line(gens, best_h, NEUTRAL, 1), f"meilleure {best_h[-1]:+.1f} m")
    hp.end_label(hp.line(gens, mean_h, GREEN), f"moyenne {mean_h[-1]:+.1f} m")
    # légende (2 séries)
    lx, ly = hp.r.right - 330, hp.r.top + 12
    pygame.draw.line(surface, _c(GREEN), (lx, ly), (lx + 22, ly), 2)
    _text(surface, fonts["small"], "moyenne", (lx + 28, ly), TEXT, "midleft")
    pygame.draw.line(surface, _c(NEUTRAL), (lx + 110, ly), (lx + 132, ly), 1)
    _text(surface, fonts["small"], "meilleure (score max)", (lx + 138, ly), TEXT, "midleft")

    muscle = [r["muscle_mean"] for r in rows]
    mp = _Panel(surface, fonts, (16, top + 2 * panel_h, w - 32, panel_h - 12), x_max, 0.0, 25.0,
                "Masse musculaire moyenne")
    mp.references(REFERENCE["muscle"])
    mp.end_label(mp.line(gens, muscle, PINK), f"{muscle[-1]:.1f}")
    _text(surface, fonts["small"], "génération", (w - 40, h - 14), TEXT_DIM, "bottomright")
    return surface


def histogram_chart(row, title, size=(1280, 720), stats_lines=(), reference=None):
    """Histogramme §7.2 : barres de 1 m de −10 à 40 m, axe Y 0–500 (agrandi si besoin)."""
    from evo.evolution import HIST_COLUMNS, HIST_EDGES

    surface = pygame.Surface(size)
    surface.fill(_c(BG))
    fonts = _fonts()
    w, h = size
    counts = np.array([row[c] for c in HIST_COLUMNS], dtype=float)
    y_max = max(500.0, np.ceil(counts.max() / 100) * 100)
    _text(surface, fonts["title"], title, (24, 18))
    plot = pygame.Rect(80, 90, w - 130 - (420 if stats_lines else 0), h - 200)
    pygame.draw.rect(surface, _c(PANEL), plot.inflate(40, 40), border_radius=8)
    for v in np.arange(0, y_max + 1, 100):
        y = plot.bottom - plot.height * v / y_max
        pygame.draw.line(surface, _c(GRID), (plot.left, y), (plot.right, y), 1)
        _text(surface, fonts["small"], f"{v:g}", (plot.left - 8, y), TEXT_DIM, "midright")
    n = len(counts)
    slot = plot.width / n
    bar_w = min(24, slot - 2)
    for k, cnt in enumerate(counts):
        if cnt <= 0:
            continue
        bh = max(2, plot.height * cnt / y_max)
        x = plot.left + k * slot + (slot - bar_w) / 2
        rect = pygame.Rect(int(x), int(plot.bottom - bh), int(bar_w), int(bh))
        pygame.draw.rect(surface, _c(BAR), rect, border_top_left_radius=4, border_top_right_radius=4)
    for e in range(int(HIST_EDGES[0]), int(HIST_EDGES[-1]) + 1, 5):
        x = plot.left + (e - HIST_EDGES[0]) * slot
        _text(surface, fonts["small"], f"{e:.1f}", (x, plot.bottom + 8), TEXT_DIM, "midtop")
    _text(surface, fonts["small"], "hauteur à 10 s (m) ; < −10 m compté dans la première barre",
          (plot.centerx, plot.bottom + 30), TEXT_DIM, "midtop")
    peak = int(np.argmax(counts))
    px = plot.left + peak * slot + slot / 2
    py = plot.bottom - plot.height * counts[peak] / y_max
    _text(surface, fonts["label"], f"{int(counts[peak])}", (px, py - 6), TEXT, "midbottom")
    if stats_lines:
        box = pygame.Rect(w - 400, 70, 380, h - 150)
        pygame.draw.rect(surface, _c(PANEL), box, border_radius=8)
        y = box.top + 14
        for line in stats_lines:
            color = TEXT_DIM if line.startswith("§9") or line.startswith("  §9") else TEXT
            _text(surface, fonts["mono"], line, (box.left + 14, y), color)
            y += 22
    if reference:
        _text(surface, fonts["small"], reference, (24, h - 16), TEXT_DIM, "midleft")
    return surface


def export_run(run_dir, out_dir=None, gens=None):
    """Courbes + histogrammes (gén. 0, 1, dernière) d'un run, en PNG. Renvoie les chemins."""
    from evo import evolution as ev

    pygame.display.init()
    out_dir = out_dir or os.path.join(run_dir, "graphes")
    os.makedirs(out_dir, exist_ok=True)
    rows = ev.read_stats(run_dir)
    seed = os.path.basename(os.path.normpath(run_dir))
    paths = []
    title = f"Run {seed} : {int(rows[-1]['gen'])} générations"
    path = os.path.join(out_dir, "courbes.png")
    pygame.image.save(evolution_chart(rows, title), path)
    paths.append(path)
    last = int(rows[-1]["gen"])
    for g in gens if gens is not None else sorted({0, min(1, last), last}):
        row = rows[g]
        path = os.path.join(out_dir, f"histogramme_gen{g:04d}.png")
        pygame.image.save(histogram_chart(row, f"Génération {g} : distribution des hauteurs à 10 s",
                                          stats_lines=summary_lines(row), reference=REFERENCE_HIST.get(g)), path)
        paths.append(path)
    return paths


def summary_lines(row):
    """Tableau de stats d'une génération, à côté des chiffres du §9."""
    g = int(row["gen"])
    ref = {0: {"fallen": "≈ 450", "best": "−0.1 m, E 0.5", "muscle": "≈ 13.2", "period": "≈ 2.9 s",
               "energy": "0.5 à 33"},
           1: {"fallen": "≈ 200", "best": "moins musclée", "muscle": "≈ 13", "period": "≈ 3", "energy": "—"},
           200: {"fallen": "≈ 30", "best": "36 m, E 32.5, M 13.5", "muscle": "≈ 10.5", "period": "≈ 0.6 s",
                 "energy": "—"}}.get(g, {})
    lines = [f"Génération {g}", "",
             f"au sol          {int(row['fallen']):4d}"]
    if ref:
        lines.append(f"  §9            {ref['fallen']}")
    lines += [f"meilleure       {row['best_height']:+.2f} m",
              f"  énergie {row['best_energy']:.1f}  muscle {row['best_muscle']:.1f}",
              f"  période {row['best_period']:.2f} s"]
    if ref:
        lines.append(f"  §9            {ref['best']}")
    lines += [f"muscle moyen    {row['muscle_mean']:.2f}"]
    if ref:
        lines.append(f"  §9            {ref['muscle']}")
    lines += [f"période moyenne {row['period_mean']:.2f} s"]
    if ref:
        lines.append(f"  §9            {ref['period']}")
    lines += [f"énergie médiane {row['energy_median']:.1f}  max {row.get('energy_max', float('nan')):.1f}",
              f"hauteur max    {row['height_max']:+.2f} m",
              f"hauteur moy.   {row['height_mean']:+.2f} m"]
    if ref:
        lines.append(f"  §9 énergie    {ref['energy']}")
    return lines
