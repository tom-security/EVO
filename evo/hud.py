"""HUD de simulation (§6, images 03, 05, 09, 39) dessiné par-dessus la scène jungle.

- En haut à gauche, trois badges empilés (fond #2C242C à ~85 %) : horloge (période), éclair
  (énergie cumulée, ENERGY_SCALE inclus), muscle (masse musculaire). Icônes vectorielles.
- En haut à droite : « Génération: N », « Classement: #R » (ou « Créature: i »), « Temps: x.x s ».
- Étiquette de hauteur à gauche du tronc, à la hauteur du lézard, pointe vers la droite, triple
  chevron vert et hauteur brute « 23.1 m ».
- Carton de génération en début de replay, icône ⏩ pour un replay accéléré.

Tout ce qui ne change pas est pré-rendu une fois (fonds, icônes) ; chaque texte est rendu une seule
fois par valeur affichée (cache), donc une frame ne coûte que quelques petits blits.
"""
import math
import os

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import numpy as np
import pygame

import config
from evo import fonts

SS = 4   # supersampling des icônes (puissance de 2 : réduction exacte)


# ---------------------------------------------------------------------------
# Icônes vectorielles (dessinées ×SS puis réduites)
# ---------------------------------------------------------------------------
def _stroke(surf, pts, color, width, closed=False, k=SS):
    """Trait épais à joints ronds (segments en polygones + disques aux sommets)."""
    pts = [(x * k, y * k) for x, y in pts]
    if closed:
        pts = pts + [pts[0]]
    w = width * k / 2
    for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
        d = math.hypot(x1 - x0, y1 - y0) or 1.0
        nx, ny = -(y1 - y0) / d * w, (x1 - x0) / d * w
        pygame.draw.polygon(surf, color, [(x0 + nx, y0 + ny), (x1 + nx, y1 + ny), (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)])
    for x, y in pts:
        pygame.draw.circle(surf, color, (x, y), w)


def _icon(size, draw):
    big = pygame.Surface((size[0] * SS, size[1] * SS), pygame.SRCALPHA)
    draw(big)
    return pygame.transform.smoothscale(big, size)


def icon_clock(color):
    """Horloge : cercle et deux aiguilles (images 03/09 : 27 px de diamètre)."""
    c = pygame.Color(color)

    def draw(s):
        pygame.draw.circle(s, c, (14.5 * SS, 14.5 * SS), 14 * SS, int(2.4 * SS))
        _stroke(s, [(14.5, 14.5), (14.5, 6.5)], c, 2.3)
        _stroke(s, [(14.5, 14.5), (19.5, 18.5)], c, 2.3)
    return _icon((29, 29), draw)


def icon_bolt(color):
    """Éclair en contour (images 03/09 : 18 × 26 px)."""
    c = pygame.Color(color)
    return _icon((20, 28), lambda s: _stroke(s, [(13.5, 1), (1.5, 16), (9, 16), (6.5, 27), (18.5, 11), (11, 11)],
                                             c, 1.9, closed=True))


def icon_muscle(color):
    """Muscle : fuseau en contour avec fibres et tendons, incliné (images 03/09 : 34 × 24 px)."""
    c = pygame.Color(color)
    ang = math.radians(32)          # monte vers la droite (images 03/09)
    ca, sa = math.cos(ang), math.sin(ang)

    def tf(u, v):   # repère du fuseau (u le long, v en travers) → icône
        return (18 + u * ca - v * sa, 13 - (u * sa + v * ca))

    def draw(s):
        L, W = 12.0, 8.0
        us = np.linspace(-1, 1, 17)
        top = [tf(L * u, W * (1 - u * u) ** 0.7) for u in us]
        bot = [tf(L * u, -W * (1 - u * u) ** 0.7) for u in us[::-1]]
        _stroke(s, top + bot, c, 1.8, closed=True)
        for f in (-0.45, 0.0, 0.45):
            _stroke(s, [tf(L * u, f * W * (1 - u * u) ** 0.7) for u in np.linspace(-0.75, 0.75, 9)], c, 1.4)
        for end in (-1, 1):
            u0 = end * (L + 2.8)
            _stroke(s, [tf(u0 - 2, -2.2), tf(u0 + 2, -2.2), tf(u0 + 2, 2.2), tf(u0 - 2, 2.2)], c, 1.6, closed=True)
    return _icon((36, 26), draw)


