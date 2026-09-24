"""Dessin dans le style des schémas pédagogiques de la vidéo (images 19–23).

Fond clair, points rouges, os gris-violet, flèches vertes (vitesse/force) et orange (gravité).
La caméra convertit des mètres (y vers le haut) en pixels (y vers le bas).
"""
import math

import pygame

import config


def color(hex_code):
    return pygame.Color(hex_code)


def load_fonts():
    pygame.font.init()
    return {
        "title": pygame.font.SysFont(config.FONT_MONO, 40),
        "label": pygame.font.SysFont(config.FONT_SANS, 22),
        "small": pygame.font.SysFont(config.FONT_SANS, 17),
        "mono": pygame.font.SysFont(config.FONT_MONO, 16),
        "mass": pygame.font.SysFont(config.FONT_SANS, 44, bold=True),
        "mass_small": pygame.font.SysFont(config.FONT_SANS, 22, bold=True),
        "half": pygame.font.SysFont(config.FONT_SANS, 30),
    }


class Painter:
    def __init__(self, surface, fonts):
        self.surface = surface
        self.fonts = fonts
        self.origin = (surface.get_width() / 2, surface.get_height() / 2)
        self.scale = 100.0

    # --- caméra -----------------------------------------------------------
    def set_camera(self, origin_px, scale):
        self.origin = origin_px
        self.scale = scale

    def to_px(self, p):
        return (self.origin[0] + p[0] * self.scale, self.origin[1] - p[1] * self.scale)

    # --- primitives en pixels ------------------------------------------------
    def clear(self, hex_code=config.SCHEMA_BG):
        self.surface.fill(color(hex_code))

    def line_px(self, a, b, hex_code, width):
        a, b = _ipt(a), _ipt(b)
        pygame.draw.line(self.surface, color(hex_code), a, b, width)
        # extrémités arrondies, comme les os des schémas
        if width > 3:
            pygame.draw.circle(self.surface, color(hex_code), a, width // 2)
            pygame.draw.circle(self.surface, color(hex_code), b, width // 2)

    def dashed_px(self, a, b, hex_code, width=2, dash=8):
        length = math.dist(a, b)
        if length < 1e-6:
            return
        n = max(1, int(length // (2 * dash)))
        for k in range(n + 1):
            t0 = min(1.0, 2 * k * dash / length)
            t1 = min(1.0, (2 * k + 1) * dash / length)
            p0 = (a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0)
            p1 = (a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1)
            pygame.draw.line(self.surface, color(hex_code), _ipt(p0), _ipt(p1), width)

    def arrow_px(self, start, end, hex_code, width=8):
        """Flèche pleine : hampe épaisse + tête triangulaire (style image 19)."""
        dx, dy = end[0] - start[0], end[1] - start[1]
        length = math.hypot(dx, dy)
        if length < 2:
            return
        ux, uy = dx / length, dy / length
        head = min(length * 0.6, width * 2.6)
        base = (end[0] - ux * head, end[1] - uy * head)
        pygame.draw.line(self.surface, color(hex_code), _ipt(start), _ipt(base), width)
        half = width * 1.4
        tip = [end,
               (base[0] - uy * half, base[1] + ux * half),
               (base[0] + uy * half, base[1] - ux * half)]
        pygame.draw.polygon(self.surface, color(hex_code), [_ipt(p) for p in tip])

    def text(self, s, pos, font="label", hex_code=config.SCHEMA_TEXT, anchor="topleft"):
        surf = self.fonts[font].render(s, True, color(hex_code))
        rect = surf.get_rect(**{anchor: _ipt(pos)})
        self.surface.blit(surf, rect)
        return rect

    # --- primitives en mètres -------------------------------------------------
    def bone(self, a, b, width=10, hex_code=config.SCHEMA_BONE):
        self.line_px(self.to_px(a), self.to_px(b), hex_code, width)

    def point(self, p, radius=14, held=False, hex_code=None):
        c = self.to_px(p)
        if held:
            pygame.draw.circle(self.surface, color(hex_code or config.SCHEMA_POINT_HELD), _ipt(c), radius)
            self.hold_cross(c, radius)
        else:
            pygame.draw.circle(self.surface, color(hex_code or config.SCHEMA_POINT), _ipt(c), radius)

    def hold_cross(self, c, radius):
        r = radius * 1.25
        w = max(2, radius // 3)
        cross = pygame.Surface((int(2 * r + 2 * w), int(2 * r + 2 * w)), pygame.SRCALPHA)
        cc = (cross.get_width() / 2, cross.get_height() / 2)
        rgba = color(config.SCHEMA_HOLD_CROSS)
        rgba.a = 220
        pygame.draw.line(cross, rgba, _ipt((cc[0] - r, cc[1] - r)), _ipt((cc[0] + r, cc[1] + r)), w)
        pygame.draw.line(cross, rgba, _ipt((cc[0] - r, cc[1] + r)), _ipt((cc[0] + r, cc[1] - r)), w)
        self.surface.blit(cross, cross.get_rect(center=_ipt(c)))

    def arrow(self, p, vec, px_per_unit, hex_code=config.SCHEMA_VELOCITY, width=8):
        """Flèche partant du point p (m), vecteur `vec` affiché à `px_per_unit` pixels par unité."""
        start = self.to_px(p)
        end = (start[0] + vec[0] * px_per_unit, start[1] - vec[1] * px_per_unit)
        self.arrow_px(start, end, hex_code, width)

    def gravity_field(self, arrows, t, speed_px=40.0, size=10, top=100, bottom=600):
        """Flèches orange qui tombent en boucle entre `top` et `bottom` (slide Gravity())."""
        span = bottom - top
        for x, y in arrows:
            yy = top + (y + t * speed_px) % span
            self.arrow_px((x, yy), (x, yy + 3.2 * size), config.SCHEMA_GRAVITY, size)

def _ipt(p):
    return (int(round(p[0])), int(round(p[1])))
