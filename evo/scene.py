"""Décor jungle (§5.6) : cadrage, caméra, couches pré-rendues avec parallaxe, cache disque.

Chaque couche est dessinée une seule fois (supersampling ×SCENE_SUPERSAMPLE puis réduction), puis
simplement blittée à chaque frame avec son décalage de parallaxe. Les couches sont mises en cache
sur disque (SCENE_CACHE_DIR) ; la clé couvre la graine, les paramètres du décor de config.py, le
code de ce fichier et le cadrage, donc toute modification du dessin régénère le décor.

Repère du monde : x vers la droite, y vers le haut (m), sol à GROUND_Y, tronc centré sur TRUNK_X.
Écran : y vers le bas. `shift` = décalage vertical de la caméra (px, plan de la créature) ; une
couche de parallaxe p est décalée de p × shift.
"""
import hashlib
import json
import math
import os

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import numpy as np
import pygame

import config

BACK_LAYERS = ("ciel", "tres_lointain", "lointain", "mi_proche", "plan")
FRONT_LAYERS = ("premier_plan",)


def _rgb(hex_code):
    return pygame.Color(hex_code)


# ---------------------------------------------------------------------------
# Cadrage et caméra
# ---------------------------------------------------------------------------
class Framing:
    """Échelle (px/m), ligne du sol à l'écran (px) et taille de fenêtre."""

    def __init__(self, size=None, scale=None, ground_px=None):
        self.size = tuple(size or config.WINDOW_SIZE)
        self.scale = float(config.SCENE_SCALE if scale is None else scale)
        self.ground_px = float(config.SCENE_GROUND_PX if ground_px is None else ground_px)

    def x_px(self, x):
        return self.size[0] / 2 + (x - config.TRUNK_X) * self.scale

    def y_px(self, y, shift=0.0):
        return self.ground_px - (y - config.GROUND_Y) * self.scale + shift

    def to_px(self, p, shift=0.0):
        return (self.x_px(p[0]), self.y_px(p[1], shift))

    def origin(self, shift=0.0):
        """(ox, oy) tels que x_px = ox + x·scale et y_px = oy − y·scale."""
        return (self.size[0] / 2 - config.TRUNK_X * self.scale,
                self.ground_px + config.GROUND_Y * self.scale + shift)

    def key(self):
        return [list(self.size), self.scale, self.ground_px]


class Camera:
    """Cadrage fixe au départ, puis suivi vertical en lerp (§5.6) ; bornée par le haut du décor."""

    def __init__(self, framing):
        self.framing = framing
        self.shift = 0.0
        self.max_shift = config.DECOR_TOP_HUD * framing.scale

    def target(self, ref_y):
        """Décalage qui garde le point de référence à la hauteur écran du départ."""
        hud = ref_y - (config.GROUND_Y + config.START_HEIGHT)
        return min(max(0.0, hud * self.framing.scale), self.max_shift)

    def update(self, ref_y, snap=False):
        goal = self.target(ref_y)
        self.shift = goal if snap else self.shift + (goal - self.shift) * config.CAMERA_LERP
        return self.shift

    def to_px(self, p):
        return self.framing.to_px(p, self.shift)

    def origin(self):
        return self.framing.origin(self.shift)


