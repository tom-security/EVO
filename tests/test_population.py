"""Phase 5b : vue population (§7.1) et histogramme au style de la vidéo (§7.2)."""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import numpy as np
import pygame
import pytest

import config
from evo import charts
from evo import evolution as ev
from evo import population as P


@pytest.fixture(scope="module")
def small_run(tmp_path_factory):
    run = str(tmp_path_factory.mktemp("run") / "0")
    ev.train(0, generations=1, pop_size=24, run_dir=run, audit_every=0, log=lambda *_: None)
    return run


def test_grid_holds_1000_distinct_cells():
    n = 1000
    start = P.slot_centers(P.compute_slots(n))
    assert len(np.unique(start, axis=0)) == n                      # 1000 miniatures, une par case
    assert sorted(P.compute_slots(n)) == list(range(n))            # la grille 50 × 20 est pleine
    ox, oy = config.POP_ORIGIN
    assert start[:, 0].min() == ox and start[:, 1].min() == oy     # zone de l'image 24 : x 67.5–1215.6, y 64.5–647.4
    assert start[:, 0].max() == pytest.approx(1215.6, abs=0.1) and start[:, 1].max() == pytest.approx(647.4, abs=0.1)
    # place de calcul : la grille se remplit colonne par colonne
    assert np.allclose(start[1] - start[0], (0, config.POP_PITCH[1]))
    assert np.allclose(start[config.POPULATION_GRID[1]] - start[0], (config.POP_PITCH[0], 0))
    with pytest.raises(ValueError):
        P.compute_slots(1001)


def test_sort_puts_the_best_first_in_reading_order():
    rng = np.random.default_rng(3)
    scores = rng.normal(size=1000)
    scores[17] = np.nan                                            # un score NaN compte comme le pire
    slots = P.sorted_slots(scores)
    assert sorted(slots) == list(range(1000))
    assert slots[int(np.nanargmax(scores))] == 0 and slots[17] == 999
    c = P.slot_centers([0, 1, config.POPULATION_GRID[0]])
    everything = P.slot_centers(np.arange(1000))
    assert tuple(c[0]) == (everything[:, 0].min(), everything[:, 1].min())   # en haut à gauche
    assert c[1][1] == c[0][1] and c[1][0] > c[0][0]                          # rang 2 : à droite
    assert c[2][0] == c[0][0] and c[2][1] > c[0][1]                          # rang 51 : ligne suivante


def test_sort_animation_endpoints():
    assert P.sort_progress(0.0) == 0.0 and P.sort_progress(config.POP_SORT_DELAY_S) == 0.0
    assert P.sort_progress(config.POP_SORT_DELAY_S + config.POP_SORT_S / 2) == pytest.approx(0.5)
    assert P.sort_progress(P.sort_end()) == 1.0 and P.sort_progress(P.sort_end() + 5) == 1.0


def test_batched_final_poses_and_miniatures(small_run):
    pygame.display.init()
    g = P.Generation(small_run, gen=1, log=None)
    _, res, _, _ = ev.load_generation(small_run, 1)
    assert g.ok and np.array_equal(g.height, res["height"])        # hauteur batchée = hauteur stockée
    view = P.PopulationView(g)
    assert len(view.minis) == len(g) == 24
    assert np.array_equal(view.positions(0.0), P.slot_centers(P.compute_slots(24)))
    assert np.allclose(view.positions(P.sort_end() + 1), P.slot_centers(g.slots), atol=1e-9)
    body = tuple(pygame.Color(config.POP_MINI_COLOR))[:3]
    for surf, _ in view.minis:
        a = pygame.surfarray.pixels_alpha(surf)
        assert (a > 0).any()
        del a
    # dans l'image triée, la meilleure est dessinée dans la première case
    screen = pygame.Surface(config.WINDOW_SIZE)
    view.draw(screen, P.sort_end())
    best = int(np.argmax(res["score"]))
    surf, (dx, dy) = view.minis[best]
    ox, oy = np.rint(P.slot_centers([0])[0]).astype(int)
    rect = pygame.Rect(ox + dx, oy + dy, *surf.get_size())
    arr = pygame.surfarray.array3d(screen.subsurface(rect)).reshape(-1, 3)
    assert (np.abs(arr - body).max(axis=1) <= 2).any()             # vert de la silhouette


def test_upright_pose_keeps_the_shape_head_up():
    from evo import creature as cr, skeleton as sk
    from evo.creature import diagonal_gait_genome

    c = cr.Creature(diagonal_gait_genome())
    P0 = c.world.pos.copy()
    ref0 = 0.5 * (P0[sk.NECK] + P0[sk.PELVIS])
    a = np.radians(100.0)                                           # couchée au sol, sur le côté
    rot = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])
    lying = (P0 - ref0) @ rot.T + np.array([config.TRUNK_X, config.GROUND_Y + 0.3])
    up = P.upright_pose(lying)
    fwd = up[sk.NECK] - up[sk.PELVIS]
    assert abs(fwd[0]) < 1e-9 and fwd[1] > 0                        # colonne verticale, tête en haut
    dist = lambda X: np.hypot(*(X[:, None, :] - X[None, :, :]).transpose(2, 0, 1))   # noqa: E731
    assert np.allclose(dist(up), dist(lying))                       # rotation seule
    cross = lambda X: np.cross(X[sk.NECK] - X[sk.PELVIS], X[sk.L_SHOULDER] - X[sk.PELVIS])   # noqa: E731
    assert np.sign(cross(up)) == np.sign(cross(lying))              # côtés gauche / droit conservés
    assert up[:, 1].min() > config.GROUND_Y + 10                   # loin du sol : la queue n'est pas couchée
    assert np.allclose(up, P.upright_pose(up))                     # déjà droite : inchangée


def test_histogram_sums_to_n_and_clips_to_the_x_axis():
    rng = np.random.default_rng(0)
    h = rng.uniform(-25.0, 55.0, 1000)
    counts = ev.histogram(h)
    lo, hi = config.HIST_RANGE
    assert (lo, hi) == (-10, 40) and len(counts) == 50 and counts.sum() == 1000
    assert counts[0] == np.sum(h < lo + 1)                          # < −10 dans la première barre
    assert counts[-1] == np.sum(h >= hi - 1)                        # > 40 dans la dernière


def test_video_histogram_axis_bounds():
    pygame.display.init()
    counts = np.zeros(50)
    counts[0], counts[-1], counts[25] = 30, 120, 650                # 650 > 500 : barre tronquée
    surf = charts.histogram_chart(dict(zip(ev.HIST_COLUMNS, counts)), style="video")
    a = pygame.surfarray.array3d(surf).transpose(1, 0, 2).astype(int)
    bar = np.array(pygame.Color(charts.BAR)[:3])
    is_bar = lambda x, y: np.abs(a[y, x] - bar).max() <= 2          # noqa: E731
    assert charts.hist_video_x(-10) == 153 and charts.hist_video_x(40) == 1127
    assert is_bar(154, 590) and not is_bar(152, 590)                # −10 m sur l'axe gauche (x 153)
    assert is_bar(1126, 590) and not is_bar(1127, 590)              # 40 m au bord droit (x 1127)
    assert is_bar(round(charts.hist_video_x(15.5)), 121)            # tronquée au sommet de l'axe (500)
    assert charts.clipped_bars(counts) == [(15, 650)]
    assert charts.hist_video_y(0) == 600 and charts.hist_video_y(500) == 120
