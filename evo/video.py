"""Export vidéo MP4 (§10, phase 6) : les images pygame d'une vue, assemblées par ffmpeg.

- find_ffmpeg : ffmpeg du PATH, sinon celui du paquet imageio-ffmpeg (s'il est installé), sinon None.
- VideoWriter : chaque image (RGB brut) part sur l'entrée standard de ffmpeg (libx264, yuv420p), sans PNG
  intermédiaires. La sortie d'erreur de ffmpeg va dans un fichier temporaire, jamais dans un tube (un tampon
  plein bloquerait l'encodage) ni dans le terminal ; elle n'est relue que si ffmpeg échoue. Sans ffmpeg : la
  séquence PNG est écrite et la commande pour l'assembler est affichée.
- playback_frames : même avancement que la fenêtre interactive (vitesse, ralenti), puis la dernière image tenue.
- record_view : joue une vue (replay, analyse, comparaison) image par image et l'enregistre ; le rendu est celui
  de la fenêtre (carton, HUD, ⏩, lerp de la caméra).
- record_population : tri animé, grille triée, puis histogramme.
"""
import os
import shlex
import shutil
import subprocess
import tempfile
import time

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import numpy as np

import config


def find_ffmpeg():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:   # paquet absent, ou binaire introuvable
        return None


def ffmpeg_args(exe, size, fps, path, source=None):
    """Commande ffmpeg : images brutes sur l'entrée standard (source None) ou séquence PNG `source`."""
    w, h = size
    if source is None:
        inp = ["-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-"]
    else:
        inp = ["-framerate", str(fps), "-i", source]
    return [exe, "-y", "-loglevel", "error", *inp, "-an", "-c:v", "libx264", "-preset", config.VIDEO_PRESET,
            "-crf", str(config.VIDEO_CRF), "-pix_fmt", "yuv420p", "-movflags", "+faststart", path]


class VideoWriter:
    """with VideoWriter(chemin, (w, h)) as out: out.write(surface) … → MP4 (ou séquence PNG sans ffmpeg)."""

    def __init__(self, path, size, fps=None, log=print, ffmpeg=None):
        self.path, self.size, self.fps, self.log = path, tuple(size), fps or config.FPS, log
        self.exe = find_ffmpeg() if ffmpeg is None else ffmpeg or None
        self.frames = 0
        self.proc = self.frames_dir = self._err = None

    def __enter__(self):
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        if self.exe:
            self._err = tempfile.TemporaryFile()
            self.proc = subprocess.Popen(ffmpeg_args(self.exe, self.size, self.fps, self.path),
                                         stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=self._err)
        else:
            self.frames_dir = os.path.splitext(self.path)[0] + "_images"
            os.makedirs(self.frames_dir, exist_ok=True)
        return self

    def write(self, surface):
        import pygame

        if self.proc is not None:
            try:
                self.proc.stdin.write(pygame.image.tobytes(surface, "RGB"))
            except BrokenPipeError:          # ffmpeg s'est arrêté : on remonte son message
                code = self.proc.wait()
                raise RuntimeError(f"ffmpeg s'est arrêté (code {code}) : {self._error()}") from None
        else:
            pygame.image.save(surface, os.path.join(self.frames_dir, f"{self.frames:06d}.png"))
        self.frames += 1

    def __exit__(self, exc_type, exc, tb):
        if self.proc is not None:
            try:
                self.proc.stdin.close()
            except BrokenPipeError:
                pass
            code = self.proc.wait()
            message = self._error() if code != 0 else ""
            self._err.close()
            if code != 0:
                self.log(f"ffmpeg a échoué (code {code}) : {message}")
                if exc_type is None:
                    raise RuntimeError(f"ffmpeg a échoué (code {code}) : {message}")
        else:
            cmd = ffmpeg_args("ffmpeg", self.size, self.fps, self.path, source=os.path.join(self.frames_dir, "%06d.png"))
            self.log(f"ffmpeg introuvable (ni dans le PATH, ni via imageio-ffmpeg) : {self.frames} images PNG écrites "
                     f"dans {self.frames_dir} ; pour les assembler : {' '.join(shlex.quote(a) for a in cmd)}")
        return False

    def _error(self):
        self._err.seek(0)
        return self._err.read().decode(errors="replace").strip()[-2000:]


