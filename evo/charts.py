"""Graphes de calibration (phase 3b) : courbes d'évolution et histogrammes, en pygame.

Style du §7 (fond #1C1C1C, couleurs de courbes du §5.2) mais, pour la calibration, une
échelle par graphe : trois panneaux alignés sur les générations (période, hauteur, masse
musculaire) au lieu de la superposition « distance ÷10 » de la vidéo, qui reviendra en
phase 5. Les repères du §9 sont dessinés en cercles creux étiquetés.

Phase 5b : l'histogramme a aussi un style « vidéo » (images 26 à 28, fond à vignette partagé avec
la vue population).

Chantier B2 : comparison_chart superpose deux runs (même graine, avant et après les butées) sur les
mêmes trois panneaux : l'ancien en pointillés gris (référence), le nouveau en trait plein coloré, avec
légende et étiquettes de fin — l'identité ne tient pas à la couleur seule.
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
REFERENCE_RUN = "#8C8C8C"  # run de référence d'une comparaison (pointillés, en retrait)

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
    def __init__(self, surface, fonts, rect, x_max, y_min, y_max, title, ticks=None):
        self.s, self.f, self.r = surface, fonts, pygame.Rect(rect)
        self.x_max, self.y_min, self.y_max = x_max, y_min, y_max
        self.plot = pygame.Rect(self.r.left + 64, self.r.top + 34, self.r.width - 84, self.r.height - 64)
        pygame.draw.rect(surface, _c(PANEL), self.r, border_radius=8)
        _text(surface, fonts["label"], title, (self.r.left + 16, self.r.top + 8))
        # grille horizontale + graduations (ticks = [(valeur, étiquette)] pour une échelle non linéaire)
        if ticks is None:
            step = _nice_step(y_max - y_min)
            first = np.ceil(y_min / step) * step
            ticks = [(v, f"{v:g}") for v in np.arange(first, y_max + 1e-9, step)]
        for v, label in ticks:
            y = self.y(v)
            pygame.draw.line(surface, _c(GRID), (self.plot.left, y), (self.plot.right, y), 1)
            _text(surface, fonts["small"], label, (self.plot.left - 8, y), TEXT_DIM, "midright")
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

    def dashed(self, gens, values, hex_code, width=2, dash=8, gap=6):
        """Même tracé que line(), en pointillés (dash px tracés, gap px vides le long de la courbe)."""
        pts = [(self.x(g), self.y(v)) for g, v in zip(gens, values)]
        on, left = True, dash
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            seg = float(np.hypot(x1 - x0, y1 - y0))
            t = 0.0
            while t < seg:
                step = min(left, seg - t)
                if on:
                    a, b = t / seg, (t + step) / seg
                    pygame.draw.line(self.s, _c(hex_code), (x0 + (x1 - x0) * a, y0 + (y1 - y0) * a),
                                     (x0 + (x1 - x0) * b, y0 + (y1 - y0) * b), width)
                t += step
                left -= step
                if left <= 0:
                    on, left = not on, (dash if not on else gap)
        return pts

    def end_label(self, pts, text):
        if pts:
            x, y = pts[-1]
            pygame.draw.circle(self.s, _c(PANEL), (int(x), int(y)), 6)
            width = self.f["small"].size(text)[0]
            if x + 8 + width <= self.r.right - 4:
                _text(self.s, self.f["small"], text, (x + 8, y), TEXT, "midleft")
            else:  # pas la place à droite : au-dessus du dernier point, aligné à droite
                _text(self.s, self.f["small"], text, (x - 4, y - 8), TEXT, "bottomright")

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


def _end_labels(panel, items):
    """Étiquettes de fin de plusieurs courbes [(points, texte)], écartées d'au moins 18 px en hauteur."""
    items = sorted((it for it in items if it[0]), key=lambda it: it[0][-1][1])
    placed = []
    for pts, text in items:
        x, y = pts[-1]
        if placed and y - placed[-1] < 18:
            y = placed[-1] + 18
        placed.append(y)
        panel.end_label(pts[:-1] + [(x, y)], text)