# ---------------------------------------------------------------------------
# Toile d'une couche (supersamplée)
# ---------------------------------------------------------------------------
class _Canvas:
    """Surface haute d'une couche : couvre l'écran pour tout décalage de caméra de 0 à max_shift."""

    def __init__(self, framing, parallax, max_shift, bg_hex, ss=None):
        self.f = framing
        self.parallax = parallax
        self.ss = config.SCENE_SUPERSAMPLE if ss is None else ss
        self.offset = parallax * max_shift   # lignes de la couche au-dessus de l'écran quand shift = 0
        self.width, h = framing.size
        self.height = int(math.ceil(h + self.offset))
        self.surf = pygame.Surface((self.width * self.ss, self.height * self.ss), pygame.SRCALPHA)
        bg = _rgb(bg_hex)
        self.surf.fill((bg.r, bg.g, bg.b, 0))   # fond transparent de la couleur dominante : pas de frange sombre

    # monde (m, espace de la couche) → pixels supersamplés de la couche
    def pt(self, x, y):
        return (self.f.x_px(x) * self.ss, (self.f.y_px(y) + self.offset) * self.ss)

    def poly(self, pts, hex_code):
        pygame.draw.polygon(self.surf, _rgb(hex_code), [self.pt(x, y) for x, y in pts])

    def world_top(self):
        """y monde de la première ligne de la couche."""
        return config.GROUND_Y + (self.f.ground_px + self.offset) / self.f.scale

    def world_bottom(self):
        return config.GROUND_Y - (self.f.size[1] - self.f.ground_px) / self.f.scale

    def world_x_range(self, margin=2.0):
        half = self.f.size[0] / 2 / self.f.scale
        return config.TRUNK_X - half - margin, config.TRUNK_X + half + margin

    def finish(self):
        if self.ss == 1:
            return self.surf
        return pygame.transform.smoothscale(self.surf, (self.width, self.height))


