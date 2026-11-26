"""01_make_bg_textures.py - v4 step 1: random textures for floor, table and distractors.

Why: in v3 the part was the ONLY textured object in the scene, so the detector learned
"detailed = part" and boxed clutter at the photo edges. In v4 everything can be textured,
so only the cube SHAPE plus its pattern marks the part.

Run in the training venv:
    .venv\\Scripts\\activate
    python scripts\\01_make_bg_textures.py

Output: data\\bg_textures\\bg_000.png ... and data\\bg_textures\\_preview.png
"""
import os
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ---- Settings you can change ----
NUM_TEXTURES = 60
SIZE = 1024                                   # pixels, square
OUT_DIR = r"C:\cad2robot\data\bg_textures"
SEED = 4                                      # different from the cube textures (seed 3)

random.seed(SEED)
np.random.seed(SEED)


def rand_rgb(lo=0, hi=255):
    return tuple(random.randint(lo, hi) for _ in range(3))


def load_font(size):
    for name in ("arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default(size=size)


# ---- Texture types: each returns a SIZE x SIZE RGB image ----
def tex_noise():
    """Soft blotches: random small colour grids blown up and stacked (like stone or worn paint)."""
    img = np.zeros((SIZE, SIZE, 3))
    base = np.array(rand_rgb(), dtype=float)
    for cells, weight in ((4, 0.5), (16, 0.3), (64, 0.2)):          # big, medium, small blotches
        small = np.random.rand(cells, cells, 1) * 2 - 1
        layer = np.array(Image.fromarray(((small[..., 0] + 1) * 127.5).astype(np.uint8))
                         .resize((SIZE, SIZE), Image.BICUBIC), dtype=float) / 127.5 - 1
        img += layer[..., None] * weight * random.uniform(40, 120)
    return Image.fromarray(np.clip(base + img, 0, 255).astype(np.uint8))


def tex_wood():
    """Wood grain: wavy stripes in two brown-ish (or random) colours."""
    c1 = np.array(random.choice([rand_rgb(), (150, 100, 60), (190, 150, 100), (90, 60, 35)]), dtype=float)
    c2 = c1 * random.uniform(0.6, 0.85)
    y, x = np.mgrid[0:SIZE, 0:SIZE] / SIZE
    wobble = np.sin(y * random.uniform(2, 6) * np.pi) * random.uniform(0.02, 0.08)
    rings = (np.sin((x + wobble) * random.uniform(20, 60) * np.pi) + 1) / 2
    img = c1 * (1 - rings[..., None]) + c2 * rings[..., None]
    img += np.random.randn(SIZE, SIZE, 1) * 6                         # fine grain
    out = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    return out.rotate(random.choice([0, 90]))


def tex_tiles():
    """Floor or wall tiles: a grid with grout lines and slightly different tiles."""
    n = random.randint(2, 8)
    grout = random.choice([(40, 40, 40), (200, 200, 200), rand_rgb()])
    base = np.array(rand_rgb(), dtype=float)
    img = Image.new("RGB", (SIZE, SIZE), grout)
    d = ImageDraw.Draw(img)
    cell, g = SIZE / n, random.randint(2, 10)
    for i in range(n):
        for j in range(n):
            c = tuple(int(v) for v in np.clip(base + np.random.randn(3) * 12, 0, 255))
            d.rectangle((i * cell + g, j * cell + g, (i + 1) * cell - g, (j + 1) * cell - g), fill=c)
    return img


def tex_checks():
    """Fabric or tablecloth: crossing stripes (plaid)."""
    img = Image.new("RGB", (SIZE, SIZE), rand_rgb())
    over = Image.new("RGB", (SIZE, SIZE))
    d = ImageDraw.Draw(over)
    for _ in range(random.randint(2, 4)):
        c, w, step = rand_rgb(), random.randint(8, 80), random.randint(60, 250)
        for k in range(0, SIZE, step):
            d.rectangle((k, 0, k + w, SIZE), fill=c)
            d.rectangle((0, k, SIZE, k + w), fill=c)
    return Image.blend(img, over, random.uniform(0.3, 0.6))


def tex_speckle():
    """Terrazzo, granite or carpet: many small dots and chips."""
    img = Image.new("RGB", (SIZE, SIZE), rand_rgb())
    d = ImageDraw.Draw(img)
    colours = [rand_rgb() for _ in range(random.randint(2, 5))]
    for _ in range(random.randint(500, 4000)):
        x, y, r = random.uniform(0, SIZE), random.uniform(0, SIZE), random.uniform(1, 12)
        d.ellipse((x - r, y - r * random.uniform(0.4, 1), x + r, y + r), fill=random.choice(colours))
    return img


def tex_packaging():
    """Like a product box or printed paper: blocks of colour, lines of text, logos.
    This is the kind of clutter v3 wrongly boxed (e.g. a cosmetics box at the photo edge)."""
    img = Image.new("RGB", (SIZE, SIZE), random.choice([(245, 245, 245), rand_rgb()]))
    d = ImageDraw.Draw(img)
    for _ in range(random.randint(1, 4)):                              # colour blocks / bands
        x0, y0 = random.uniform(0, SIZE), random.uniform(0, SIZE)
        d.rectangle((x0, y0, x0 + random.uniform(100, 600), y0 + random.uniform(40, 400)), fill=rand_rgb())
    for _ in range(random.randint(0, 3)):                              # round logos
        x, y, r = random.uniform(0, SIZE), random.uniform(0, SIZE), random.uniform(30, 150)
        d.ellipse((x - r, y - r, x + r, y + r), outline=rand_rgb(), width=random.randint(4, 20))
    letters = "ABCDEFGHIJKLMNOPRSTUVWXYZ"
    for _ in range(random.randint(3, 15)):                             # text lines
        size = random.randint(18, 90)
        word = "".join(random.choice(letters) for _ in range(random.randint(3, 12)))
        d.text((random.uniform(0, SIZE * 0.7), random.uniform(0, SIZE)), word,
               fill=random.choice([(20, 20, 20), rand_rgb()]), font=load_font(size))
    return img.rotate(random.choice([0, 90, 180, 270]))


def tex_plain():
    """Almost plain, with a soft gradient: most real tables and walls look like this."""
    c1, c2 = np.array(rand_rgb(), dtype=float), None
    c2 = np.clip(c1 + np.random.randn(3) * 25, 0, 255)
    t = np.linspace(0, 1, SIZE)[None, :, None]
    img = c1 * (1 - t) + c2 * t + np.random.randn(SIZE, SIZE, 1) * 3
    return Image.fromarray(np.clip(np.broadcast_to(img, (SIZE, SIZE, 3)), 0, 255).astype(np.uint8))


TYPES = [tex_noise, tex_wood, tex_tiles, tex_checks, tex_speckle, tex_packaging, tex_plain]
WEIGHTS = [2, 2, 2, 1, 2, 3, 1]             # packaging is the most common clutter in the real photos


# ---- Main ----
os.makedirs(OUT_DIR, exist_ok=True)
previews = []
for k in range(NUM_TEXTURES):
    kind = random.choices(TYPES, WEIGHTS)[0]
    img = kind()
    if random.random() < 0.3:                                          # sometimes a bit blurry
        img = img.filter(ImageFilter.GaussianBlur(random.uniform(0.5, 2.5)))
    img.save(os.path.join(OUT_DIR, f"bg_{k:03d}.png"))
    if k < 24:
        previews.append(img.resize((256, 256)))
    print(f"Texture {k + 1}/{NUM_TEXTURES}: {kind.__name__}")

# Contact sheet of the first 24 textures
sheet = Image.new("RGB", (256 * 6, 256 * 4), (255, 255, 255))
for k, p in enumerate(previews):
    sheet.paste(p, ((k % 6) * 256, (k // 6) * 256))
sheet.save(os.path.join(OUT_DIR, "_preview.png"))
print("Done. Open", os.path.join(OUT_DIR, "_preview.png"))