def comparison_chart(rows_ref, rows_new, title, labels=("sans butées", "avec butées"), size=(1280, 1080)):
    """Les trois panneaux d'evolution_chart, deux runs superposés : `rows_ref` (référence) en pointillés gris,
    `rows_new` en trait plein coloré ; mêmes échelles pour les deux, repères du §9."""
    surface = pygame.Surface(size)
    surface.fill(_c(BG))
    fonts = _fonts()
    w, h = size
    runs = ((rows_ref, labels[0], True), (rows_new, labels[1], False))
    x_max = max(max(r["gen"] for r in rows) for rows, _, _ in runs)
    x_max = max(x_max, 30)
    _text(surface, fonts["title"], title, (24, 18))
    _text(surface, fonts["small"], f"Pointillés gris : {labels[0]}. Trait plein : {labels[1]}. "
          "Cercles creux : repères du §9 (vidéo).", (24, 52), TEXT_DIM)
    panel_h = (h - 100) // 3
    top = 84

    def draw(panel, key, color, fmt, width=2):
        items = []
        for rows, label, ref in runs:
            gens = [r["gen"] for r in rows]
            values = [r[key] for r in rows]
            pts = (panel.dashed if ref else panel.line)(gens, values, REFERENCE_RUN if ref else color, width)
            items.append((pts, f"{label} {fmt(values[-1])}"))
        return items

    def legend(panel, color):
        lx, ly = panel.r.right - 380, panel.r.top + 14
        pygame.draw.line(surface, _c(REFERENCE_RUN), (lx, ly), (lx + 8, ly), 2)
        pygame.draw.line(surface, _c(REFERENCE_RUN), (lx + 14, ly), (lx + 22, ly), 2)
        _text(surface, fonts["small"], labels[0], (lx + 28, ly), TEXT, "midleft")
        pygame.draw.line(surface, _c(color), (lx + 190, ly), (lx + 212, ly), 2)
        _text(surface, fonts["small"], labels[1], (lx + 218, ly), TEXT, "midleft")

    period_max = max(max(r["period_mean"] for r in rows) for rows, _, _ in runs)
    p = _Panel(surface, fonts, (16, top, w - 32, panel_h - 12), x_max, 0.0, max(5.0, period_max * 1.05),
               "Période d'horloge moyenne (s)")
    p.references(REFERENCE["period"])
    _end_labels(p, draw(p, "period_mean", CYAN, lambda v: f"{v:.2f} s"))
    legend(p, CYAN)

    top_h = max(5.0, max(max(max(r["best_height"], r["height_mean"]) for r in rows) for rows, _, _ in runs) * 1.1)
    hp = _Panel(surface, fonts, (16, top + panel_h, w - 32, panel_h - 12), x_max, -10.0, top_h,
                "Hauteur à 10 s (m) : moyenne de la population (2 px) et meilleure (1 px)")
    hp.references(REFERENCE["height"])
    items = draw(hp, "height_mean", GREEN, lambda v: f"moy. {v:+.1f} m")
    items += draw(hp, "best_height", GREEN, lambda v: f"meill. {v:+.1f} m", width=1)
    _end_labels(hp, items)
    legend(hp, GREEN)

    mp = _Panel(surface, fonts, (16, top + 2 * panel_h, w - 32, panel_h - 12), x_max, 0.0, 25.0,
                "Masse musculaire moyenne")
    mp.references(REFERENCE["muscle"])
    _end_labels(mp, draw(mp, "muscle_mean", PINK, lambda v: f"{v:.1f}"))
    legend(mp, PINK)
    _text(surface, fonts["small"], "génération", (w - 40, h - 14), TEXT_DIM, "bottomright")
    return surface


def export_comparison(ref_dir, new_dir, out_dir=None, labels=("sans butées", "avec butées")):
    """PNG des courbes de deux runs superposées ; renvoie le chemin."""
    from evo import evolution as ev

    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pygame.display.init()
    out_dir = out_dir or os.path.join(new_dir, "graphes")
    os.makedirs(out_dir, exist_ok=True)
    seed = os.path.basename(os.path.normpath(new_dir))
    path = os.path.join(out_dir, "courbes_comparees.png")
    surface = comparison_chart(ev.read_stats(ref_dir), ev.read_stats(new_dir),
                               f"Graine {seed} : {ref_dir} contre {new_dir}", labels)
    pygame.image.save(surface, path)
    return path


