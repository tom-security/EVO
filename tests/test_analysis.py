"""Phase 5c : mode analyse biomécanique (§7.4, §5.5) et comparaison de générations (§7.5)."""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import numpy as np
import pygame
import pytest

import config
from evo import analysis as an
from evo import compare as cp
from evo import creature as cr
from evo import evolution as ev
from evo import physics
from evo import replay as rp
from evo import skeleton as sk
from evo.render_lizard import LizardShape


@pytest.fixture(scope="module")
def small_run(tmp_path_factory):
    run = str(tmp_path_factory.mktemp("run") / "0")
    ev.train(0, generations=1, pop_size=24, run_dir=run, audit_every=0, log=lambda *_: None)
    return run


@pytest.fixture
def tmp_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SCENE_CACHE_DIR", str(tmp_path / "cache"))


def _anatomy(strength=1.0):
    g = cr.diagonal_gait_genome(strength=strength)
    c = cr.Creature(g)
    return an.Anatomy(LizardShape(c.skel), g), c


def test_sixteen_muscles_sized_by_their_max_force():
    anat, c = _anatomy(0.8)
    m = anat.muscles(c.world.pos)
    assert len(m) == 16 and all(v[0] is not None for v in m.values())
    anat.frac[0, an.ELBOW, an.PLUS] = 0.0                            # force nulle : pas de fuseau
    wide, _ = _anatomy(1.6)
    m0, m2 = anat.muscles(c.world.pos), wide.muscles(c.world.pos)
    assert m0[(0, an.ELBOW, an.PLUS)][0] is None
    # épaisseur ∝ force max : un fuseau à 1.6 est deux fois plus large qu'à 0.8
    def half_width(contour, a, b):
        d = (b - a) / np.hypot(*(b - a))
        n = np.array([-d[1], d[0]])
        return np.ptp((contour - a) @ n)
    a, b = c.world.pos[sk.L_HIP], c.world.pos[sk.L_KNEE]
    w1 = half_width(m[(0, an.KNEE, an.PLUS)][0], a, b)
    w2 = half_width(m2[(0, an.KNEE, an.PLUS)][0], a, b)
    assert w2 == pytest.approx(2 * w1, rel=1e-6)


def test_plus_muscle_sits_where_it_turns_the_distal_bone():
    """Biceps / ischios du côté vers lequel leur contraction fait tourner l'avant-bras / le tibia."""
    anat, c = _anatomy()
    P = c.world.pos
    m = anat.muscles(P)
    for s in (0, 1):
        for joint, (a, p, b) in ((an.ELBOW, cr.JOINTS[s * 4 + 1]), (an.KNEE, cr.JOINTS[s * 4 + 3])):
            torque = np.zeros(len(cr.JOINTS))
            torque[s * 4 + joint] = cr.JOINT_SIGNS[s * 4 + joint] * 1.0      # contraction du muscle « + »
            f = physics.contraction_forces(P, np.array(cr.JOINTS), torque)[b]
            proximal = P[p] - P[a]
            n = np.array([-proximal[1], proximal[0]])
            plus_side = np.dot(m[(s, joint, an.PLUS)][2] - P[a], n)
            minus_side = np.dot(m[(s, joint, an.MINUS)][2] - P[a], n)
            assert np.sign(plus_side) == np.sign(np.dot(f, n)) == -np.sign(minus_side)


def test_contraction_colors_and_labels():
    anat, c = _anatomy()
    act = np.zeros(8)
    act[0] = anat.s_plus[0]                                          # deltoïde gauche à fond
    act[5] = -0.5 * anat.s_minus[5]                                  # triceps droit à moitié
    k = anat.contraction(act)
    assert k[0, an.SHOULDER, an.PLUS] == 1.0 and k[1, an.ELBOW, an.MINUS] == pytest.approx(0.5)
    assert k.sum() == pytest.approx(1.5)
    assert an._mix(config.ANALYSIS_MUSCLE_REST, config.ANALYSIS_MUSCLE_ACTIVE, 0.0) == tuple(pygame.Color(config.ANALYSIS_MUSCLE_REST))[:3]
    assert an._mix(config.ANALYSIS_MUSCLE_REST, config.ANALYSIS_MUSCLE_ACTIVE, 1.0) == tuple(pygame.Color(config.ANALYSIS_MUSCLE_ACTIVE))[:3]
    assert an.percent(0.76) == "76%" and an.percent(0.0) == "0%"
    start, step, fade = config.ANALYSIS_LABEL_TIMES
    n = len(config.ANALYSIS_LABELS)
    assert n == 8                                                    # un libellé par muscle
    assert all(an.label_alpha(start + k * step - 0.01, k) == 0.0 for k in range(n))      # un par un
    assert all(an.label_alpha(start + k * step + fade + 1e-9, k) == 1.0 for k in range(n))
    assert start + (n - 1) * step + fade <= config.SIM_DURATION                        # tous avant la fin


