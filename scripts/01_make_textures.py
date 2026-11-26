"""01_make_textures.py - v3 step 1: draw random "puzzle cube" face textures.

Run in the training venv (it needs Pillow, which came with ultralytics):
    .venv\\Scripts\\activate
    python scripts\\01_make_textures.py

Output: data\\textures\\atlas_000.png ... and data\\textures\\_preview.png
Each atlas holds the 6 faces of one cube, laid out 3 wide x 2 high:
    +------+------+------+
    |  +X  |  -X  |  +Y  |
    +------+------+------+
    |  -Y  |  +Z  |  -Z  |
    +------+------+------+
The v3 data script will wrap one atlas around the part per frame.
"""
import math
import os
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ---- Settings you can change ----
NUM_ATLASES = 100                         # 100 different cubes is plenty; each is reused ~10x
FACE_PX = 512                             # pixels per cube face
OUT_DIR = r"C:\cad2robot\data\textures"
SEED = 3                                  # same seed = same textures every run

random.seed(SEED)
LETTERS = "ABCDEFGHJKLMNPRSTUVWXYZ0123456789"


def load_font(size):
    """Find a bold font on Windows; fall back to Pillow's built-in one."""
    for name in ("arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default(size=size)


def rand_rgb(lo=0, hi=255):
    return tuple(random.randint(lo, hi) for _ in range(3))


def contrast(c):
    """White on dark colours, black or white on light ones."""
    bright = 0.3 * c[0] + 0.59 * c[1] + 0.11 * c[2]
    if bright < 140:
        return (255, 255, 255)
    return random.choice([(0, 0, 0), (255, 255, 255)])


# ---- Tile designs: each draws into the box (x0, y0, x1, y1) ----
def tile_plain(d, box):
    d.rectangle(box, fill=rand_rgb())


def tile_letter(d, box):
    """A letter or digit on a coloured tile (like the red faces of the real cube)."""
    bg = random.choice([rand_rgb(), (200, 20, 30), (180, 0, 0)])
    d.rectangle(box, fill=bg)
    x0, y0, x1, y1 = box
    font = load_font(int((y1 - y0) * random.uniform(0.5, 0.8)))
    d.text(((x0 + x1) / 2, (y0 + y1) / 2), random.choice(LETTERS),
           fill=contrast(bg), font=font, anchor="mm")


def tile_flowers(d, box):
    """A few simple flowers: petals around a centre, on a coloured background."""
    d.rectangle(box, fill=rand_rgb(80, 255))
    x0, y0, x1, y1 = box
    w = x1 - x0
    for _ in range(random.randint(1, 4)):
        cx, cy = random.uniform(x0, x1), random.uniform(y0, y1)
        r = w * random.uniform(0.12, 0.3)
        petal = rand_rgb()
        n = random.randint(5, 8)
        for k in range(n):
            a = 2 * math.pi * k / n
            px, py = cx + r * 0.6 * math.cos(a), cy + r * 0.6 * math.sin(a)
            d.ellipse((px - r * 0.4, py - r * 0.4, px + r * 0.4, py + r * 0.4), fill=petal)
        d.ellipse((cx - r * 0.25, cy - r * 0.25, cx + r * 0.25, cy + r * 0.25), fill=rand_rgb())


def tile_stripes(d, box):
    x0, y0, x1, y1 = box
    c1, c2 = rand_rgb(), rand_rgb()
    d.rectangle(box, fill=c1)
    step = max(4, int((x1 - x0) / random.randint(3, 8)))
    for x in range(int(x0) - int(y1 - y0), int(x1), step * 2):   # diagonal stripes
        d.polygon([(x, y1), (x + step, y1), (x + step + (y1 - y0), y0), (x + (y1 - y0), y0)], fill=c2)


def tile_dots(d, box):
    x0, y0, x1, y1 = box
    d.rectangle(box, fill=rand_rgb())
    dot = rand_rgb()
    n = random.randint(2, 5)
    r = (x1 - x0) / n * 0.3
    for i in range(n):
        for j in range(n):
            cx = x0 + (i + 0.5) * (x1 - x0) / n
            cy = y0 + (j + 0.5) * (y1 - y0) / n
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=dot)


TILE_TYPES = [tile_plain, tile_letter, tile_flowers, tile_stripes, tile_dots]
TILE_WEIGHTS = [3, 2, 3, 1, 1]          # flowers and letters are common, like the real cube


def make_face(face_style):
    """One cube face: an N x N grid of tiles with dark gaps between them."""
    img = Image.new("RGB", (FACE_PX, FACE_PX), face_style["gap_color"])
    n = face_style["grid"]
    gap = face_style["gap"]
    cell = FACE_PX // n
    tile_px = max(8, cell - 2 * gap)
    # Some faces share one tile design (like a whole red letter face), others mix designs
    one_type = random.choice(TILE_TYPES) if random.random() < 0.4 else None
    for i in range(n):
        for j in range(n):
            # Draw each tile on its own small image, so flowers cannot spill into neighbours
            tile = Image.new("RGB", (tile_px, tile_px))
            kind = one_type or random.choices(TILE_TYPES, TILE_WEIGHTS)[0]
            kind(ImageDraw.Draw(tile), (0, 0, tile_px - 1, tile_px - 1))
            img.paste(tile, (i * cell + gap, j * cell + gap))
    return img


def make_atlas():
    # One "style" per cube, so all 6 faces look like the same object
    style = {
        "grid": random.choices([3, 2, 4, 1], [6, 1, 1, 1])[0],   # mostly 3x3, like the real cube
        "gap": random.choice([0, 4, 8, 14, 20]),                   # 0 = no visible gap
        "gap_color": random.choice([(10, 10, 10), (30, 30, 30), (230, 230, 230), rand_rgb()]),
    }
    atlas = Image.new("RGB", (FACE_PX * 3, FACE_PX * 2))
    for f in range(6):
        atlas.paste(make_face(style), ((f % 3) * FACE_PX, (f // 3) * FACE_PX))
    # A little blur and noise so the edges are not unrealistically sharp
    if random.random() < 0.5:
        atlas = atlas.filter(ImageFilter.GaussianBlur(random.uniform(0.5, 2.0)))
    noise = Image.effect_noise(atlas.size, random.uniform(5, 25)).convert("RGB")
    return Image.blend(atlas, noise, random.uniform(0.0, 0.12))


# ---- Main ----
os.makedirs(OUT_DIR, exist_ok=True)
previews = []
for k in range(NUM_ATLASES):
    atlas = make_atlas()
    atlas.save(os.path.join(OUT_DIR, f"atlas_{k:03d}.png"))
    if k < 12:
        previews.append(atlas.resize((384, 256)))
    print(f"Atlas {k + 1}/{NUM_ATLASES}")

# Contact sheet of the first 12 atlases, so you can check them in one picture
sheet = Image.new("RGB", (384 * 4, 256 * 3), (255, 255, 255))
for k, p in enumerate(previews):
    sheet.paste(p, ((k % 4) * 384, (k // 4) * 256))
sheet.save(os.path.join(OUT_DIR, "_preview.png"))
print("Done. Open", os.path.join(OUT_DIR, "_preview.png"))