def diversity_chart(rows, title, size=(1280, 1080), x_max=None):
    """Trois panneaux : ancêtres distincts de la gén. 0 (log), écart-type de la période, part au sol."""
    surface = pygame.Surface(size)
    surface.fill(_c(BG))
    fonts = _fonts()
    w, h = size
    gens = [r["gen"] for r in rows]
    x_max = x_max or max(max(gens), 30)
    _text(surface, fonts["title"], title, (24, 18))
    _text(surface, fonts["small"], "Diversité de la population. Cercles creux : repères du §9. Une échelle par graphe.",
          (24, 52), TEXT_DIM)
    panel_h = (h - 100) // 3
    top = 84

    anc = [np.log10(max(r["ancestors"], 1)) for r in rows]
    ticks = [(np.log10(v), f"{v:g}") for v in (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000)]
    a = _Panel(surface, fonts, (16, top, w - 32, panel_h - 12), x_max, 0.0, 3.0,
               "Ancêtres distincts de la génération 0 parmi la population (échelle log)", ticks)
    y20 = a.y(np.log10(20))
    for x0 in range(a.plot.left, a.plot.right, 12):  # seuil de 20 en pointillés
        pygame.draw.line(surface, _c(NEUTRAL), (x0, y20), (min(x0 + 6, a.plot.right), y20), 1)
    a.end_label(a.line(gens, anc, NEUTRAL), f"{int(rows[-1]['ancestors'])}")

    std = [r["period_std"] for r in rows]
    sp = _Panel(surface, fonts, (16, top + panel_h, w - 32, panel_h - 12), x_max, 0.0, max(1.5, max(std) * 1.1),
                "Écart-type de la période d'horloge dans la population (s)")
    sp.end_label(sp.line(gens, std, CYAN), f"{std[-1]:.2f} s")

    frac = [100.0 * r["fallen_frac"] for r in rows]
    fp = _Panel(surface, fonts, (16, top + 2 * panel_h, w - 32, panel_h - 12), x_max, 0.0,
                max(50.0, max(frac) * 1.1), "Part de la population au sol à 10 s (%)")
    fp.references([(0, 45.0, "≈ 450 / 1000"), (1, 20.0, "≈ 200"), (200, 3.0, "≈ 30")])
    fp.end_label(fp.line(gens, frac, GREEN), f"{frac[-1]:.1f} %")
    _text(surface, fonts["small"], "génération", (w - 40, h - 14), TEXT_DIM, "bottomright")
    return surface


def vignette(size):
    """Fond des écrans d'analyse (§7.1, §7.2) : gris sombre à vignette (ANALYSIS_BG_STOPS), pré-rendu."""
    w, h = size
    yy, xx = np.mgrid[0:h, 0:w]
    d = np.hypot((xx + 0.5 - w / 2) / (w / 2), (yy + 0.5 - h / 2) / (h / 2))
    stops_d, stops_v = zip(*config.ANALYSIS_BG_STOPS)
    gray = np.round(np.interp(d, stops_d, stops_v)).astype(np.uint8)
    return pygame.surfarray.make_surface(np.repeat(gray.T[:, :, None], 3, axis=2))


def hist_video_x(m):
    """Abscisse (px) d'une hauteur (m) dans l'histogramme au style de la vidéo."""
    x0, _, x1, _ = config.HIST_VIDEO["plot"]
    lo, hi = config.HIST_RANGE
    return x0 + (m - lo) * (x1 - x0) / (hi - lo)


def hist_video_y(count):
    """Ordonnée (px) d'un effectif dans l'histogramme au style de la vidéo (tronqué à l'axe Y)."""
    hv = config.HIST_VIDEO
    _, y_top, _, y0 = hv["plot"]
    return y0 - min(count, hv["y_max"]) * (y0 - y_top) / hv["y_max"]