# ---------------------------------------------------------------------------
# Scène
# ---------------------------------------------------------------------------
class Scene:
    """Couches du décor (§5.6), construites ou relues depuis le cache disque."""

    def __init__(self, framing=None, layers=None, use_cache=True, log=None):
        self.framing = framing or Framing()
        self.layer_names = tuple(config.SCENE_LAYERS if layers is None else layers)
        self.max_shift = config.DECOR_TOP_HUD * self.framing.scale
        self.markers = [k * config.MARKER_STEP for k in range(1, int(config.DECOR_TOP_HUD // config.MARKER_STEP) + 1)]
        self.key = cache_key(self.framing, self.layer_names)
        self.layers = {}   # nom → (surface, parallaxe, décalage)
        self.built = False
        self.cache_path = os.path.join(_cache_root(), self.key)
        if not (use_cache and self._load()):
            self._build()
            self.built = True
            if use_cache:
                self._save()
        if log:
            log(f"décor {'construit' if self.built else 'relu du cache'} ({self.cache_path})")
        if pygame.display.get_init() and pygame.display.get_surface() is not None:
            self.layers = {n: (s.convert() if n == "ciel" else s.convert_alpha(), p, o)
                           for n, (s, p, o) in self.layers.items()}

    # --- rendu par frame ---------------------------------------------------
    def _blit(self, surface, name, shift):
        surf, p, offset = self.layers[name]
        top = int(round(offset - p * min(max(shift, 0.0), self.max_shift)))
        surface.blit(surf, (0, 0), pygame.Rect(0, top, self.framing.size[0], self.framing.size[1]))

    def draw_back(self, surface, shift):
        """Ciel, arrière-plans et plan de la créature (tronc, sol, repères)."""
        for name in BACK_LAYERS:
            if name in self.layers:
                self._blit(surface, name, shift)

    def draw_front(self, surface, shift):
        """Premier plan, qui passe devant le lézard."""
        for name in FRONT_LAYERS:
            if name in self.layers:
                self._blit(surface, name, shift)

    # --- construction ------------------------------------------------------
    def _build(self):
        builders = {"ciel": self._build_sky, "plan": self._build_plane}
        order = BACK_LAYERS + FRONT_LAYERS
        for name in self.layer_names:
            # une graine par couche : ajouter ou retirer une couche ne change pas les autres
            surf, offset = builders[name](np.random.default_rng([config.SCENE_SEED, order.index(name)]))
            self.layers[name] = (surf, config.PARALLAX[name], offset)

    def _build_sky(self, rng):
        """§5.2 : dégradé vertical (fixe à l'écran) et traits de nuages plats."""
        f = self.framing
        w, h = f.size
        k = config.SCENE_SCALE / f.scale   # cadrage serré : on lit le dégradé du cadrage standard
        stops = config.SKY_STOPS
        ys = np.array([y for y, _ in stops], dtype=float)
        cols = np.array([tuple(_rgb(c))[:3] for _, c in stops], dtype=float)
        ss = config.SCENE_SUPERSAMPLE
        surf = pygame.Surface((w * ss, h * ss))
        for row in range(h * ss):
            y_std = config.SCENE_GROUND_PX + ((row + 0.5) / ss - f.ground_px) * k
            rgb = [np.interp(y_std, ys, cols[:, c]) for c in range(3)]
            pygame.draw.line(surf, [int(round(v)) for v in rgb], (0, row), (w * ss, row))
        for x0, x1, y0, th in config.CLOUDS:
            def to_screen(x, y):
                return ((w / 2 + (x - w / 2) / k) * ss, (f.ground_px + (y - config.SCENE_GROUND_PX) / k) * ss)
            slant = 0.8 * th
            pts = [(x0 + slant, y0), (x1, y0), (x1 - slant, y0 + th), (x0, y0 + th)]
            pygame.draw.polygon(surf, _rgb(config.CLOUD_COLOR), [to_screen(x, y) for x, y in pts])
        if ss > 1:
            surf = pygame.transform.smoothscale(surf, (w, h))
        return surf, 0.0

    def _build_plane(self, rng):
        """Plan de la créature (parallaxe 1) : branches, tronc, sol, rochers, touffes, repères."""
        cv = _Canvas(self.framing, config.PARALLAX["plan"], self.max_shift, config.TRUNK_COLORS[4])
        top, bottom = cv.world_top() + 2.0, cv.world_bottom() - 2.0
        _branches(cv)
        _trunk(cv, rng, config.GROUND_Y - 0.6, top)
        _ground(cv, rng, bottom)
        _rocks(cv)
        _tufts(cv, rng)
        surf = cv.finish()
        _markers(surf, cv)
        return surf, cv.offset

    # --- cache -------------------------------------------------------------
    def _load(self):
        manifest = os.path.join(self.cache_path, "manifest.json")
        if not os.path.exists(manifest):
            return False
        try:
            with open(manifest) as fh:
                meta = json.load(fh)
            if meta.get("key") != self.key or set(meta["layers"]) != set(self.layer_names):
                return False
            for name, info in meta["layers"].items():
                surf = pygame.image.load(os.path.join(self.cache_path, f"{name}.png"))
                self.layers[name] = (surf, float(info["parallax"]), float(info["offset"]))
            return True
        except (OSError, ValueError, KeyError, pygame.error):
            self.layers = {}
            return False

    def _save(self):
        _prune_cache()
        os.makedirs(self.cache_path, exist_ok=True)
        meta = {"key": self.key, "seed": config.SCENE_SEED, "framing": self.framing.key(),
                "source": _source_digest(), "layers": {}}
        for name, (surf, p, offset) in self.layers.items():
            pygame.image.save(surf, os.path.join(self.cache_path, f"{name}.png"))
            meta["layers"][name] = {"parallax": p, "offset": offset, "size": list(surf.get_size())}
        with open(os.path.join(self.cache_path, "manifest.json"), "w") as fh:
            json.dump(meta, fh, indent=1)


# ---------------------------------------------------------------------------
# Cache : clé = graine + paramètres du décor + code de ce fichier + cadrage
# ---------------------------------------------------------------------------
_DECOR_PREFIXES = ("SCENE_", "SKY_", "CLOUD", "TRUNK_", "BRANCH", "GRASS_", "DIRT_", "ROCK",
                   "TUFT", "MARKER_", "DECOR_", "PARALLAX")
_DECOR_KEYS = ("START_HEIGHT", "GROUND_Y", "FONT_SANS")


def decor_params():
    keys = sorted(k for k in dir(config) if k.isupper() and (k.startswith(_DECOR_PREFIXES) or k in _DECOR_KEYS))
    return {k: getattr(config, k) for k in keys}


def _source_digest():
    with open(__file__, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def cache_key(framing, layers):
    payload = json.dumps({"params": decor_params(), "framing": framing.key(), "layers": list(layers),
                          "source": _source_digest()}, sort_keys=True, default=list)
    return hashlib.sha256(payload.encode()).hexdigest()[:20]


def _prune_cache():
    """Supprime les décors construits par une autre version de ce fichier (ils ne resserviront plus)."""
    import shutil

    root = _cache_root()
    if not os.path.isdir(root):
        return
    current = _source_digest()
    for name in os.listdir(root):
        manifest = os.path.join(root, name, "manifest.json")
        try:
            with open(manifest) as fh:
                stale = json.load(fh).get("source") != current
        except (OSError, ValueError):
            stale = True
        if stale:
            shutil.rmtree(os.path.join(root, name), ignore_errors=True)


def _cache_root():
    root = config.SCENE_CACHE_DIR
    if not os.path.isabs(root):
        root = os.path.join(os.path.dirname(os.path.abspath(config.__file__)), root)
    return root


# ---------------------------------------------------------------------------
# Éléments du plan de la créature
# ---------------------------------------------------------------------------
def _trunk_half_width(y):
    """Demi-largeur du tronc, avec la base évasée (TRUNK_FLARE)."""
    fh, fw = config.TRUNK_FLARE
    hy = y - config.GROUND_Y
    extra = fw if hy <= 0 else (fw * (1 - hy / fh) ** 1.6 if hy < fh else 0.0)
    return config.TRUNK_WIDTH / 2 + extra


def _trunk(cv, rng, bottom, top):
    """Tronc à facettes : rangées de sommets décalées et jitterées, triangulées en fermeture éclair ;
    teinte = position horizontale (clair à gauche) ± hasard. La base évasée est un liseré lisse."""
    fw, fh = config.TRUNK_FACET
    jit = config.TRUNK_JITTER
    half = config.TRUNK_WIDTH / 2
    left, right = config.TRUNK_X - half, config.TRUNK_X + half
    n_cols = max(2, int(round(config.TRUNK_WIDTH / fw)))
    n_rows = max(1, int(math.ceil((top - bottom) / fh)))
    rows = []
    for j in range(n_rows + 1):
        y0 = bottom + j * (top - bottom) / n_rows
        inner = n_cols - 1 if j % 2 == 0 else n_cols        # rangées décalées d'une demi-facette
        row = [(left, y0 + (rng.uniform(-0.5, 0.5) * jit * fh if 0 < j < n_rows else 0.0))]
        for i in range(inner):
            u = (i + 1) / n_cols if j % 2 == 0 else (i + 0.5) / n_cols
            x = left + (u + rng.uniform(-0.5, 0.5) * jit / n_cols) * config.TRUNK_WIDTH
            y = y0 + (rng.uniform(-0.5, 0.5) * jit * fh if 0 < j < n_rows else 0.0)
            row.append((x, y))
        row.append((right, y0 + (rng.uniform(-0.5, 0.5) * jit * fh if 0 < j < n_rows else 0.0)))
        rows.append(row)
    n_shades = len(config.TRUNK_COLORS)

    def shade(tri):
        cx = sum(p[0] for p in tri) / 3
        t = (cx - left) / config.TRUNK_WIDTH
        return config.TRUNK_COLORS[int(np.clip(math.floor(t * n_shades + rng.uniform(-1, 1) * config.TRUNK_SHADE_JITTER),
                                               0, n_shades - 1))]

    for lo, hi in zip(rows[:-1], rows[1:]):
        i = k = 0
        while i < len(lo) - 1 or k < len(hi) - 1:
            advance_lo = k == len(hi) - 1 or (i < len(lo) - 1 and lo[i + 1][0] <= hi[k + 1][0])
            tri = (lo[i], hi[k], lo[i + 1]) if advance_lo else (lo[i], hi[k], hi[k + 1])
            cv.poly(tri, shade(tri))
            if advance_lo:
                i += 1
            else:
                k += 1
    # base évasée : liseré lisse de chaque côté, en deux facettes
    fh_flare = config.TRUNK_FLARE[0]
    ys = np.linspace(config.GROUND_Y + fh_flare, bottom, 14)
    for side, (c_hi, c_lo) in ((-1, (config.TRUNK_COLORS[1], config.TRUNK_COLORS[0])),
                               (1, (config.TRUNK_COLORS[-2], config.TRUNK_COLORS[-1]))):
        edge = [(config.TRUNK_X + side * _trunk_half_width(y), y) for y in ys]
        inner_x = config.TRUNK_X + side * (half - 0.02)   # le liseré ne couvre que ce qui dépasse du fût
        mid = len(edge) // 2
        cv.poly([(inner_x, ys[0])] + edge[:mid + 1] + [(inner_x, edge[mid][1])], c_hi)
        cv.poly([(inner_x, edge[mid][1])] + edge[mid:] + [(inner_x, ys[-1])], c_lo)


def _branches(cv):
    """Branches en L (diagonale puis poteau vertical), qui partent de derrière le tronc."""
    base_y = config.GROUND_Y + config.START_HEIGHT
    for hud, side, dx, dy, post, th in config.BRANCHES:
        y0 = base_y + hud
        edge = config.TRUNK_X + side * config.TRUNK_WIDTH / 2
        x_in = edge - side * 1.5
        x_end = edge + side * dx
        x_post = x_end - side * th
        # diagonale : bande d'épaisseur verticale th, du tronc jusqu'au pied du poteau
        cv.poly([(x_in, y0), (x_end, y0 + dy), (x_end, y0 + dy + th), (x_in, y0 + th)], config.BRANCH_COLOR)
        # face du dessus éclairée (lumière de la gauche) : liseré le long du bord supérieur
        cv.poly([(x_in, y0 + 0.62 * th), (x_post, y0 + dy + 0.62 * th), (x_post, y0 + dy + th), (x_in, y0 + th)],
                config.BRANCH_FACET)
        # poteau vertical, face gauche éclairée
        left, right = sorted((x_post, x_end))
        cv.poly([(left, y0 + dy), (right, y0 + dy), (right, y0 + dy + post), (left, y0 + dy + post)], config.BRANCH_COLOR)
        cv.poly([(left, y0 + dy + th), (left + 0.38 * th, y0 + dy + th), (left + 0.38 * th, y0 + dy + post),
                 (left, y0 + dy + post)], config.BRANCH_FACET)


def _teeth(rng, x0, x1, depth, amp):
    """Bord dentelé : alternance de pointes irrégulières autour de y = −depth."""
    lo, hi = config.GRASS_TEETH
    pts, x, down = [], x0, True
    while x < x1 + hi:
        y = -depth - (rng.uniform(0.35, 1.0) * amp if down else -rng.uniform(0.0, 0.6) * amp)
        pts.append((x, config.GROUND_Y + y))
        x += rng.uniform(lo, hi) * (0.35 if down else 0.65)
        down = not down
    return pts


def _ground(cv, rng, bottom):
    """Herbe (bande claire + bande sombre au bord dentelé), terre à facettes, ombre du tronc."""
    x0, x1 = cv.world_x_range()
    g = config.GROUND_Y
    light, total, amp = config.GRASS_BANDS
    dirt, dirt_dark = config.DIRT_COLORS
    # terre et facettes verticales
    cv.poly([(x0, g - light), (x1, g - light), (x1, bottom), (x0, bottom)], dirt)
    x = x0
    while x < x1:
        w = rng.uniform(*config.DIRT_FACETS)
        if rng.random() < 0.5:
            s1, s2 = rng.uniform(-1.5, 1.5, 2)
            cv.poly([(x + s1, g - total), (x + w + s2, g - total), (x + w - s2, bottom), (x - s1, bottom)], dirt_dark)
        x += w
    # bord dentelé de l'herbe et liseré sombre de la terre juste dessous
    edge = _teeth(rng, x0, x1, total, amp)
    shadow = [(px, py - 0.55) for px, py in edge]
    cv.poly([(x0, g - light)] + shadow + [(x1 + 8, g - light)], dirt_dark)
    cv.poly([(x0, g - light)] + edge + [(x1 + 8, g - light)], config.GRASS_COLORS[1])
    cv.poly([(x0, g), (x1, g), (x1, g - light), (x0, g - light)], config.GRASS_COLORS[0])
    # ombre du tronc portée vers la droite (lumière de la gauche)
    length, th = config.TRUNK_SHADOW
    xr = config.TRUNK_X + _trunk_half_width(g) - 0.4
    cv.poly([(xr, g), (xr + 0.75 * length, g), (xr + length, g - 0.45 * th), (xr + 0.8 * length, g - th), (xr, g - th)],
            config.GRASS_COLORS[1])


def _rocks(cv):
    """Petits rochers low-poly en trois facettes (claire en haut à gauche)."""
    light, mid, dark = config.ROCK_COLORS
    g = config.GROUND_Y - 0.15
    for x, s in config.ROCKS:
        a, b, c = (x - 0.5 * s, g), (x - 0.47 * s, g + 0.48 * s), (x - 0.05 * s, g + 0.82 * s)
        d, e, m = (x + 0.46 * s, g + 0.58 * s), (x + 0.5 * s, g + 0.02 * s), (x - 0.02 * s, g + 0.38 * s)
        cv.poly([a, b, m, e], dark)
        cv.poly([m, c, d, e], mid)
        cv.poly([b, c, m], light)


def _tufts(cv, rng):
    """Touffes d'herbe pointues, feuilles sombres derrière et claires devant."""
    dark, light, _ = config.TUFT_COLORS
    g = config.GROUND_Y - 0.25
    for x, h in config.TUFTS:
        n = int(rng.integers(3, 6))
        blades = sorted(((rng.uniform(-0.55, 0.6) * h, rng.uniform(0.55, 1.0) * h) for _ in range(n)),
                        key=lambda b: -b[1])
        for k, (dx, bh) in enumerate(blades):
            base = x + rng.uniform(-0.25, 0.25) * h
            w = 0.16 * h
            cv.poly([(base - w, g), (base + w, g), (x + dx, g + bh)], light if k % 2 else dark)


def _markers(surf, cv):
    """Repères de hauteur (hauteur HUD) : ligne blanche sur le tronc et libellé « 10 m » à gauche."""
    f = cv.f
    pygame.font.init()
    font = pygame.font.SysFont(config.FONT_SANS, int(round(config.MARKER_FONT_PX * f.scale / config.SCENE_SCALE)))
    color = _rgb(config.MARKER_COLOR)
    left = int(round(f.x_px(config.TRUNK_X - config.TRUNK_WIDTH / 2)))
    right = int(round(f.x_px(config.TRUNK_X + config.TRUNK_WIDTH / 2)))
    gap = config.MARKER_LABEL_GAP_PX * f.scale / config.SCENE_SCALE
    base = config.GROUND_Y + config.START_HEIGHT
    for hud in range(int(config.MARKER_STEP), int(config.DECOR_TOP_HUD) + 1, int(config.MARKER_STEP)):
        row = f.y_px(base + hud) + cv.offset
        if not 0 <= row < surf.get_height():
            continue
        y = int(round(row))
        pygame.draw.rect(surf, color, (left, y - config.MARKER_LINE_PX // 2, right - left, config.MARKER_LINE_PX))
        label = font.render(f"{hud} m", True, color)
        surf.blit(label, label.get_rect(midright=(int(round(left - gap)), y)))
