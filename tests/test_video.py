"""Phase 6 : export vidéo (images pygame → ffmpeg), même avancement que la fenêtre interactive."""
import os
import re
import subprocess

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
import pytest

import config
from evo import video


def test_playback_matches_the_interactive_loop():
    hold = int(round(config.VIDEO_HOLD_S * config.FPS))
    frames = video.playback_frames(601)
    assert frames[:601] == list(range(601)) and frames[601:] == [600] * hold      # vitesse 1 + tenue de fin
    fast = video.playback_frames(601, speed=4, hold_s=0)
    assert fast[:4] == [0, 4, 8, 12] and fast[-1] == 600 and len(fast) == 151      # ×4 : une image sur 4
    slow = video.playback_frames(601, slow=True, hold_s=0)
    assert slow[:9] == [0, 0, 0, 0, 1, 1, 1, 1, 2] and len(slow) == 2401          # ×0.25 : chaque image 4 fois


def _frames(n):
    pygame.display.init()
    surf = pygame.Surface((64, 48))
    for k in range(n):
        surf.fill((20 * k % 255, 100, 200))
        yield surf


def test_png_fallback_without_ffmpeg(tmp_path):
    logs = []
    path = str(tmp_path / "sortie.mp4")
    with video.VideoWriter(path, (64, 48), log=logs.append, ffmpeg=False) as out:
        for surf in _frames(5):
            out.write(surf)
    images = sorted(os.listdir(tmp_path / "sortie_images"))
    assert images == [f"{k:06d}.png" for k in range(5)] and not os.path.exists(path)
    assert "ffmpeg introuvable" in logs[0] and "%06d.png" in logs[0] and "libx264" in logs[0]   # commande pour assembler


@pytest.mark.skipif(video.find_ffmpeg() is None, reason="ffmpeg absent (PATH ou imageio-ffmpeg)")
def test_mp4_has_every_frame(tmp_path):
    path = str(tmp_path / "sortie.mp4")
    with video.VideoWriter(path, (64, 48), log=lambda *_: None) as out:
        for surf in _frames(12):
            out.write(surf)
    assert out.frames == 12 and os.path.getsize(path) > 0
    decoded = subprocess.run([video.find_ffmpeg(), "-i", path, "-f", "null", "-"], capture_output=True, text=True)
    counts = re.findall(r"frame=\s*(\d+)", decoded.stderr)
    assert counts and int(counts[-1]) == 12                        # décodé : les 12 images


@pytest.mark.skipif(video.find_ffmpeg() is None, reason="ffmpeg absent (PATH ou imageio-ffmpeg)")
def test_ffmpeg_failure_is_reported(tmp_path):
    logs = []
    bad = str(tmp_path / "pas_de_dossier" / "x" / "sortie.mkv_invalide")   # extension inconnue : ffmpeg échoue
    with pytest.raises(RuntimeError, match="ffmpeg"):
        with video.VideoWriter(bad, (64, 48), log=logs.append) as out:
            for surf in _frames(3):
                out.write(surf)
    assert logs and "ffmpeg" in logs[0]                             # message de ffmpeg recopié dans le journal