def _histogram_video(counts, size):
    """§7.2 d'après les images 26 à 28 : vignette, grille fine, barres jointives, libellés blancs, sans titre."""
    from evo import fonts

    hv = config.HIST_VIDEO
    surface = vignette(size)
    x0, y_top, x1, y0 = hv["plot"]
    lo, hi = config.HIST_RANGE
    font = fonts.load(hv["font"], hv["font_px"])
    grid = _c(hv["grid"])
    xs = range(lo, hi + 1, hv["x_step"])
    ys = range(0, hv["y_max"] + 1, hv["y_step"])
    for m in xs:
        x = round(hist_video_x(m))
        pygame.draw.line(surface, grid, (x, y_top), (x, y0))
    for v in ys:
        y = round(hist_video_y(v))
        pygame.draw.line(surface, grid, (x0, y), (x1, y))
    bar = _c(BAR)
    for k, cnt in enumerate(counts):   # barres de 1 m jointives, par-dessus la grille
        if cnt <= 0:
            continue
        left, right = round(hist_video_x(lo + k)), round(hist_video_x(lo + k + 1))
        top = round(hist_video_y(cnt))
        surface.fill(bar, pygame.Rect(left, top, right - left, y0 - top))
    for dy, color in hv["axis_bottom"]:
        surface.fill(_c(color), pygame.Rect(x0, y0 + dy, x1 - x0 + 1, 1))
    for dx, color in hv["axis_left"]:
        surface.fill(_c(color), pygame.Rect(x0 + dx, y_top, 1, y0 - y_top))
    label = _c(hv["label"])

    def blit_ink(s, **where):
        img = font.render(s, True, label)
        ink = img.get_bounding_rect()
        # right : dernière colonne d'encre (Rect.right est exclusif)
        x = where["center_x"] - ink.centerx if "center_x" in where else where["right"] + 1 - ink.right
        surface.blit(img, (round(x), where["top"] - ink.top))

    for m in xs:
        blit_ink(f"{m:.1f}", center_x=hist_video_x(m), top=hv["x_label_top"])
    for v in ys:
        blit_ink(f"{v}", right=hv["y_label_right"], top=round(hist_video_y(v)) + hv["y_label_dy"])
    return surface


def clipped_bars(counts):
    """Barres qui dépassent l'axe Y fixe du style vidéo : [(hauteur de début de barre en m, effectif)]."""
    lo = config.HIST_RANGE[0]
    return [(lo + k, int(c)) for k, c in enumerate(counts) if c > config.HIST_VIDEO["y_max"]]


def histogram_chart(row, title=None, size=(1280, 720), stats_lines=(), reference=None, style="calibration"):
    """Histogramme §7.2 : barres de 1 m de −10 à 40 m, axe Y 0–500.

    style="calibration" (phase 3b) : titre, encart de stats, axe Y agrandi si besoin.
    style="video" (phase 5b) : rendu des images 26 à 28, axe Y fixe (une barre plus haute est tronquée).
    """
    from evo.evolution import HIST_COLUMNS, HIST_EDGES

    if style == "video":
        return _histogram_video([row[c] for c in HIST_COLUMNS], size)
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


def export_run(run_dir, out_dir=None, gens=None, curves=True, style="calibration"):
    """Courbes + histogrammes (gén. 0, 1, dernière) d'un run, en PNG. Renvoie les chemins."""
    from evo import evolution as ev

    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")  # rendu sans écran
    pygame.display.init()
    out_dir = out_dir or os.path.join(run_dir, "graphes")
    os.makedirs(out_dir, exist_ok=True)
    rows = ev.read_stats(run_dir)
    seed = os.path.basename(os.path.normpath(run_dir))
    paths = []
    if curves:
        path = os.path.join(out_dir, "courbes.png")
        pygame.image.save(evolution_chart(rows, f"Run {seed} : {int(rows[-1]['gen'])} générations"), path)
        paths.append(path)
        if all("ancestors" in r for r in rows):  # runs d'avant l'étape 3 : pas de lignée complète
            path = os.path.join(out_dir, "diversite.png")
            pygame.image.save(diversity_chart(rows, f"Run {seed} : diversité"), path)
            paths.append(path)
    last = int(rows[-1]["gen"])
    for g in gens if gens is not None else sorted({0, min(1, last), last}):
        row = rows[g]
        if style == "video":
            path = os.path.join(out_dir, f"histogramme_gen{g:04d}_video.png")
            pygame.image.save(histogram_chart(row, style="video"), path)
        else:
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
