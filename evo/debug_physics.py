"""Commande `debug-physics` : fenêtre interactive des 8 bancs, ou export PNG sans écran."""
import os

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import config
from evo.benches import BENCHES, H

SPEEDS = (1.0, 0.25, 0.1)
CONTROLS = "1–8 / ←→ banc · Espace pause · R recommencer · S ralenti · V vitesses"


def draw_frame(painter, bench, index, speed=1.0, paused=False):
    painter.clear()
    bench.draw(painter)
    width, height = painter.surface.get_size()
    painter.text(bench.title, (width / 2, 18), "title", anchor="midtop")
    painter.text(bench.subtitle, (width / 2, 70), "small", config.SCHEMA_TEXT_DIM, anchor="midtop")
    painter.text(f"Banc {index + 1}/{len(BENCHES)}", (16, 14), "small", config.SCHEMA_TEXT_DIM)
    status = f"t = {bench.clock:.2f} s"
    if speed != 1.0:
        status += f"   ralenti ×{speed:g}"
    if paused:
        status += "   pause"
    painter.text(status, (width - 16, 14), "mono", config.SCHEMA_TEXT_DIM, anchor="topright")
    lines = bench.metrics()
    for k, line in enumerate(lines):
        painter.text(line, (16, height - 16 - 20 * (len(lines) - k) - 20), "mono")
    controls = CONTROLS + (f" · {bench.help}" if bench.help else "")
    painter.text(controls, (16, height - 26), "small", config.SCHEMA_TEXT_DIM)


def run_interactive(start=1):
    import pygame
    from evo.render_schema import Painter, load_fonts

    pygame.display.init()
    screen = pygame.display.set_mode(config.WINDOW_SIZE)
    pygame.display.set_caption("debug-physics — moteur physique")
    painter = Painter(screen, load_fonts())
    benches = [cls() for cls in BENCHES]
    index = max(0, min(len(benches) - 1, start - 1))
    speed_idx, paused, accumulator = 0, False, 0.0
    clock = pygame.time.Clock()

    running = True
    while running:
        bench = benches[index]
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif pygame.K_1 <= event.key <= pygame.K_8:
                    index = event.key - pygame.K_1
                elif event.key == pygame.K_RIGHT:
                    index = (index + 1) % len(benches)
                elif event.key == pygame.K_LEFT:
                    index = (index - 1) % len(benches)
                elif event.key == pygame.K_SPACE:
                    paused = not paused
                elif event.key == pygame.K_r:
                    bench.reset()
                elif event.key == pygame.K_s:
                    speed_idx = (speed_idx + 1) % len(SPEEDS)
                elif event.key == pygame.K_v:
                    bench.show_velocity = not bench.show_velocity
                elif event.unicode:
                    bench.on_key(event.unicode.lower())
        bench = benches[index]

        # Le pas physique reste fixe ; le ralenti exécute simplement moins de sous-pas par image.
        if not paused:
            accumulator += SPEEDS[speed_idx] * config.SUBSTEPS
            n = int(accumulator)
            accumulator -= n
            for _ in range(n):
                bench.substep(H)

        draw_frame(painter, bench, index, SPEEDS[speed_idx], paused)
        pygame.display.flip()
        clock.tick(config.FPS)
    pygame.quit()


def export(out_dir):
    """Rendu sans écran : pour chaque banc, une image par instant de `snapshot_times`,
    une planche 2×2, puis un aperçu global (dernier instant de chaque banc)."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    from evo.render_schema import Painter, load_fonts

    pygame.display.init()
    os.makedirs(out_dir, exist_ok=True)
    width, height = config.WINDOW_SIZE
    surface = pygame.Surface(config.WINDOW_SIZE)
    painter = Painter(surface, load_fonts())
    overview = pygame.Surface((width, height * len(BENCHES) // 4))
    overview.fill(pygame.Color(config.SCHEMA_BG))

    for index, cls in enumerate(BENCHES):
        bench = cls()
        for key in bench.export_keys:
            bench.on_key(key)
        slug = cls.__name__.replace("Bench", "").lower()
        frames, done = [], 0
        for t in bench.snapshot_times:
            target = int(round(t / H))
            for _ in range(target - done):
                bench.substep(H)
            done = target
            draw_frame(painter, bench, index)
            path = os.path.join(out_dir, f"banc{bench.number}_{slug}_t{t:05.2f}.png")
            pygame.image.save(surface, path)
            frames.append(surface.copy())
        print(f"[banc {bench.number}] {bench.title}")
        for line in bench.metrics():
            print("    " + line)

        sheet = pygame.Surface(config.WINDOW_SIZE)
        sheet.fill(pygame.Color(config.SCHEMA_BG))
        for k, frame in enumerate(frames[:4]):
            small = pygame.transform.smoothscale(frame, (width // 2, height // 2))
            sheet.blit(small, ((k % 2) * width // 2, (k // 2) * height // 2))
        pygame.image.save(sheet, os.path.join(out_dir, f"planche_banc{bench.number}_{slug}.png"))

        small = pygame.transform.smoothscale(frames[-1], (width // 2, height // 2))
        overview.blit(small, ((index % 2) * width // 2, (index // 2) * height // 2))

    pygame.image.save(overview, os.path.join(out_dir, "apercu_phase1.png"))
    pygame.quit()
    print(f"Images écrites dans {out_dir}")