def playback_frames(n_frames, speed=1.0, slow=False, hold_s=None):
    """Indices des images du replay, comme la fenêtre : +(SLOW_SPEED si ralenti, sinon 1) × vitesse par image
    affichée, puis la dernière tenue hold_s (VIDEO_HOLD_S par défaut)."""
    step = (config.SLOW_SPEED if slow else 1.0) * speed
    out, f = [], 0.0
    while f <= n_frames - 1 + 1e-9:
        out.append(int(f))
        f += step
    hold = int(round((config.VIDEO_HOLD_S if hold_s is None else hold_s) * config.FPS))
    return out + [n_frames - 1] * hold


def _open_screen():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    pygame.display.init()
    pygame.font.init()
    return pygame.display.set_mode(config.WINDOW_SIZE)


def _report(path, frames, render_s, total_s, log):
    size = os.path.getsize(path) if os.path.exists(path) else 0
    stats = {"path": path, "frames": frames, "duration_s": frames / config.FPS, "render_s": render_s,
             "total_s": total_s, "size_mb": size / 1e6}
    log(f"vidéo {path} : {frames} images, {stats['duration_s']:.1f} s à {config.FPS} images/s, "
        f"{stats['size_mb']:.1f} Mo ; rendu {render_s:.1f} s, encodage compris {total_s:.1f} s")
    return stats


def record_view(make_view, replay, path, speed=1.0, slow=False, log=print, max_frames=None):
    """Joue une vue image par image (même pas que run_interactive) et l'enregistre en MP4."""
    import pygame

    screen = _open_screen()
    view = make_view()                      # après set_mode : décor converti au format de l'écran
    follow = getattr(view, "follow", None) or (lambda f: view.camera.update(replay.ref_y[f]))
    frames = playback_frames(getattr(view, "n_frames", replay.n_frames), speed, slow)
    if max_frames is not None:
        frames = frames[:max_frames]
    view.reset_camera()
    render_s, t0 = 0.0, time.perf_counter()
    with VideoWriter(path, screen.get_size(), log=log) as out:
        for f in frames:
            a = time.perf_counter()
            follow(f)
            view.draw(screen, f, speed=speed)
            render_s += time.perf_counter() - a
            out.write(screen)
    stats = _report(path, len(frames), render_s, time.perf_counter() - t0, log)
    pygame.quit()
    return stats


def record_population(generation, path, log=print, offspring=None):
    """Vue population : tri animé, grille triée tenue VIDEO_HOLD_S, puis l'histogramme VIDEO_HIST_S.
    Avec `offspring` : cycle complet (apparition, tri, histogramme, élimination, enfants)."""
    import pygame
    from evo import population as pop

    screen = _open_screen()
    render_s, t0 = 0.0, time.perf_counter()
    if offspring is not None:
        view = pop.CycleView(generation, offspring)
        times = np.arange(0.0, view.duration, config.DT)
        with VideoWriter(path, screen.get_size(), log=log) as out:
            for t in times:
                a = time.perf_counter()
                view.draw(screen, t)
                render_s += time.perf_counter() - a
                out.write(screen)
        stats = _report(path, len(times), render_s, time.perf_counter() - t0, log)
        pygame.quit()
        return stats
    view = pop.PopulationView(generation)
    hist, _ = pop._histogram_surface(generation)
    hist = hist.convert()
    times = np.arange(0.0, pop.sort_end() + config.VIDEO_HOLD_S, config.DT)
    n_hist = int(round(config.VIDEO_HIST_S * config.FPS))
    with VideoWriter(path, screen.get_size(), log=log) as out:
        for t in times:
            a = time.perf_counter()
            view.draw(screen, t)
            render_s += time.perf_counter() - a
            out.write(screen)
        screen.blit(hist, (0, 0))
        for _ in range(n_hist):
            out.write(screen)
    stats = _report(path, len(times) + n_hist, render_s, time.perf_counter() - t0, log)
    pygame.quit()
    return stats
