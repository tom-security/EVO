"""Phase 5a : HUD (§6) — polices, textes en cache, badges, étiquette de hauteur, carton."""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import numpy as np
import pygame
import pytest

import config
from evo import evolution as ev
from evo import fonts
from evo import hud as H
from evo import replay as rp
from evo import scene as sc


@pytest.fixture(scope="module")
def small_run(tmp_path_factory):
    run = str(tmp_path_factory.mktemp("run") / "0")
    ev.train(0, generations=1, pop_size=24, run_dir=run, audit_every=0, log=lambda *_: None)
    return run


@pytest.fixture
def tmp_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SCENE_CACHE_DIR", str(tmp_path / "cache"))


def test_fonts_are_bundled_with_licence_and_fall_back(monkeypatch, tmp_path):
    for name in config.FONT_FILES:
        assert fonts.available(name)
    root = os.path.dirname(fonts.path("questrial"))
    assert os.path.exists(os.path.join(root, "Questrial-OFL.txt")) and os.path.exists(os.path.join(root, "NunitoSans-OFL.txt"))
    assert fonts.load("questrial", 22).size("1.3 s")[0] > 0
    monkeypatch.setitem(config.FONT_FILES, "questrial", str(tmp_path / "absente.ttf"))
    fonts.load.cache_clear()
    try:
        assert not fonts.available("questrial") and fonts.load("questrial", 22).size("1.3 s")[0] > 0   # repli
    finally:
        fonts.load.cache_clear()


def test_formats_and_title_card_timing():
    assert H.format_height(23.14) == "23.1 m" and H.format_height(-4.9) == "-4.9 m" and H.format_height(-0.02) == "0.0 m"
    hold, fade = config.TITLE_CARD_HOLD_S, config.TITLE_CARD_FADE_S
    assert H.card_alpha(0.0) == 1.0 and H.card_alpha(hold) == 1.0
    assert H.card_alpha(hold + fade / 2) == pytest.approx(0.5) and H.card_alpha(hold + fade + 0.1) == 0.0


def test_hud_layout_cache_and_label_follows_the_lizard():
    pygame.display.init()
    framing = sc.Framing()
    hud = H.Hud(framing, 200, 0.6, 13.5, rank=1)
    surf = pygame.Surface(config.WINDOW_SIZE)
    surf.fill((128, 128, 128))
    hud.draw(surf, 6.4, 23.1, 32.5, 358.0, card=False)
    a = pygame.surfarray.array3d(surf).transpose(1, 0, 2).astype(int)
    b = config.HUD_BADGES
    for k in range(3):   # trois badges sombres empilés
        y = b["y"] + k * b["pitch"] + b["h"] // 2
        assert a[y, b["x"] + b["w"] - 4].mean() < 90 and a[y, b["x"] + b["w"] + 3].mean() > 120
    rect = hud.label_rect(358.0)
    assert rect.centery == pytest.approx(358.0 + config.HUD_LABEL["dy"], abs=1)
    tip = framing.x_px(config.TRUNK_X - config.TRUNK_WIDTH / 2) + config.HUD_LABEL["tip_on_trunk"]
    assert rect.right + config.HUD_LABEL["tip"] == pytest.approx(tip, abs=1)
    assert hud.label_rect(500.0).centery - rect.centery == pytest.approx(142, abs=1)   # suit le lézard
    # cache : mêmes valeurs → aucun nouveau rendu ; une valeur qui change → un seul rendu
    n = hud.renders
    hud.draw(surf, 6.4, 23.1, 32.5, 358.0, card=False)
    assert hud.renders == n
    hud.draw(surf, 6.4, 23.2, 32.5, 358.0, card=False)
    assert hud.renders == n + 1
    assert ("text", "Classement: #1") in hud._texts and ("text", "Temps: 6.4 s") in hud._texts


def test_replay_energy_matches_run_and_creature_mode(small_run):
    _, res, _, _ = ev.load_generation(small_run, 1)
    r = rp.Replay(small_run, gen=1, index=0, log=None)
    assert r.by_index and r.creature_number == 1 and "créature 1" in r.label()
    assert r.energy[0] == 0.0 and r.energy[-1] == pytest.approx(res["energy"][0], rel=1e-9, abs=1e-9)
    assert np.all(np.diff(r.energy) >= 0)                  # énergie cumulée


def test_label_stays_visible_over_a_front_canopy(small_run, tmp_cache):
    pygame.display.init()
    r = rp.Replay(small_run, gen=1, rank=1, log=None)
    view = rp.JungleView(r)
    # caméra à la hauteur de la canopée de la branche gauche (elle couvre la zone de l'étiquette)
    hud_m, side, dx, dy, post, th = config.BRANCHES[1]
    y_mid = config.GROUND_Y + config.START_HEIGHT + hud_m + dy + config.FG_CANOPY_LIFT + 0.45 * config.FG_CANOPIES[1][2]
    view.camera.update(y_mid, snap=True)
    surf = pygame.Surface(config.WINDOW_SIZE)
    view.scene.draw_back(surf, view.camera.shift)
    view.scene.draw_front(surf, view.camera.shift)
    ref_px = view.framing.y_px(y_mid, view.camera.shift)
    rect = view.hud.label_rect(ref_px)
    before = surf.get_at((rect.left + 4, rect.centery))
    view.hud.draw(surf, 5.0, 12.3, 4.2, ref_px, card=False)
    after = surf.get_at((rect.left + 4, rect.centery))
    assert np.mean(before[:3]) > 90 and np.mean(after[:3]) < 90   # sous la canopée, l'étiquette sombre est dessinée


def test_markers_only_without_hud(small_run, tmp_cache):
    pygame.display.init()
    r = rp.Replay(small_run, gen=1, rank=1, log=None)
    view = rp.JungleView(r)
    view.crossings = {10.0: 0}                    # repère de 10 m franchi à la frame 0 (pleine opacité)
    view.reset_camera()
    surf = pygame.Surface(config.WINDOW_SIZE)
    row = int(round(view.framing.y_px(config.GROUND_Y + config.START_HEIGHT + 10.0, view.camera.shift)))
    x = int(view.framing.x_px(config.TRUNK_X + 0.35 * config.TRUNK_WIDTH))   # sur le tronc, loin de l'étiquette
    white = tuple(pygame.Color(config.MARKER_COLOR))[:3]
    view.draw(surf, 0, hud=False)
    assert tuple(surf.get_at((x, row)))[:3] == white                          # sans HUD : le repère est là
    view.draw(surf, 0, hud=True)
    assert tuple(surf.get_at((x, row)))[:3] != white                          # avec HUD : pas de repère
