"""Commande `decor` (§5.6, chantier A) : le décor au-dessus de 23 m.

Les comparaisons de la phase 4 s'arrêtaient à ≈ 23 m (image 09). Une seule image de docs/reference/ montre le
décor plus haut : l'image 08 (t = 14:26, repère de 30 m, cadrage normal). Aucune ne couvre 30 à 50 m.
- Comparaison avec l'image 08 : le champion à son premier passage de +30 m, sans HUD, repère visible (même
  procédé que t13m55 pour 10 m) ; relevé de palette par zone (médiane, ±12, comme en phase 4) et mesures de
  forme (extension verticale de la canopée du premier plan par rapport à la ligne du repère).
- Contrôle de cohérence interne de 20 à 50 m : planche du décor à plusieurs hauteurs de caméra avec tous les
  repères, coupe du plan du tronc sur toute la hauteur ; mesures de répétition (ressemblance entre tranches
  de 5 m), de continuité des couleurs du tronc, de position des repères, de couverture en haut du décor.
"""
import json
import os

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import numpy as np

import config

CAMERA_HEIGHTS = (20, 25, 30, 35, 40, 45, 50)   # hauteur HUD visée par la caméra (m)
TOLERANCE = 12                                  # écart de palette toléré par canal (phase 4)


def _array(surface):
    import pygame
    return pygame.surfarray.array3d(surface).transpose(1, 0, 2).astype(int)


def _hex(c):
    return "#%02X%02X%02X" % tuple(int(v) for v in c)


# ---------------------------------------------------------------------------
# Palette et formes (image 08 contre nous)
# ---------------------------------------------------------------------------
def palette_roles():
    """(rôle, couleur visée ou None, boîte x0, x1, y0, y1) : même boîte dans les deux images ; seuls les
    pixels à moins de 20 (par canal) de la couleur du rôle comptent (méthode de la phase 4)."""
    return (
        ("ciel, haut", None, (800, 980, 0, 30)),
        ("ciel, milieu", config.SKY_STOPS[2][1], (0, 1280, 150, 280)),
        ("tronc, face éclairée", config.TRUNK_COLORS[1], (520, 770, 0, 720)),
        ("tronc, milieu", config.TRUNK_COLORS[4], (520, 770, 0, 720)),
        ("tronc, face sombre", config.TRUNK_COLORS[-1], (520, 770, 0, 720)),
        ("branche", config.BRANCH_COLOR, (760, 900, 380, 720)),
        ("canopée du premier plan, base", config.CANOPY_COLORS[0], (560, 1280, 150, 650)),
        ("canopée, facettes éclairées", config.CANOPY_COLORS[1], (560, 1280, 150, 650)),
        ("canopée, dessous", config.CANOPY_COLORS[2], (560, 1280, 150, 650)),
        ("lianes", config.VINE_COLOR, (560, 1280, 400, 720)),
        ("arbre latéral, tronc éclairé", config.SIDE_TREE_COLORS[0], (0, 130, 0, 720)),
        ("arbre latéral, canopée", config.SIDE_CANOPY_COLORS[0], (0, 450, 0, 720)),
        ("arbre latéral, canopée éclairée", config.SIDE_CANOPY_COLORS[1], (0, 450, 0, 720)),
        ("lointain, silhouettes kaki", config.DISTANT_COLORS[0], (0, 1280, 0, 720)),
        ("très lointain, silhouettes pâles", config.FAR_COLORS[1], (0, 1280, 0, 720)),
        ("mi-proche, palmier feuille sombre", config.MID_PALM_COLORS[0], (0, 1280, 400, 720)),
    )


def _median(img, box, color, dist=20):
    import pygame
    x0, x1, y0, y1 = box
    reg = img[y0:y1, x0:x1].reshape(-1, 3)
    if color is None:
        return np.median(reg, axis=0), len(reg)
    target = np.array(pygame.Color(color)[:3])
    mask = np.all(np.abs(reg - target) <= dist, axis=1)
    if mask.sum() < 20:
        return None, int(mask.sum())
    return np.median(reg[mask], axis=0), int(mask.sum())


