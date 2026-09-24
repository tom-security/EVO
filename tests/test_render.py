"""Phase 4a : replay (moteur scalaire), décor pré-rendu et cache, lézard dessiné depuis les points."""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import numpy as np
import pygame
import pytest

import config
from evo import creature as cr
from evo import evolution as ev
from evo import render_lizard as rl
from evo import replay as rp
from evo import scene as sc
from evo import skeleton as sk


@pytest.fixture(scope="module")
def small_run(tmp_path_factory):
    run = str(tmp_path_factory.mktemp("run") / "0")
    ev.train(0, generations=1, pop_size=24, run_dir=run, audit_every=0, log=lambda *_: None)
    return run


@pytest.fixture
def tmp_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SCENE_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


def _near(arr, hex_code, tol=6):
    c = np.array(pygame.Color(hex_code)[:3])
    return np.all(np.abs(arr.astype(int) - c) <= tol, axis=-1)


# Replay ------------------------------------------------------------------------------
def test_replay_ranks_and_matches_stored_height(small_run):
    _, res, _, _ = ev.load_generation(small_run, 1)
    best = rp.Replay(small_run, gen=1, rank=1, log=None)
    worst = rp.Replay(small_run, gen=1, rank=24, log=None)
    assert best.index == int(np.argmax(res["score"]))
    assert worst.index == int(ev.ranking(res["score"])[-1])
    for r in (best, worst):
        assert r.ok and r.height_replay == pytest.approx(r.stored["height"], abs=1e-9)
        assert r.n_frames == int(round(config.SIM_DURATION / config.DT)) + 1
        assert r.height[-1] == r.height_replay and r.height[0] == 0.0