def icon_chevrons(color):
    """Triple chevron vers le haut : deux chevrons et une flèche à hampe (images 03/09 : 18 × 34 px)."""
    c = pygame.Color(color)

    def draw(s):
        _stroke(s, [(1.5, 9), (9, 1.5), (16.5, 9)], c, 2.8)
        _stroke(s, [(1.5, 16.5), (9, 9), (16.5, 16.5)], c, 2.8)
        _stroke(s, [(1.5, 24), (9, 16.5), (16.5, 24), (12.2, 24), (12.2, 32.5), (5.8, 32.5), (5.8, 24)], c, 2.6, closed=True)
    return _icon((18, 34), draw)


def icon_fast(color="#FCFCFC", size=None):
    """⏩ : deux triangles blancs."""
    w, h = size or config.FAST_ICON[2:]
    c = pygame.Color(color)

    def draw(s):
        half = w / 2
        for x0 in (0, half):
            pygame.draw.polygon(s, c, [(x0 * SS, 0), ((x0 + half) * SS, h / 2 * SS), (x0 * SS, h * SS)])
    return _icon((int(w), int(h)), draw)


def _rounded(size, radius, rgba):
    surf = pygame.Surface(size, pygame.SRCALPHA)
    pygame.draw.rect(surf, rgba, surf.get_rect(), border_radius=radius)
    return surf


def card_alpha(t):
    """Opacité du carton de génération à l'instant t du replay (pleine, puis fondu)."""
    if t <= config.TITLE_CARD_HOLD_S:
        return 1.0
    return max(0.0, 1.0 - (t - config.TITLE_CARD_HOLD_S) / config.TITLE_CARD_FADE_S)


def format_height(h):
    """Hauteur brute du HUD : « 23.1 m », « -4.9 m » (jamais « -0.0 m »)."""
    return f"{0.0 if abs(h) < 0.05 else h:.1f} m"


