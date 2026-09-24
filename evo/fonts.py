"""Polices du rendu (§5.3) : fichiers de assets/fonts/, avec repli sur les polices du système.

Questrial (HUD, cartons, repères) et Nunito Sans SemiBold (titres des slides), licence OFL.
Si un fichier manque, on prend la première police de config.FONT_SANS disponible, sinon la
police par défaut de pygame : l'affichage continue, seul le dessin des lettres change.
"""
import functools
import os

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

import config

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def path(name):
    p = config.FONT_FILES[name]
    return p if os.path.isabs(p) else os.path.join(ROOT, p)


@functools.lru_cache(maxsize=None)
def load(name, size):
    """Police `name` (clé de config.FONT_FILES) à `size` px ; repli si le fichier manque."""
    pygame.font.init()
    p = path(name)
    if os.path.exists(p):
        try:
            return pygame.font.Font(p, size)
        except (OSError, pygame.error):
            pass
    return pygame.font.SysFont(config.FONT_SANS, size)


def available(name):
    return os.path.exists(path(name))