# Décor ---------------------------------------------------------------------------------
def test_scene_covers_decor_and_frames_are_filled(tmp_cache):
    scene = sc.Scene()
    assert config.DECOR_TOP_HUD >= 45 and scene.markers[:4] == [10, 20, 30, 40]
    plane, parallax, offset = scene.layers["plan"]
    assert parallax == 1.0 and offset == pytest.approx(scene.max_shift)
    surf = pygame.Surface(config.WINDOW_SIZE)
    w, h = config.WINDOW_SIZE
    for shift in (0.0, scene.max_shift / 2, scene.max_shift):
        surf.fill((255, 0, 255))
        scene.draw_back(surf, shift)
        arr = pygame.surfarray.array3d(surf)
        assert not _near(arr, "#FF00FF", 0).any()          # rien d'oublié : pas de trou dans l'image
        ground_row = int(config.SCENE_GROUND_PX + shift)
        column = arr[w // 2, 5:min(h - 5, ground_row - 5)]     # tronc brun jusqu'au sol (ou au bas de l'écran)
        white = np.all(column > 240, axis=1)                 # repères de hauteur
        assert len(column) > 400 and np.all((column[:, 0] > column[:, 1]) | white)
    # cadrage de départ : herbe à la ligne du sol, terre en bas de l'écran
    surf.fill((255, 0, 255))
    scene.draw_back(surf, 0.0)
    arr = pygame.surfarray.array3d(surf)
    assert _near(arr[:, config.SCENE_GROUND_PX + 4], config.GRASS_COLORS[0]).mean() > 0.5
    assert np.all(arr[:, h - 2, 0] > arr[:, h - 2, 1])


def test_markers_appear_only_once_reached(tmp_cache):
    scene = sc.Scene()
    surf = pygame.Surface(config.WINDOW_SIZE)
    row = int(round(scene.framing.y_px(config.GROUND_Y + config.START_HEIGHT + 10.0)))
    x = scene.framing.size[0] // 2
    for reached, visible in ((9.9, False), (10.0, True), (15.0, True)):
        scene.draw_back(surf, 0.0)
        scene.draw_markers(surf, 0.0, reached)
        assert (tuple(surf.get_at((x, row)))[:3] == tuple(pygame.Color(config.MARKER_COLOR))[:3]) == visible


def test_visual_tail_is_longer_than_physics_and_stays_above_ground():
    c = cr.Creature(cr.diagonal_gait_genome())
    shape = rl.LizardShape(c.skel)
    pos = c.world.pos.copy()
    tail = np.vstack([pos[sk.PELVIS], pos[sk.TAIL_START:]])
    visual = shape._visual_tail(tail)
    length = np.hypot(*np.diff(visual, axis=0).T).sum()
    assert length == pytest.approx(config.TAIL_VISUAL_FACTOR * shape.spine, rel=1e-6)
    pos[:, 1] -= pos[:, 1].min() - config.GROUND_Y      # bout de la queue physique posé sur le sol
    polys = shape.polygons(pos)
    assert min(p[:, 1].min() for _, p in polys[:2]) >= config.GROUND_Y - 1e-9


def test_camera_is_fixed_at_start_then_follows_with_lerp():
    cam = sc.Camera(sc.Framing())
    start = config.GROUND_Y + config.START_HEIGHT
    cam.update(start - 5.0, snap=True)
    assert cam.shift == 0.0                                    # sous le départ : cadrage fixe
    cam.update(start + 10.0)
    assert 0.0 < cam.shift < 10.0 * config.SCENE_SCALE        # lerp : rattrape progressivement
    for _ in range(300):
        cam.update(start + 10.0)
    assert cam.shift == pytest.approx(10.0 * config.SCENE_SCALE)
    assert cam.framing.y_px(start + 10.0, cam.shift) == pytest.approx(config.SCENE_GROUND_PX - config.START_HEIGHT * config.SCENE_SCALE)
    cam.update(start + 500.0, snap=True)
    assert cam.shift == cam.max_shift                          # bornée par le haut du décor


def test_scene_cache_is_reused_and_invalidated(tmp_cache, monkeypatch):
    a = sc.Scene()
    b = sc.Scene()
    assert a.built and not b.built and a.key == b.key
    pa = pygame.surfarray.array3d(a.layers["plan"][0])
    pb = pygame.surfarray.array3d(b.layers["plan"][0])
    np.testing.assert_array_equal(pa, pb)
    assert sc.Scene(use_cache=False).built                     # --no-cache
    monkeypatch.setattr(config, "SCENE_SEED", config.SCENE_SEED + 1)
    c = sc.Scene()
    assert c.built and c.key != a.key                          # paramètre du décor changé
    monkeypatch.setattr(config, "SCENE_SEED", config.SCENE_SEED - 1)
    monkeypatch.setattr(sc, "_source_digest", lambda: "code modifié")
    assert sc.cache_key(sc.Framing(), config.SCENE_LAYERS) != a.key   # code de scene.py changé
    d = sc.Scene()
    assert d.built and os.path.isdir(d.cache_path)
    assert not os.path.exists(a.cache_path)                    # les décors de l'ancien code sont supprimés


# Lézard ------------------------------------------------------------------------------
def test_lizard_two_tones_fingers_eyes_and_follows_points():
    c = cr.Creature(cr.diagonal_gait_genome())
    shape = rl.LizardShape(c.skel)
    framing = sc.Framing()
    surf = pygame.Surface(config.WINDOW_SIZE)

    def render(pos):
        surf.fill((0, 0, 255))
        shape.draw(surf, pos, framing.origin(), framing.scale)
        return pygame.surfarray.array3d(surf)

    a = render(c.world.pos)
    assert _near(a, config.LIZARD_LIGHT, 2).sum() > 100 and _near(a, config.LIZARD_DARK, 2).sum() > 100
    assert _near(a, config.LIZARD_FINGER, 30).sum() > 5 and _near(a, config.LIZARD_EYE_COLOR, 30).sum() > 2
    # moitié claire à gauche de la colonne (côté des points L_*) quand le lézard a la tête en haut
    spine_x = framing.x_px(c.world.pos[sk.NECK][0])
    assert np.nonzero(_near(a, config.LIZARD_LIGHT, 2))[0].max() <= spine_x + 1
    b = render(c.world.pos + np.array([2.0, 1.0]))
    mask_a, mask_b = np.any(a != (0, 0, 255), axis=-1), np.any(b != (0, 0, 255), axis=-1)
    (xa, ya), (xb, yb) = (np.argwhere(m).min(axis=0) for m in (mask_a, mask_b))
    assert xb - xa == pytest.approx(2.0 * framing.scale, abs=1.5)
    assert ya - yb == pytest.approx(1.0 * framing.scale, abs=1.5)