# ---------------------------------------------------------------------------
# HUD
# ---------------------------------------------------------------------------
class Hud:
    def __init__(self, framing, gen, period, muscle, rank=None, creature=None, subtitle=None):
        self.framing = framing
        self.gen, self.rank, self.creature = gen, rank, creature
        self.period, self.muscle = period, muscle
        self.subtitle = subtitle
        name = config.HUD_FONT
        self.font = {"badge": fonts.load(name, config.HUD_BADGE_FONT_PX), "text": fonts.load(name, config.HUD_TEXT_FONT_PX),
                     "label": fonts.load(name, config.HUD_LABEL_FONT_PX),
                     "title": fonts.load(name, config.TITLE_CARD_FONT_PX[0]),
                     "subtitle": fonts.load(name, config.TITLE_CARD_FONT_PX[1])}
        self._texts = {}
        self.renders = 0          # nombre de textes rendus (contrôle du cache)
        bg_hex, bg_alpha = config.HUD_BG
        bg = pygame.Color(bg_hex)
        bg.a = bg_alpha
        b = config.HUD_BADGES
        icons = (icon_clock(config.HUD_ICON_COLORS["horloge"]), icon_bolt(config.HUD_ICON_COLORS["energie"]),
                 icon_muscle(config.HUD_ICON_COLORS["muscle"]))
        self.badges = []
        for icon, icon_x in zip(icons, b["icon_x"]):
            surf = _rounded((b["w"], b["h"]), b["radius"], bg)
            surf.blit(icon, icon.get_rect(center=(round(icon_x - b["x"]), round(b["h"] / 2))))
            self.badges.append(surf)
        lab = config.HUD_LABEL
        label = pygame.Surface((lab["w"] + lab["tip"], lab["h"]), pygame.SRCALPHA)
        pygame.draw.rect(label, bg, (0, 0, lab["w"], lab["h"]), border_radius=lab["radius"])
        mid = lab["h"] / 2
        pygame.draw.polygon(label, bg, [(lab["w"], mid - lab["tip_base"] / 2), (lab["w"] + lab["tip"], mid),
                                        (lab["w"], mid + lab["tip_base"] / 2)])
        chev = icon_chevrons(config.HUD_LABEL_ICON)
        label.blit(chev, chev.get_rect(midleft=(lab["icon_x"], mid)))
        self.label = label
        self.fast = icon_fast()
        w, h = framing.size
        veil_hex, veil_alpha = config.TITLE_CARD_VEIL
        self._veil_rgb = pygame.Color(veil_hex)
        self._veil_alpha = veil_alpha
        self.veil = pygame.Surface((w, h), pygame.SRCALPHA)
        self._veil_level = None
        # pré-rendu des textes fixes (pas de pic de temps à la première frame)
        self.text("title", f"Génération {gen}")
        if subtitle:
            self.text("subtitle", subtitle)
        self.text("text", f"Génération: {gen}")
        self.text("text", f"Créature: {creature}" if creature is not None else f"Classement: #{rank}")
        self.text("badge", f"{period:.1f} s")
        self.text("badge", f"{muscle:.1f}")

    # --- textes mis en cache -------------------------------------------------
    def text(self, font, s):
        """(surface, rectangle d'encre dans la surface) ; rendu une seule fois par (police, texte)."""
        key = (font, s)
        if key not in self._texts:
            if len(self._texts) > 512:        # borne mémoire : les valeurs passées ne reviennent pas souvent
                for old in list(self._texts)[:256]:
                    del self._texts[old]
            surf = self.font[font].render(s, True, pygame.Color(config.HUD_TEXT))
            self._texts[key] = (surf, surf.get_bounding_rect())
            self.renders += 1
        return self._texts[key]

    def _blit_ink(self, surface, font, s, left=None, right=None, top=None, center_y=None, center_x=None, alpha=None):
        surf, ink = self.text(font, s)
        x = (left - ink.left if left is not None else right - ink.right if right is not None
             else center_x - ink.centerx)
        y = top - ink.top if top is not None else center_y - ink.centery
        if alpha is not None:
            surf.set_alpha(int(round(255 * alpha)))
        surface.blit(surf, (round(x), round(y)))
        if alpha is not None:
            surf.set_alpha(None)
        return pygame.Rect(round(x) + ink.left, round(y) + ink.top, ink.width, ink.height)

    # --- rendu par frame --------------------------------------------------------
    def label_rect(self, ref_y_px):
        """Rectangle de la boîte de l'étiquette (sans la pointe) pour un point de référence à l'écran."""
        lab = config.HUD_LABEL
        tip_x = self.framing.x_px(config.TRUNK_X - config.TRUNK_WIDTH / 2) + lab["tip_on_trunk"]
        cy = min(max(ref_y_px + lab["dy"], lab["h"] / 2), self.framing.size[1] - lab["h"] / 2)
        return pygame.Rect(round(tip_x - lab["tip"] - lab["w"]), round(cy - lab["h"] / 2), lab["w"], lab["h"])

    def draw(self, surface, t, height, energy, ref_y_px, speed=1.0, card=True):
        b = config.HUD_BADGES
        values = (f"{self.period:.1f} s", f"{energy:.1f}", f"{self.muscle:.1f}")
        for k, (badge, value) in enumerate(zip(self.badges, values)):
            y = b["y"] + k * b["pitch"]
            surface.blit(badge, (b["x"], y))
            self._blit_ink(surface, "badge", value, left=b["text_x"], center_y=y + b["h"] / 2)
        second = f"Créature: {self.creature}" if self.creature is not None else f"Classement: #{self.rank}"
        for top, line in zip(config.HUD_TEXT_TOPS, (f"Génération: {self.gen}", second, f"Temps: {t:.1f} s")):
            self._blit_ink(surface, "text", line, right=config.HUD_TEXT_RIGHT, top=top)
        rect = self.label_rect(ref_y_px)
        surface.blit(self.label, rect.topleft)
        lab = config.HUD_LABEL
        self._blit_ink(surface, "label", format_height(height), left=rect.left + lab["text_x"], center_y=rect.centery - 1)
        if speed > 1:
            x, y = config.FAST_ICON[:2]
            surface.blit(self.fast, (x, y))
        if card:
            self.draw_card(surface, t)

    def draw_card(self, surface, t):
        a = card_alpha(t)
        if a <= 0:
            return
        level = int(round(self._veil_alpha * a))
        if level != self._veil_level:
            self.veil.fill((self._veil_rgb.r, self._veil_rgb.g, self._veil_rgb.b, level))
            self._veil_level = level
        surface.blit(self.veil, (0, 0))
        cx = self.framing.size[0] / 2
        self._blit_ink(surface, "title", f"Génération {self.gen}", center_x=cx, top=config.TITLE_CARD_TOPS[0], alpha=a)
        if self.subtitle:
            self._blit_ink(surface, "subtitle", self.subtitle, center_x=cx, top=config.TITLE_CARD_TOPS[1], alpha=a)