def palette_table(ref, ours):
    rows = []
    for role, color, box in palette_roles():
        mr, nr = _median(ref, box, color)
        mo, no = _median(ours, box, color)
        delta = None if mr is None or mo is None else int(np.abs(mr - mo).max())
        rows.append({"role": role, "target": color, "ref": None if mr is None else _hex(mr), "ref_px": nr,
                     "ours": None if mo is None else _hex(mo), "ours_px": no, "delta": delta,
                     "ok": delta is not None and delta <= TOLERANCE})
    return rows


def marker_row(img, x0=522, x1=580):
    """Ligne (px) du repère blanc sur le tronc : rangée la plus blanche entre x0 et x1."""
    white = (img[:, x0:x1].min(axis=2) > 225).sum(axis=1)
    return int(np.argmax(white)) if white.max() > 0.5 * (x1 - x0) else None


def canopy_extent(img, marker_y, scale, x0=560, x1=1280):
    """Haut et bas (m, par rapport au repère) de la canopée du premier plan à droite du tronc."""
    import pygame
    target = np.array(pygame.Color(config.CANOPY_COLORS[0])[:3])
    mask = np.all(np.abs(img[:, x0:x1] - target) <= 22, axis=2).sum(axis=1) > 20
    rows = np.nonzero(mask)[0]
    if not len(rows) or marker_y is None:
        return None
    # bloc de lignes contigu (trous de moins de 12 px tolérés) le plus proche du repère : la canopée du repère
    runs = np.split(rows, np.nonzero(np.diff(rows) > 12)[0] + 1)
    rows = min(runs, key=lambda r: 0 if r.min() <= marker_y <= r.max() else min(abs(r.min() - marker_y), abs(r.max() - marker_y)))
    return {"top_m": (marker_y - rows.min()) / scale, "bottom_m": (marker_y - rows.max()) / scale,
            "height_m": (rows.max() - rows.min()) / scale}


# ---------------------------------------------------------------------------
# Cohérence interne en hauteur
# ---------------------------------------------------------------------------
def band_similarity(layer_rgb, layer_alpha, scale, band_m=5.0, step=2):
    """Répétitions dans une couche, découpée en tranches de `band_m` m : pour deux tranches non voisines, part des
    pixels de détail (couleur ou opacité différente du pixel du dessus) qui existent dans les deux tranches au même
    endroit avec la même couleur (±3 par canal), sur l'ensemble des détails des deux tranches. Les aplats et les
    structures verticales (troncs), pareils à toutes les hauteurs, ne comptent pas. Motif recopié → ≈ 1 ; décor tiré au hasard →
    faible. Tranches presque vides ignorées."""
    rgb = layer_rgb[::step, ::step].astype(int)
    alpha = layer_alpha[::step, ::step] > 0
    rows = int(round(band_m * scale / step))
    starts = list(range(0, rgb.shape[0] - rows + 1, rows))
    bands = np.array([rgb[k:k + rows] for k in starts])
    cover = np.array([alpha[k:k + rows] for k in starts])
    # détail = changement par rapport au pixel du dessus : les bords des structures verticales (troncs, qui
    # traversent plusieurs tranches à l'identique) ne comptent pas, un motif recopié si
    detail = np.zeros(cover.shape, dtype=bool)
    detail[:, 1:, :] = (np.abs(np.diff(bands, axis=1)).max(axis=3) > 3) | (np.diff(cover, axis=1) != 0)
    detail &= cover
    keep = [k for k in range(len(bands)) if cover[k].mean() > 0.02]
    best, pair, identical = 0.0, None, 0
    for i, ki in enumerate(keep):
        for kj in keep[i + 1:]:
            if kj - ki < 2:
                continue
            union = detail[ki] | detail[kj]
            if union.sum() < 50:
                continue
            same = (np.abs(bands[ki] - bands[kj]).max(axis=2) <= 3) & (cover[ki] == cover[kj])
            sim = float((detail[ki] & detail[kj] & same).sum() / union.sum())   # détails présents et pareils dans les deux
            if sim > best:
                best, pair = sim, (ki, kj)
            identical += int(np.array_equal(bands[ki], bands[kj]) and np.array_equal(cover[ki], cover[kj]))
    heights = None if pair is None else [round(p * band_m, 1) for p in pair]   # depuis le haut de la couche (m)
    return {"max_similarity": best, "most_similar_bands_m_from_top": heights, "identical_bands": identical,
            "bands": len(keep)}


