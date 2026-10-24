"""Cut generated sheets into site assets.

  icons <sheet.png> <first-level>   a 5x2 pixel-art sheet -> site/art/icons/<n>.png, snapped to its art-pixel grid
  lineup <sheet.png>                the 5x2 caveman lineup -> site/art/tiers/<tier>.webp

Icons: each cell's background is keyed out, the art-pixel period is found by trying periods and keeping the one whose
blocks are most uniform, and every block becomes one pixel (its median colour). The site scales them up with
image-rendering: pixelated, so they stay crisp at any size.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
COLS, ROWS = 5, 2


def cells(img):
    w, h = img.size
    for r in range(ROWS):
        for c in range(COLS):
            yield img.crop((c * w // COLS, r * h // ROWS, (c + 1) * w // COLS, (r + 1) * h // ROWS))


def key_out(a, bg, tol=26):
    """alpha 0 where the pixel is close to the sheet's background colour"""
    d = np.sqrt(((a[..., :3].astype(int) - bg) ** 2).sum(-1))
    out = np.dstack([a[..., :3], np.where(d < tol, 0, 255).astype(np.uint8)])
    return out


def bbox(alpha):
    ys, xs = np.nonzero(alpha)
    return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1


def period(rgb, lo=6.0, hi=12.0):
    """the art-pixel size: colour edges in pixel art fall on a grid, so pick the period that lines the edges up best
    (the mean resultant length of edge positions taken modulo the period). The range holds one harmonic only."""
    g = rgb.astype(int)
    xs = np.nonzero(np.abs(np.diff(g, axis=1)).sum(-1).ravel() > 60)[0] % (g.shape[1] - 1)
    ys = np.nonzero(np.abs(np.diff(g, axis=0)).sum(-1).T.ravel() > 60)[0] % (g.shape[0] - 1)
    edges = np.concatenate([xs + 1, ys + 1]).astype(float)
    best = max(np.arange(lo, hi, 0.02), key=lambda p: abs(np.exp(2j * np.pi * edges / p).mean()))
    phase = (np.angle(np.exp(2j * np.pi * edges / best).mean()) / (2 * np.pi) * best) % best
    return best, phase


def snap(cell):
    a = np.asarray(cell.convert("RGB"))
    bg = np.median(np.concatenate([a[:6].reshape(-1, 3), a[-6:].reshape(-1, 3)]), 0)
    rgba = key_out(a, bg)
    x0, y0, x1, y1 = bbox(rgba[..., 3])
    pad = 4
    x0, y0, x1, y1 = max(0, x0 - pad), max(0, y0 - pad), min(a.shape[1], x1 + pad), min(a.shape[0], y1 + pad)
    crop = rgba[y0:y1, x0:x1]
    p, ph = period(a[y0:y1, x0:x1])
    crop = crop[int(round(ph)):, int(round(ph)):]
    n_y, n_x = int(crop.shape[0] // p), int(crop.shape[1] // p)
    out = np.zeros((n_y, n_x, 4), np.uint8)
    for j in range(n_y):
        for i in range(n_x):
            blk = crop[int(j * p):int((j + 1) * p), int(i * p):int((i + 1) * p)].reshape(-1, 4)
            if not len(blk):
                continue
            solid = blk[blk[:, 3] > 0]
            if len(solid) > len(blk) * 0.5:
                out[j, i, :3] = np.median(solid[:, :3], 0)
                out[j, i, 3] = 255
    # trim and centre on a square canvas
    x0, y0, x1, y1 = bbox(out[..., 3])
    out = out[y0:y1, x0:x1]
    s = max(out.shape[:2]) + 2
    sq = np.zeros((s, s, 4), np.uint8)
    oy, ox = (s - out.shape[0]) // 2, (s - out.shape[1]) // 2
    sq[oy:oy + out.shape[0], ox:ox + out.shape[1]] = out
    return Image.fromarray(sq), p


def icons(sheet, first):
    dest = ROOT / "site/art/icons"
    dest.mkdir(parents=True, exist_ok=True)
    for k, cell in enumerate(cells(Image.open(sheet))):
        img, p = snap(cell)
        img.save(dest / f"{first + k}.png", optimize=True)
        print(f"{first + k}: {img.size[0]}px (period {p})")


def lineup(sheet):
    dest = ROOT / "site/art/tiers"
    dest.mkdir(parents=True, exist_ok=True)
    for k, cell in enumerate(cells(Image.open(sheet).convert("RGB"))):
        cell.save(dest / f"{k + 1}.webp", quality=82)
        print(f"tier {k + 1}: {cell.size}")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "icons":
        icons(sys.argv[2], int(sys.argv[3]))
    elif cmd == "lineup":
        lineup(sys.argv[2])
