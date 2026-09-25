"""Chantier A : contrôle du décor au-dessus de 23 m (§5.6)."""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import numpy as np
import pygame
import pytest

import config
from evo import decor_check as dc
from evo import scene as sc


@pytest.fixture
def tmp_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SCENE_CACHE_DIR", str(tmp_path / "cache"))


def test_band_similarity_detects_a_copied_motif():
    rng = np.random.default_rng(0)
    scale, rows = 20.2, 101
    motif = rng.integers(0, 255, size=(rows, 64, 3))
    copied = np.concatenate([motif] * 6)                                 # même tranche recopiée
    random = rng.integers(0, 255, size=(6 * rows, 64, 3))
    alpha = np.full((6 * rows, 64), 255)
    assert dc.band_similarity(copied, alpha, scale, step=1)["max_similarity"] == pytest.approx(1.0)
    assert dc.band_similarity(random, alpha, scale, step=1)["max_similarity"] < 0.1
    empty = dc.band_similarity(random, np.zeros_like(alpha), scale, step=1)
    assert empty["bands"] == 0                                           # tranches vides ignorées


def test_marker_row_and_canopy_extent():
    img = np.zeros((720, 1280, 3), dtype=int)
    img[:, 520:770] = (132, 76, 44)                                      # tronc
    img[300, 520:770] = (252, 252, 252)                                  # repère
    img[250:450, 700:1100] = pygame.Color(config.CANOPY_COLORS[0])[:3]   # canopée
    img[600:650, 900:1000] = pygame.Color(config.CANOPY_COLORS[0])[:3]   # autre élément de même couleur, plus bas
    assert dc.marker_row(img) == 300
    ext = dc.canopy_extent(img, 300, 20.0)
    assert ext["top_m"] == pytest.approx(50 / 20.0) and ext["bottom_m"] == pytest.approx(-149 / 20.0)


def test_markers_and_trunk_up_to_the_top(tmp_cache):
    pygame.display.init()
    pygame.display.set_mode(config.WINDOW_SIZE)
    scene = sc.Scene(sc.Framing(), layers=sc.BACK_LAYERS)
    f = scene.framing
    base = config.GROUND_Y + config.START_HEIGHT
    screen = pygame.Surface(config.WINDOW_SIZE)
    x = int(f.x_px(config.TRUNK_X + 0.3 * config.TRUNK_WIDTH))
    for hud in (30, 45):
        shift = min(hud * f.scale, scene.max_shift)
        scene.draw_back(screen, shift)
        scene.draw_markers(screen, shift, {m: 1.0 for m in scene.markers})
        col = pygame.surfarray.array3d(screen)[x].astype(int)
        for m in scene.markers:
            y = f.y_px(base + m, shift)
            if 5 <= y <= 715:
                rows = np.nonzero(col.min(axis=1) > 245)[0]
                assert np.abs(rows - y).min() <= 1                        # repère à sa hauteur
    plan, _, off = scene.layers["plan"]
    tr = dc.trunk_continuity(pygame.surfarray.array3d(plan).transpose(1, 0, 2).astype(int),
                             pygame.surfarray.array_alpha(plan).T, f, off)
    assert tr["bands"] >= 30 and tr["palette_share_min"] > 0.95 and tr["max_jump"] < 20   # tronc continu jusqu'en haut
