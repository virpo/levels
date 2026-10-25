"""Cut generated sheets into site assets.

  icons                             every icon in art/icons.json -> site/art/icons/<level id>.webp
  find <sheet.png>                  show the ten icons a sheet holds, numbered, to add new ones to art/icons.json
  lineup <sheet.png>                the 5x2 caveman lineup -> site/art/tiers/<tier>.webp

Icons: the generator draws ten icons roughly on a 5x2 grid, but parts (sparkles, sound lines) spill over the cell lines,
so a fixed grid clips them and catches bits of the neighbours. Instead the background is flooded in from the sheet's
edges (light areas inside an icon stay), the drawn parts are grouped by distance, and every stray part joins the
nearest icon. Each icon is cut at the sheet's own resolution and scaled down smoothly onto a square: the art is
pixel-art in style, not on an exact grid, so forcing it onto one bends lines and squeezes shapes.
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
COLS, ROWS = 5, 2
OUT = 112      # px: the biggest key shows an icon at 40 CSS px; sharp on 2x screens, and close on 3x phones, where keys are smaller
MARGIN = 6     # px of air around the art inside the square


def cells(img):
    w, h = img.size
    for r in range(ROWS):
        for c in range(COLS):
            yield img.crop((c * w // COLS, r * h // ROWS, (c + 1) * w // COLS, (r + 1) * h // ROWS))


def background(a, tol=30):
    """the sheet's background: everything close to its colour that connects to the edge"""
    edge = np.concatenate([a[:4].reshape(-1, 3), a[-4:].reshape(-1, 3), a[:, :4].reshape(-1, 3), a[:, -4:].reshape(-1, 3)])
    bg = np.median(edge, 0)
    near = np.sqrt(((a.astype(int) - bg) ** 2).sum(-1)) < tol
    lab, _ = ndimage.label(near)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    return np.isin(lab, list(border)), bg


def split(sheet):
    """the ten icons on a sheet, in reading order, each as (RGBA crop of the sheet, its box)"""
    a = np.asarray(Image.open(sheet).convert("RGB"))
    bgmask, bg = background(a)
    fg = ~bgmask
    fg = ndimage.binary_opening(fg, iterations=1)                    # specks of noise in the background
    parts, n = ndimage.label(fg)
    sizes = ndimage.sum(fg, parts, range(1, n + 1))
    # grow the drawing so the pieces of one icon join up, by as much as the gaps between icons allow: some sheets
    # space them widely, some nearly touch. The first reach that gives ten icon-sized groups wins.
    for reach in (14, 10, 7, 5, 3):
        groups, g = ndimage.label(ndimage.binary_dilation(fg, iterations=reach))
        gsize = ndimage.sum(fg, groups, range(1, g + 1))
        top = np.sort(gsize)[::-1][:COLS * ROWS]
        if len(top) == COLS * ROWS and top[-1] > 0.2 * np.median(top):
            break
    else:
        raise SystemExit(f"{sheet}: couldn't find {COLS * ROWS} separate icons")
    seeds = [i + 1 for i in np.argsort(gsize)[::-1][:COLS * ROWS]]
    seedmask = {s: groups == s for s in seeds}
    dist = {s: ndimage.distance_transform_edt(~m) for s, m in seedmask.items()}
    owner = np.zeros(a.shape[:2], int)
    for s in seeds:
        owner[seedmask[s] & fg] = s
    # every stray part (a sparkle outside its icon's group) joins the nearest icon, unless it's far from all of them
    for k in range(1, n + 1):
        m = parts == k
        if owner[m].any() or sizes[k - 1] < 6:
            continue
        ys, xs = np.nonzero(m)
        d = {s: dist[s][ys, xs].min() for s in seeds}
        s = min(d, key=d.get)
        if d[s] < 60:
            owner[m] = s
    boxes = []
    for s in seeds:
        ys, xs = np.nonzero(owner == s)
        boxes.append((s, xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    mid = np.median([(b[2] + b[4]) / 2 for b in boxes])
    boxes.sort(key=lambda b: ((b[2] + b[4]) / 2 > mid, (b[1] + b[3]) / 2))
    alpha = np.where(bgmask, 0, 255).astype(np.uint8)
    out = []
    for s, x0, y0, x1, y1 in boxes:
        keep = (owner[y0:y1, x0:x1] == s) | (~bgmask[y0:y1, x0:x1] & ~fg[y0:y1, x0:x1])   # this icon, plus its light insides
        rgba = np.dstack([a[y0:y1, x0:x1], np.where(keep, alpha[y0:y1, x0:x1], 0)]).astype(np.uint8)
        out.append((rgba, (x0, y0, x1, y1)))
    return out


def square(rgba):
    """the icon scaled down smoothly to fit a square, centred"""
    im = Image.fromarray(rgba)
    room = OUT - 2 * MARGIN
    k = room / max(im.size)
    im = im.convert("RGBa").resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS).convert("RGBA")
    sq = Image.new("RGBA", (OUT, OUT))
    sq.paste(im, ((OUT - im.width) // 2, (OUT - im.height) // 2))
    return sq


def icons():
    """art/icons.json says which sheet and which of its ten icons each level uses ("t5:2" is the second icon on
    art/raw/icons-t5.png), so reordering the list or swapping one icon never means re-cutting by hand"""
    which = json.loads((ROOT / "art/icons.json").read_text())
    dest = ROOT / "site/art/icons"
    dest.mkdir(parents=True, exist_ok=True)
    sheets = {}
    for lid, ref in which.items():
        name, k = ref.split(":")
        if name not in sheets:
            sheets[name] = split(ROOT / f"art/raw/icons-{name}.png")
        square(sheets[name][int(k) - 1][0]).save(dest / f"{lid}.webp", quality=84, method=6)
    for old in dest.glob("*.png"):
        old.unlink()
    print(f"{len(which)} icons from {len(sheets)} sheets")


def find(sheet):
    """a numbered strip of a sheet's ten icons, to check the cut and pick from"""
    tiles = [square(rgba) for rgba, _ in split(sheet)]
    strip = Image.new("RGB", (OUT * len(tiles), OUT), "#E9E3D6")
    for i, t in enumerate(tiles):
        strip.paste(t, (i * OUT, 0), t)
    path = Path(sheet).with_suffix(".cut.png")
    strip.save(path)
    print(path)


def lineup(sheet):
    dest = ROOT / "site/art/tiers"
    dest.mkdir(parents=True, exist_ok=True)
    for k, cell in enumerate(cells(Image.open(sheet).convert("RGB"))):
        cell.save(dest / f"{k + 1}.webp", quality=82)
        print(f"tier {k + 1}: {cell.size}")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "icons":
        icons()
    elif cmd == "find":
        find(sys.argv[2])
    elif cmd == "lineup":
        lineup(sys.argv[2])
