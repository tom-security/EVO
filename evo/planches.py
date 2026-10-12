"""Commande `planche` (chantier C2) : assemble des images existantes côte à côte, avec une légende sous chacune.

Sert aux planches avant / après faites sur le PC à partir des rendus rapatriés du runner (les captures de la vidéo,
dans docs/reference/, ne sortent jamais dans les artefacts publics du workflow). Les images sont ramenées à la même
hauteur ; facteur de réduction optionnel pour les planches larges.
"""
import os

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

CAPTION_H = 36
GAP = 8
BG = (28, 28, 28)
TEXT = (252, 252, 252)


def assemble(paths, labels=None, height=None, crop=None):
    """Surface : les images de `paths` côte à côte, à la même hauteur, chacune légendée.

    crop : (x0, y0, x1, y1) en fractions de l'image, appliqué à chaque image avant la mise à l'échelle.
    """
    pygame.font.init()
    labels = list(labels or [os.path.basename(p) for p in paths])
    if len(labels) != len(paths):
        raise ValueError("une légende par image")
    images = []
    for p in paths:
        img = pygame.image.load(p)
        if crop:
            w, h = img.get_size()
            x0, y0, x1, y1 = crop
            img = img.subsurface(pygame.Rect(int(x0 * w), int(y0 * h), int((x1 - x0) * w), int((y1 - y0) * h))).copy()
        images.append(img)
    target = height or min(img.get_height() for img in images)
    scaled = [pygame.transform.smoothscale(img, (max(1, round(img.get_width() * target / img.get_height())), target))
              for img in images]
    width = sum(s.get_width() for s in scaled) + GAP * (len(scaled) - 1)
    sheet = pygame.Surface((width, target + CAPTION_H))
    sheet.fill(BG)
    font = pygame.font.SysFont(None, 26)
    x = 0
    for s, label in zip(scaled, labels):
        sheet.blit(s, (x, 0))
        text = font.render(label, True, TEXT)
        sheet.blit(text, text.get_rect(midtop=(x + s.get_width() // 2, target + 8)))
        x += s.get_width() + GAP
    return sheet


def export(paths, out, labels=None, height=None, crop=None):
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pygame.display.init()
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    pygame.image.save(assemble(paths, labels, height, crop), out)
    return out