def trunk_continuity(layer_rgb, layer_alpha, framing, offset, band_m=2.0):
    """Couleur moyenne du tronc par tranche de hauteur HUD, saut maximal entre tranches voisines, et part des
    pixels du tronc dans la palette §5.2 (±12)."""
    import pygame
    x0 = int(framing.x_px(config.TRUNK_X - config.TRUNK_WIDTH / 2 + 0.6))
    x1 = int(framing.x_px(config.TRUNK_X + config.TRUNK_WIDTH / 2 - 0.6))
    palette = np.array([pygame.Color(c)[:3] for c in config.TRUNK_COLORS + (config.BRANCH_COLOR, config.BRANCH_FACET)])
    base = config.GROUND_Y + config.START_HEIGHT
    means, shares = [], []
    top_hud = config.DECOR_TOP_HUD + (framing.y_px(base) / framing.scale)   # le plus haut visible
    for h in np.arange(0.0, top_hud - band_m, band_m):
        r1 = int(round(framing.y_px(base + h) + offset))
        r0 = int(round(framing.y_px(base + h + band_m) + offset))
        reg = layer_rgb[max(r0, 0):max(r1, 0), x0:x1].reshape(-1, 3)
        a = layer_alpha[max(r0, 0):max(r1, 0), x0:x1].ravel()
        reg = reg[a > 250]
        if len(reg) < 100:
            continue
        means.append(reg.mean(axis=0))
        near = np.min(np.abs(reg[:, None, :] - palette[None, :, :]).max(axis=2), axis=1) <= TOLERANCE
        shares.append(float(near.mean()))
    means = np.array(means)
    jumps = np.abs(np.diff(means, axis=0)).max(axis=1) if len(means) > 1 else np.zeros(1)
    return {"bands": len(means), "max_jump": float(jumps.max()), "mean_jump": float(jumps.mean()),
            "palette_share_min": float(min(shares)), "palette_share_mean": float(np.mean(shares))}


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------
def export(replay, out_dir, use_cache=True, log=print):
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    from evo.replay import JungleView, _caption, reference_image

    pygame.display.init()
    pygame.font.init()
    os.makedirs(out_dir, exist_ok=True)
    w, h = config.WINDOW_SIZE
    screen = pygame.display.set_mode((w, h))
    view = JungleView(replay, use_cache=use_cache, log=log, hud=False)
    scene, framing = view.scene, view.framing
    small = pygame.font.SysFont(config.FONT_SANS, 18)
    base = config.GROUND_Y + config.START_HEIGHT
    paths, stats = [], {}

    # 1. image 08 : le champion à son premier passage de +30 m, repère visible
    f30 = view.crossings.get(30.0)
    if f30 is None:
        raise ValueError("la créature n'atteint pas +30 m : pas de comparaison avec l'image 08")
    view.reset_camera()
    for f in range(f30 + 1):
        view.camera.update(replay.ref_y[f], snap=(f == 0))
    view.draw(screen, f30, hud=False)
    ours = screen.copy()
    ref_path = reference_image(14, 26)
    ref = pygame.image.load(ref_path).convert()
    board = pygame.Surface((2 * w, h))
    board.blit(ref, (0, 0))
    board.blit(ours, (w, 0))
    _caption(pygame, board, [f"Référence : {os.path.basename(ref_path)}"], (8, h - 44), small)
    _caption(pygame, board, [f"Nous : {replay.label()}, premier passage de +30 m (t = {replay.t[f30]:.2f} s), sans HUD"],
             (w + 8, h - 44), small)
    path = os.path.join(out_dir, "comparaison_t14m26.png")
    pygame.image.save(board, path)
    paths.append(path)
    a_ref, a_ours = _array(ref), _array(ours)
    table = palette_table(a_ref, a_ours)
    m_ref, m_ours = marker_row(a_ref), marker_row(a_ours)
    shapes = {"marker_row_px": {"ref": m_ref, "ours": m_ours},
              "front_canopy": {"ref": canopy_extent(a_ref, m_ref, config.SCENE_SCALE),
                               "ours": canopy_extent(a_ours, m_ours, framing.scale)}}
    stats["image_08"] = {"frame": f30, "t": float(replay.t[f30]), "height": float(replay.height[f30]),
                         "palette": table, "shapes": shapes}

    # 2. planche : décor à plusieurs hauteurs de caméra, tous les repères, et coupe du plan du tronc
    tw, th = w // 2, h // 2
    sheet = pygame.Surface((4 * tw, 2 * th))
    alphas = {m: 1.0 for m in scene.markers}
    marker_checks, top_trunk = [], None
    x_trunk = int(framing.x_px(config.TRUNK_X + 0.3 * config.TRUNK_WIDTH))
    for k, hud in enumerate(CAMERA_HEIGHTS):
        shift = min(max(hud * framing.scale, 0.0), scene.max_shift)
        scene.draw_back(screen, shift)
        scene.draw_markers(screen, shift, alphas)
        scene.draw_front(screen, shift)
        a = _array(screen)
        for m in scene.markers:                      # chaque repère visible est-il à sa hauteur ?
            y = framing.y_px(base + m, shift)
            if 5 <= y <= h - 5:
                col = a[:, x_trunk]
                rows = np.nonzero(col.min(axis=1) > 245)[0]
                near = rows[np.abs(rows - y) <= 3] if len(rows) else rows
                marker_checks.append({"camera": hud, "marker": m, "expected_px": round(y, 1),
                                      "drawn_px": float(near.mean()) if len(near) else None})
        if hud == CAMERA_HEIGHTS[-1]:
            top = a[0:4, int(framing.x_px(config.TRUNK_X - 0.3 * config.TRUNK_WIDTH)):x_trunk].reshape(-1, 3)
            top_trunk = float(np.mean((top[:, 0] > top[:, 2] + 40) & (top[:, 0] > 90)))
        sheet.blit(pygame.transform.smoothscale(screen, (tw, th)), ((k % 4) * tw, (k // 4) * th))
        _caption(pygame, sheet, [f"caméra à +{hud} m (vue de +{hud - 18.8:.0f} à +{hud + 16.8:.0f} m)"],
                 ((k % 4) * tw + 8, (k // 4) * th + th - 40), small)
    # coupe : plan du tronc et premier plan sur toute la hauteur, sur le ciel du milieu
    plan, _, off = scene.layers["plan"]
    front, _, foff = scene.layers.get("premier_plan", (None, None, 0))
    cut = pygame.Surface(plan.get_size())
    cut.fill(pygame.Color(config.SKY_STOPS[2][1]))
    cut.blit(plan, (0, 0))
    if front is not None:
        cut.blit(front, (0, off - foff))
    cw = int(round(cut.get_width() * th / cut.get_height()))
    cell = pygame.Surface((tw, th))
    cell.fill((24, 24, 24))
    cell.blit(pygame.transform.smoothscale(cut, (cw, th)), ((tw - cw) // 2, 0))
    k_scale = th / cut.get_height()
    tick = pygame.font.SysFont(config.FONT_SANS, 14)
    for m in range(0, int(config.DECOR_TOP_HUD) + 1, 10):
        y = (framing.y_px(base + m) + off) * k_scale
        pygame.draw.line(cell, (250, 250, 250), ((tw - cw) // 2 - 12, y), ((tw - cw) // 2 - 2, y))
        img = tick.render(f"{m} m", True, (250, 250, 250))
        cell.blit(img, img.get_rect(midright=((tw - cw) // 2 - 16, y)))
    sheet.blit(cell, (3 * tw, th))
    _caption(pygame, sheet, ["coupe du plan du tronc + premier plan, 0 → 50 m"], (3 * tw + 8, 2 * th - 40), small)
    path = os.path.join(out_dir, "planche_decor_hauteur.png")
    pygame.image.save(sheet, path)
    paths.append(path)

    # 3. mesures de cohérence
    layers = {}
    for name in ("plan", "premier_plan", "mi_proche", "lointain", "tres_lointain"):
        if name in scene.layers:
            surf = scene.layers[name][0]
            layers[name] = band_similarity(pygame.surfarray.array3d(surf).transpose(1, 0, 2),
                                           pygame.surfarray.array_alpha(surf).T, framing.scale)
    plan_rgb = pygame.surfarray.array3d(plan).transpose(1, 0, 2).astype(int)
    plan_alpha = pygame.surfarray.array_alpha(plan).T
    crossings = []
    for m in (10.0, 20.0, 30.0):
        f = view.crossings.get(m)
        if f is not None:
            crossings.append({"marker": m, "frame": int(f), "height": float(replay.height[f]),
                              "offset_px": float((replay.height[f] - m) * framing.scale)})
    placed = [c for c in marker_checks if c["drawn_px"] is not None]
    stats["coherence"] = {
        "layers": layers,
        "trunk": trunk_continuity(plan_rgb, plan_alpha, framing, off),
        "markers_drawn": marker_checks,
        "markers_max_error_px": max(abs(c["drawn_px"] - c["expected_px"]) for c in placed) if placed else None,
        "markers_at_crossing": crossings,
        "trunk_at_top_of_screen_at_50m": top_trunk,
    }
    with open(os.path.join(out_dir, "decor_hauteur.json"), "w") as fh:
        json.dump(stats, fh, indent=1, ensure_ascii=False)

    log(f"image 08 : passage de +30 m à t = {replay.t[f30]:.2f} s ; palette ({len(table)} zones, ±{TOLERANCE}) :")
    for row in table:
        mark = "ok" if row["ok"] else ("—" if row["delta"] is None else f"ÉCART {row['delta']}")
        log(f"  {row['role']:34s} réf. {row['ref'] or '—':8s} nous {row['ours'] or '—':8s} {mark}")
    fc = shapes["front_canopy"]
    if fc["ref"] and fc["ours"]:
        log(f"canopée du premier plan (m par rapport au repère de 30 m) : réf. de {fc['ref']['bottom_m']:+.1f} à "
            f"{fc['ref']['top_m']:+.1f}, nous de {fc['ours']['bottom_m']:+.1f} à {fc['ours']['top_m']:+.1f}")
    for name, st in layers.items():
        log(f"couche {name:14s} : détails identiques entre deux tranches de 5 m, au plus {st['max_similarity'] * 100:.0f} % "
            f"({st['bands']} tranches), tranches identiques {st['identical_bands']}")
    tr = stats["coherence"]["trunk"]
    log(f"tronc : {tr['bands']} tranches de 2 m, saut de couleur max {tr['max_jump']:.1f} (moyen {tr['mean_jump']:.1f}), "
        f"part dans la palette {tr['palette_share_min'] * 100:.0f} % au pire, {tr['palette_share_mean'] * 100:.0f} % en moyenne")
    log(f"repères : écart max ligne dessinée / position calculée {stats['coherence']['markers_max_error_px']} px ; "
        + ", ".join(f"{c['marker']:.0f} m : {c['offset_px']:+.1f} px au passage" for c in crossings))
    log(f"haut du décor (caméra à +50 m) : tronc sur {top_trunk * 100:.0f} % du haut de l'écran")
    pygame.quit()
    return paths, stats