def test_analysis_view_draws_overlay_and_labels(small_run, tmp_cache):
    pygame.display.init()
    screen = pygame.display.set_mode(config.WINDOW_SIZE)
    r = rp.Replay(small_run, gen=1, rank=1, log=None)
    view = an.AnalysisView(r)
    assert view.framing.scale == config.ANALYSIS_SCALE and "premier_plan" not in view.scene.layers
    view.reset_camera()
    view.draw(screen, 0)
    torso = view.framing.y_px(r.ref_y[0], view.camera.shift)
    assert torso == pytest.approx(config.ANALYSIS_TORSO_PX, abs=1)  # torse au cadrage de l'image 11
    a = pygame.surfarray.array3d(screen).transpose(1, 0, 2).astype(int)
    cream = np.array(pygame.Color(config.ANALYSIS_BONE)[:3])
    assert (np.abs(a - cream).max(axis=2) <= 3).sum() > 50           # os et articulations
    reds = (a[:, :, 0] > 240) & (a[:, :, 1] < 110) & (a[:, :, 2] < 130)
    assert reds.sum() > 200                                          # muscles
    frames = []
    view.draw(screen, r.n_frames - 1, timings=frames)                # à 10 s : les 8 libellés sont là
    b = pygame.surfarray.array3d(screen).transpose(1, 0, 2).astype(int)
    cx = int(view.framing.x_px(config.TRUNK_X))
    right = b[:, cx + config.ANALYSIS_LABEL_DX: cx + config.ANALYSIS_LABEL_DX + 60]
    assert (right.min(axis=2) > 245).sum() > 100                     # texte blanc dans la colonne de droite
    assert len(frames) == 1 and len(frames[0]) == 4
    keys = an.key_frames(r, view.anatomy)
    assert set(keys) == {"epaule", "hanche", "genou"} and all(0 <= f < r.n_frames for f, _ in keys.values())


def test_compare_ghosts_same_time_and_camera(small_run, tmp_cache):
    pygame.display.init()
    screen = pygame.display.set_mode(config.WINDOW_SIZE)
    replays = cp.load_champions(small_run, [1, 0], log=None)
    view = cp.CompareView(replays)
    assert [r.gen for r in view.replays] == [0, 1] and view.replay.gen == 1      # libellé : la plus récente
    assert "premier_plan" not in view.scene.layers
    track = view.track
    ys = np.stack([r.ref_y for r in view.replays])
    above = view.framing.y_px(config.GROUND_Y + config.START_HEIGHT) / view.framing.scale
    assert np.all(track >= 0.5 * (ys.max(0) + ys.min(0)) - 1e-12)
    assert np.all(track >= ys.max(0) - (above - config.COMPARE_TOP_MARGIN) - 1e-12)
    view.reset_camera()
    view.draw(screen, 0)
    a = pygame.surfarray.array3d(screen).transpose(1, 0, 2).astype(int)
    assert (a.min(axis=2) > 245).sum() > 100                         # libellé blanc « Génération 1 » souligné


def test_ghost_track_follows_the_highest(small_run):
    class Fake:
        def __init__(self, ys):
            self.ref_y = np.asarray(ys, float)
    from evo.scene import Framing
    f = Framing()
    above = f.y_px(config.GROUND_Y + config.START_HEIGHT) / f.scale
    low, high = Fake([10.3, 10.3]), Fake([10.3, 10.3 + 40.0])
    track = cp.camera_track([low, high], f)
    assert track[0] == pytest.approx(10.3)                           # ensemble : centre
    assert track[1] == pytest.approx(10.3 + 40.0 - (above - config.COMPARE_TOP_MARGIN))   # écart trop grand : le plus haut
