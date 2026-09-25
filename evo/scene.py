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
        self._prepare_markers()
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
        # nombre de pixels non transparents par ligne du premier plan (mesure des frames avec canopée)
        self._front_rows = {n: (pygame.surfarray.array_alpha(self.layers[n][0]) > 0).sum(axis=0)
                            for n in FRONT_LAYERS if n in self.layers}
        if pygame.display.get_init() and pygame.display.get_surface() is not None:
            self.layers = {n: (s.convert() if n == "ciel" else _rle(s.convert_alpha()), p, o)
                           for n, (s, p, o) in self.layers.items()}

    # --- rendu par frame ---------------------------------------------------
    def _blit(self, surface, name, shift):
        surf, p, offset = self.layers[name]
        top = int(round(offset - p * min(max(shift, 0.0), self.max_shift)))
        surface.blit(surf, (0, 0), pygame.Rect(0, top, self.framing.size[0], self.framing.size[1]))

    def draw_back(self, surface, shift):
        """Ciel, arrière-plans et plan de la créature (tronc, sol)."""
        for name in BACK_LAYERS:
            if name in self.layers:
                self._blit(surface, name, shift)

    def draw_markers(self, surface, shift, alphas):
        """Repères de hauteur (§5.6) : ligne blanche sur le tronc et libellé à gauche, avec l'opacité
        de chaque repère (`alphas` : hauteur HUD → opacité 0–1, cf. marker_alpha)."""
        f = self.framing
        h = f.size[1]
        base = config.GROUND_Y + config.START_HEIGHT
        for hud, alpha in alphas.items():
            if alpha <= 0.0 or hud not in self._marker_labels:
                continue
            y = int(round(f.y_px(base + hud, shift)))
            label = self._marker_labels[hud]
            if -label.get_height() < y < h + label.get_height():
                a = int(round(255 * min(alpha, 1.0)))
                self._marker_line.set_alpha(a)
                label.set_alpha(a)
                surface.blit(self._marker_line, (self._marker_left, y - config.MARKER_LINE_PX // 2))
                surface.blit(label, label.get_rect(midright=(self._marker_label_x, y)))

    def front_coverage(self, shift):
        """Part des pixels de l'écran couverts par le premier plan pour ce décalage de caméra."""
        total = 0
        w, h = self.framing.size
        for name, rows in self._front_rows.items():
            _, p, offset = self.layers[name]
            top = int(round(offset - p * min(max(shift, 0.0), self.max_shift)))
            total += int(rows[max(top, 0):max(top + h, 0)].sum())
        return total / float(w * h)

    def _prepare_markers(self):
        f = self.framing
        from evo import fonts
        font = fonts.load(config.HUD_FONT, int(round(config.MARKER_FONT_PX * f.scale / config.SCENE_SCALE)))
        self._marker_color = _rgb(config.MARKER_COLOR)
        self._marker_labels = {hud: font.render(f"{hud:g} m", True, self._marker_color) for hud in self.markers}
        self._marker_left = int(round(f.x_px(config.TRUNK_X - config.TRUNK_WIDTH / 2)))
        self._marker_right = int(round(f.x_px(config.TRUNK_X + config.TRUNK_WIDTH / 2)))
        self._marker_line = pygame.Surface((self._marker_right - self._marker_left, config.MARKER_LINE_PX))
        self._marker_line.fill(self._marker_color)
        self._marker_label_x = int(round(self._marker_left - config.MARKER_LABEL_GAP_PX * f.scale / config.SCENE_SCALE))

    def draw_front(self, surface, shift):
        """Premier plan, qui passe devant le lézard."""
        for name in FRONT_LAYERS:
            if name in self.layers:
                self._blit(surface, name, shift)

    # --- construction ------------------------------------------------------
    def _build(self):
        builders = {"ciel": self._build_sky, "tres_lointain": self._build_far, "lointain": self._build_distant,
                    "mi_proche": self._build_mid, "plan": self._build_plane, "premier_plan": self._build_front}
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
        """Plan de la créature (parallaxe 1) : branches, tronc, sol, rochers, touffes."""
        cv = _Canvas(self.framing, config.PARALLAX["plan"], self.max_shift, config.TRUNK_COLORS[4])
        top, bottom = cv.world_top() + 2.0, cv.world_bottom() - 2.0
        for x, height, lean, span in config.PLANE_PALMS:
            _palm(cv, rng, x, config.GROUND_Y - 0.5, height, lean, span, config.PALM_COLORS, detailed=True)
        for x, height, width in config.PLANE_FERNS:
            _fern(cv, rng, x, config.GROUND_Y - 0.3, height, width, config.FERN_COLORS)
        _branches(cv)
        _trunk(cv, rng, config.GROUND_Y - 0.6, top)
        _ground(cv, rng, bottom)
        _rocks(cv)
        _tufts(cv, rng)
        return cv.finish(), cv.offset

    def _build_far(self, rng):
        """Couche 1 (très lointain) : brume, collines, arbres et palmiers en silhouettes pâles."""
        cv = _Canvas(self.framing, config.PARALLAX["tres_lointain"], self.max_shift, config.FAR_COLORS[1])
        x0, x1 = cv.world_x_range(6.0)
        bottom = cv.world_bottom() - 2.0
        haze, pale = config.FAR_COLORS
        _hills(cv, rng, x0, x1, 7.5, 3.0, bottom, haze, n=7)
        n_trees, n_palms = config.FAR_COUNTS
        for x in rng.uniform(x0, x1, n_palms):
            _palm(cv, rng, x, 7.0, rng.uniform(5.0, 7.5), rng.uniform(-12, 12), rng.uniform(4.0, 6.0), (haze,) * 4)
        _hills(cv, rng, x0, x1, 4.5, 2.2, bottom, pale, n=6)
        for x in rng.uniform(x0, x1, n_trees):
            _tree_silhouette(cv, rng, x, bottom, rng.uniform(9.0, 14.0), rng.uniform(5.0, 8.0), pale)
        for x in rng.uniform(x0, x1, n_palms):
            _palm(cv, rng, x, 3.5, rng.uniform(5.5, 8.0), rng.uniform(-14, 14), rng.uniform(4.5, 6.5), (pale,) * 4)
        return cv.finish(), cv.offset

    def _build_distant(self, rng):
        """Couche 2 (lointain) : relief, gros arbres à canopée arrondie avec lianes, palmiers ; kaki."""
        cv = _Canvas(self.framing, config.PARALLAX["lointain"], self.max_shift, config.DISTANT_COLORS[0])
        x0, x1 = cv.world_x_range(6.0)
        bottom = cv.world_bottom() - 2.0
        kaki, kaki2 = config.DISTANT_COLORS
        n_trees, n_palms = config.DISTANT_COUNTS
        for x in rng.uniform(x0, x1, n_palms):
            _palm(cv, rng, x, 1.5, rng.uniform(6.5, 9.5), rng.uniform(-14, 14), rng.uniform(5.5, 7.5), (kaki2,) * 4)
        for x, height, width in config.DISTANT_TREES:
            _tree_silhouette(cv, rng, x, bottom, height, width, kaki)
        for x in rng.uniform(x0, x1, n_trees):
            _tree_silhouette(cv, rng, x, bottom, rng.uniform(10.0, 16.0), rng.uniform(6.0, 9.0), kaki)
        _hills(cv, rng, x0, x1, 2.4, 2.4, bottom, kaki, n=6)
        return cv.finish(), cv.offset

    def _build_mid(self, rng):
        """Couche 3 (mi-proche) : collines sombres, palmiers en deux tons, fougères, arbre latéral."""
        cv = _Canvas(self.framing, config.PARALLAX["mi_proche"], self.max_shift, config.MID_HILL_COLOR)
        x0, x1 = cv.world_x_range(6.0)
        top, bottom = cv.world_top() + 2.0, cv.world_bottom() - 2.0
        dark, lit, trunk = config.MID_PALM_COLORS
        for x, height, lean in config.MID_PALMS:
            _palm(cv, rng, x, 0.8, height, lean, 0.85 * height, (dark, lit, lit, trunk), detailed=True, coconut=False)
        _hills(cv, rng, x0, x1, 1.6, 1.3, bottom, config.MID_HILL_COLOR, n=5)
        for x, height in config.MID_FERNS:
            _fern(cv, rng, x, 0.4, height, 1.4 * height, (config.MID_PALM_COLORS[0], config.MID_HILL_COLOR,
                                                           config.MID_PALM_COLORS[1]))
        _side_tree(cv, rng, bottom, top)
        return cv.finish(), cv.offset

    def _build_front(self, rng):
        """Couche 6 (premier plan) : grandes canopées low-poly portées par les branches du tronc,
        dessinées après le lézard (elles le masquent quand il passe dessous)."""
        cv = _Canvas(self.framing, config.PARALLAX["premier_plan"], self.max_shift, config.CANOPY_COLORS[0])
        base_y = config.GROUND_Y + config.START_HEIGHT
        for (hud, side, dx, dy, post, th), (off, width, height) in zip(config.BRANCHES, config.FG_CANOPIES):
            bottom = base_y + hud + dy + config.FG_CANOPY_LIFT
            _canopy(cv, rng, config.TRUNK_X + side * off, bottom, width, height, config.CANOPY_COLORS, vines=True)
        return cv.finish(), cv.offset

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


def marker_alpha(dt):
    """Opacité d'un repère `dt` secondes après son premier franchissement (négatif : pas encore)."""
    if dt < 0:
        return 0.0
    if dt <= config.MARKER_SHOW_S:
        return 1.0
    return max(0.0, 1.0 - (dt - config.MARKER_SHOW_S) / config.MARKER_FADE_S)


def _rle(surf):
    """Encodage RLE de SDL : les pixels transparents sont sautés au blit (4 à 8 fois plus rapide
    pour ces couches, qui sont transparentes à 50–90 % ; écart ≤ 2 niveaux sur les bords)."""
    surf.set_alpha(255, pygame.RLEACCEL)
    # l'encodage se fait au premier blit vers l'écran : on le déclenche dès le chargement (1 pixel)
    pygame.display.get_surface().blit(surf, (0, 0), pygame.Rect(0, 0, 1, 1))
    return surf


# ---------------------------------------------------------------------------
# Cache : clé = graine + paramètres du décor + code de ce fichier + cadrage
# ---------------------------------------------------------------------------
_DECOR_PREFIXES = ("SCENE_", "SKY_", "CLOUD", "TRUNK_", "BRANCH", "GRASS_", "DIRT_", "ROCK",
                   "TUFT", "MARKER_", "DECOR_", "PARALLAX", "FAR_", "DISTANT_", "MID_", "SIDE_", "PALM_",
                   "COCONUT_", "FERN_", "CANOPY_", "VINE_", "PLANE_", "FG_")
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


# ---------------------------------------------------------------------------
# Éléments des arrière-plans et du premier plan
# ---------------------------------------------------------------------------
def _hills(cv, rng, x0, x1, base, amp, bottom, color, n=6):
    """Relief low-poly : ligne brisée de n sommets autour de y = base, remplie jusqu'en bas."""
    xs = np.sort(np.concatenate([[x0 - 5, x1 + 5], rng.uniform(x0, x1, 2 * n)]))
    ys = config.GROUND_Y + base + rng.uniform(-0.3, 1.0, len(xs)) * amp
    ys[1::2] -= 0.6 * amp          # alternance sommet / creux
    cv.poly([(x0 - 5, bottom)] + list(zip(xs, ys)) + [(x1 + 5, bottom)], color)


def _round_blob(rng, cx, cy, width, height, n=None, jitter=0.12):
    """Blob arrondi irrégulier (silhouettes lointaines) : 11 à 14 sommets autour d'une ellipse complète."""
    n = int(rng.integers(11, 15)) if n is None else n
    pts = []
    for k in range(n):
        a = 2 * math.pi * (k + rng.uniform(-0.3, 0.3)) / n
        r = 1.0 + rng.uniform(-jitter, jitter)
        pts.append((cx + 0.5 * width * r * math.cos(a), cy + 0.5 * height * r * math.sin(a)))
    return pts


def _canopy_parts(rng, cx, bottom, width, height):
    """Contour low-poly irrégulier d'une canopée (images 06 et 09) : (pointe gauche, dessus de gauche à
    droite, pointe droite, dessous de droite à gauche). 8 à 12 sommets : dessus bosselé de 5 à 7 sommets,
    dessous en zigzag de 2 ou 3 sommets. Le dessus reste au-dessus de 58 % de la hauteur sur les 70 %
    centraux de la largeur (le lézard qui passe dessous reste masqué)."""
    n_top, n_bot = int(rng.integers(5, 8)), int(rng.integers(2, 4))
    left = (cx - 0.5 * width, bottom + height * rng.uniform(0.38, 0.52))
    right = (cx + 0.5 * width, bottom + height * rng.uniform(0.35, 0.55))
    us = np.sort(rng.uniform(-0.44, 0.44, n_top))
    us = np.clip(us + np.linspace(-0.05, 0.05, n_top), -0.46, 0.46)       # évite deux sommets confondus
    top = []
    for k, u in enumerate(us):
        envelope = 0.62 + 0.38 * math.sqrt(max(0.0, 1.0 - (2.0 * u) ** 2))
        v = envelope * rng.uniform(0.8, 1.0) * (0.9 if k % 2 else 1.0)   # bosses et marches
        if abs(u) <= 0.35:
            v = max(v, 0.6)
        top.append((cx + u * width, bottom + v * height))
    low = []
    for k, u in enumerate(np.sort(rng.uniform(-0.4, 0.4, n_bot))[::-1]):
        low.append((cx + u * width, bottom + height * (rng.uniform(0.0, 0.04) if k % 2 == 0 else rng.uniform(0.07, 0.13))))
    return left, top, right, low


def _canopy_outline(rng, cx, bottom, width, height):
    left, top, right, low = _canopy_parts(rng, cx, bottom, width, height)
    return [left] + top + [right] + low


def _canopy(cv, rng, cx, bottom, width, height, colors, vines=False):
    """Canopée low-poly (§5.2, images 06 et 09) : dessous en deux tons (bande sombre tout en bas, bande
    moyenne sous le corps), corps, 2 ou 3 facettes claires, 1 ou 2 petits triangles sombres, lianes."""
    base, lit, under, shade = colors
    left, top, right, low = _canopy_parts(rng, cx, bottom, width, height)
    outline = [left] + top + [right] + low
    lower = [left] + low[::-1] + [right]                              # bord inférieur du corps, de gauche à droite

    def band(edge, lo, hi):
        """Bord décalé vers le bas d'une épaisseur tirée entre lo et hi (× h), amincie vers les pointes."""
        out = []
        for k, (x, y) in enumerate(edge):
            taper = 0.35 if k in (0, len(edge) - 1) else 1.0
            out.append((x + rng.uniform(-0.02, 0.02) * width, y - taper * rng.uniform(lo, hi) * height))
        return out

    mid_edge = band(lower, 0.10, 0.14)
    low_edge = band(mid_edge, 0.08, 0.12)
    if vines:
        for x in rng.uniform(cx - 0.4 * width, cx + 0.4 * width, int(width // 3)):
            y_top = float(np.interp(x, [p[0] for p in low_edge], [p[1] for p in low_edge])) + 0.3
            length = rng.uniform(1.5, 0.45 * height)
            w = rng.uniform(0.18, 0.3)
            cv.poly([(x - w, y_top), (x + w, y_top), (x + w, y_top - length), (x - w, y_top - length)], config.VINE_COLOR)
    cv.poly(low_edge + mid_edge[::-1], shade)       # dessous, ton sombre (tout en bas)
    cv.poly(mid_edge + lower[::-1], under)          # dessous, ton moyen (sous le corps)
    cv.poly(outline, base)
    # facettes claires : pan le long du bord supérieur gauche, pan en haut à droite, petit quadrilatère intérieur
    down = lambda p, d: (p[0] + rng.uniform(-0.01, 0.03) * width, p[1] - d * height)   # noqa: E731
    k_left = max(1, len(top) // 3)
    facets = [[left] + top[:k_left + 1] + [down(top[k_left], 0.26)] + [down(q, 0.22) for q in top[:k_left][::-1]]
              + [(left[0] + 0.08 * width, left[1] - 0.04 * height)]]
    choices = []
    if len(top) >= 3:
        k0 = len(top) - 3
        seg = top[k0:k0 + 2]
        choices.append(seg + [down(q, rng.uniform(0.12, 0.2)) for q in seg[::-1]])
    qx, qy = cx - rng.uniform(0.2, 0.3) * width, bottom + rng.uniform(0.42, 0.55) * height
    qw, qh = rng.uniform(0.07, 0.11) * width, rng.uniform(0.12, 0.18) * height
    choices.append([(qx - qw, qy), (qx + 0.2 * qw, qy + qh), (qx + qw, qy + 0.1 * qh), (qx + 0.3 * qw, qy - 0.7 * qh)])
    keep = rng.permutation(len(choices))[:int(rng.integers(1, len(choices) + 1))]
    facets += [choices[i] for i in sorted(keep)]
    for poly in facets:
        cv.poly(poly, lit)
    # petits triangles sombres, plutôt à droite
    for _ in range(int(rng.integers(1, 3))):
        x = cx + rng.uniform(0.05, 0.32) * width
        y = bottom + rng.uniform(0.38, 0.55) * height
        sz = rng.uniform(0.05, 0.08) * width
        cv.poly([(x - sz, y + 0.1 * sz), (x + 0.4 * sz, y + 0.45 * sz), (x + 0.2 * sz, y - 0.5 * sz)], under)


def _tree_silhouette(cv, rng, x, bottom, height, width, color):
    """Arbre en silhouette (une couleur, images 06 et 09) : tronc fin, branches fines en L, canopée en
    nuage de 2 à 4 blobs arrondis irréguliers, lianes."""
    g = config.GROUND_Y
    tw = rng.uniform(0.4, 0.7)
    crown = g + height - 0.32 * width
    cv.poly([(x - tw / 2, bottom), (x + tw / 2, bottom), (x + tw / 2, crown), (x - tw / 2, crown)], color)
    for side in (-1, 1):
        if rng.random() < 0.6:
            y0 = g + rng.uniform(0.4, 0.65) * height
            reach = rng.uniform(0.22, 0.4) * width
            bw = rng.uniform(0.3, 0.45)
            cv.poly([(x, y0), (x + side * reach, y0 + 0.35 * reach), (x + side * reach, y0 + 0.35 * reach + bw), (x, y0 + bw)],
                    color)
            cv.poly([(x + side * reach - side * bw, y0 + 0.35 * reach), (x + side * reach, y0 + 0.35 * reach),
                     (x + side * reach, crown), (x + side * reach - side * bw, crown)], color)
    blobs = [(x, crown, width, 0.62 * width)]
    for _ in range(int(rng.integers(1, 4))):
        bw = width * rng.uniform(0.45, 0.7)
        blobs.append((x + rng.uniform(-0.35, 0.35) * width, crown + rng.uniform(-0.18, 0.2) * width, bw, 0.6 * bw))
    for bx, by, bw, bh in blobs:
        cv.poly(_round_blob(rng, bx, by, bw, bh), color)
        for vx in rng.uniform(bx - 0.35 * bw, bx + 0.35 * bw, int(rng.integers(1, 4))):
            y_top = by - 0.3 * bh
            length = rng.uniform(0.1, 0.28) * height
            cv.poly([(vx - 0.1, y_top), (vx + 0.1, y_top), (vx + 0.1, y_top - length), (vx - 0.1, y_top - length)], color)


def _leaf(center, angle, length, width, droop, teeth=0):
    """Feuille de palmier : nervure courbée vers le bas ; renvoie (moitié haute, moitié basse)."""
    ts = np.linspace(0.0, 1.0, 9)
    c, s = math.cos(angle), math.sin(angle)
    mid = np.array([(center[0] + length * t * c, center[1] + length * t * s - droop * length * t * t) for t in ts])
    tang = np.gradient(mid, axis=0)
    nrm = np.array([(-ty, tx) for tx, ty in tang])
    nrm /= np.maximum(np.hypot(nrm[:, 0], nrm[:, 1]), 1e-9)[:, None]
    if nrm[4, 1] < 0:                  # « haut » de la feuille : normale vers le ciel
        nrm = -nrm
    w = width * np.sin(np.pi * np.clip(ts, 0, 1)) ** 0.8
    upper = mid + nrm * w[:, None]
    lower_w = w.copy()
    if teeth:
        lower_w[1:-1:2] *= 0.45        # dents de scie sur le bord inférieur
    lower = mid - nrm * lower_w[:, None]
    return [tuple(p) for p in np.vstack([upper, mid[::-1]])], [tuple(p) for p in np.vstack([mid, lower[::-1]])]


def _palm(cv, rng, x, base_y, height, lean_deg, span, colors, detailed=False, coconut=True):
    """Palmier : stipe incliné et courbé, couronne de feuilles (deux tons si `detailed`), noix."""
    dark, lit, lit2, trunk = colors[:4]
    lean = math.radians(lean_deg)
    top = (x + height * math.sin(lean), config.GROUND_Y + base_y + height * math.cos(lean))
    base = (x, config.GROUND_Y + base_y - 3.0)
    ctrl = (0.5 * (base[0] + top[0]) - 0.12 * height * math.sin(lean), 0.5 * (base[1] + top[1]))
    ts = np.linspace(0, 1, 10)
    pts = [((1 - t) ** 2 * base[0] + 2 * (1 - t) * t * ctrl[0] + t * t * top[0],
            (1 - t) ** 2 * base[1] + 2 * (1 - t) * t * ctrl[1] + t * t * top[1]) for t in ts]
    w0, w1 = 0.065 * height, 0.045 * height
    left, right = [], []
    for k, (px, py) in enumerate(pts):
        a = pts[min(k + 1, len(pts) - 1)]
        b = pts[max(k - 1, 0)]
        d = np.array([a[0] - b[0], a[1] - b[1]])
        d /= max(np.hypot(*d), 1e-9)
        w = w0 + (w1 - w0) * ts[k]
        left.append((px - d[1] * w, py + d[0] * w))
        right.append((px + d[1] * w, py - d[0] * w))
    cv.poly(left + right[::-1], trunk)
    leaf_len = 0.5 * span
    angles = [-15, 18, 52, 128, 162, 195] + ([80] if rng.random() < 0.5 else [])
    for ang in angles:
        a = math.radians(ang + rng.uniform(-8, 8))
        upper, lower = _leaf(top, a, leaf_len * rng.uniform(0.8, 1.05), 0.11 * leaf_len, rng.uniform(0.25, 0.45),
                             teeth=detailed)
        if detailed:
            cv.poly(lower, dark)
            cv.poly(upper, lit if math.cos(a) < 0.2 else lit2)   # lumière de la gauche : feuilles de gauche plus claires
        else:
            cv.poly(lower + upper, dark)
    if coconut and detailed:
        r = 0.055 * height
        cx, cy = top
        cv.poly([(cx - 1.6 * r, cy + 0.3 * r), (cx - 0.9 * r, cy + 1.0 * r), (cx + 0.9 * r, cy + 1.0 * r),
                 (cx + 1.6 * r, cy + 0.3 * r), (cx, cy)], config.COCONUT_COLORS[0])
        cv.poly([(cx - 1.6 * r, cy + 0.3 * r), (cx, cy), (cx + 1.6 * r, cy + 0.3 * r), (cx + 1.3 * r, cy - 0.7 * r),
                 (cx + 0.2 * r, cy - 1.3 * r), (cx - 1.2 * r, cy - 0.8 * r)], config.COCONUT_COLORS[1])


def _fern(cv, rng, x, base_y, height, width, colors):
    """Fougère / agave : éventail de longues feuilles pointues, moitié gauche éclairée."""
    dark, mid, lit = colors
    g = config.GROUND_Y + base_y
    n = int(rng.integers(7, 10))
    angles = np.sort(rng.uniform(25, 155, n))
    for ang in sorted(angles, key=lambda a: abs(a - 90)):          # feuilles couchées d'abord
        a = math.radians(ang)
        length = height * (0.55 + 0.45 * math.sin(a)) * rng.uniform(0.85, 1.1)
        tip = (x + 0.5 * width * math.cos(a) * length / height, g + length * math.sin(a))
        w = 0.07 * length + 0.2
        nx, ny = -math.sin(a) * w, math.cos(a) * w
        mid_pt = (x + 0.45 * (tip[0] - x), g + 0.45 * (tip[1] - g))
        cv.poly([(x, g), (mid_pt[0] + nx, mid_pt[1] + ny), tip, mid_pt], lit if ang > 90 else mid)
        cv.poly([(x, g), mid_pt, tip, (mid_pt[0] - nx, mid_pt[1] - ny)], dark)
    b = 0.12 * width
    cv.poly([(x - b, g - 0.2), (x + b, g - 0.2), (x + 0.5 * b, g + 0.5 * b), (x - 0.5 * b, g + 0.5 * b)], dark)


def _side_tree(cv, rng, bottom, top):
    """Arbre latéral (images 03 à 09, à gauche) : tronc brun en deux tons sur toute la hauteur,
    branches en L et canopées low-poly avec lianes, espacées de SIDE_TREE[2] m."""
    x, width, step = config.SIDE_TREE
    lit, shade = config.SIDE_TREE_COLORS
    y = config.GROUND_Y + 11.5
    k = 0
    while y < top:
        side = 1 if k % 3 != 2 else -1
        (w_lo, w_hi), (h_lo, h_hi) = config.SIDE_CANOPY_SIZE
        cw = rng.uniform(w_lo, w_hi)
        cx = x + side * (0.42 * cw + rng.uniform(0.0, 2.0))
        bw = 0.7
        # branche : horizontale depuis le tronc, puis montée jusqu'à la canopée
        reach = cx - x - side * 0.25 * cw
        cv.poly([(x, y - 2.8), (x + reach, y - 2.8 + 0.5 * abs(reach) * 0.3), (x + reach, y - 2.8 + 0.5 * abs(reach) * 0.3 + bw),
                 (x, y - 2.8 + bw)], shade)
        cv.poly([(x + reach - side * bw, y - 2.8), (x + reach, y - 2.8), (x + reach, y + 1.0), (x + reach - side * bw, y + 1.0)],
                shade)
        _canopy(cv, rng, cx, y, cw, rng.uniform(h_lo, h_hi), config.SIDE_CANOPY_COLORS + (config.SIDE_CANOPY_COLORS[2],),
                vines=True)
        y += step * rng.uniform(0.85, 1.15)
        k += 1
    half = width / 2
    cv.poly([(x - half, bottom), (x, bottom), (x, top), (x - half, top)], lit)
    cv.poly([(x, bottom), (x + half, bottom), (x + half, top), (x, top)], shade)
