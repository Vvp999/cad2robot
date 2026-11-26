"""05_make_textures.py - generate random pattern images to put on the part in v3."""
import os
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = r"C:\cad2robot\textures"
N = 60
SIZE = 512
CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
random.seed(1)
os.makedirs(OUT, exist_ok=True)


def rcol():
    return tuple(random.randint(0, 255) for _ in range(3))


def font(size):
    for name in ("arialbd.ttf", "arial.ttf", "segoeui.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def tiles_with_letters(d):
    """Grid of tiles, often with a letter or digit on each, like a puzzle cube."""
    n = random.choice([2, 3, 3, 4])
    step = SIZE // n
    base = rcol()
    same_colour = random.random() < 0.5
    border = random.choice([0, 4, 8])
    for i in range(n):
        for j in range(n):
            box = [i * step, j * step, (i + 1) * step - 1, (j + 1) * step - 1]
            d.rectangle(box, fill=base if same_colour else rcol(), outline=(235, 235, 235), width=border)
            if random.random() < 0.8:
                d.text((i * step + step // 2, j * step + step // 2), random.choice(CHARS),
                       fill=rcol(), font=font(int(step * 0.6)), anchor="mm")


def blobs(d):
    """Many coloured ellipses, similar to flower prints."""
    d.rectangle([0, 0, SIZE, SIZE], fill=rcol())
    for _ in range(random.randint(20, 80)):
        x, y = random.randint(0, SIZE), random.randint(0, SIZE)
        rx, ry = random.randint(8, 70), random.randint(8, 70)
        d.ellipse([x - rx, y - ry, x + rx, y + ry], fill=rcol())


def stripes(d):
    c1, c2 = rcol(), rcol()
    w = random.randint(10, 60)
    d.rectangle([0, 0, SIZE, SIZE], fill=c2)
    for x in range(0, SIZE, 2 * w):
        d.rectangle([x, 0, x + w, SIZE], fill=c1)


def checker(d):
    c1, c2 = rcol(), rcol()
    n = random.choice([4, 6, 8, 12])
    step = SIZE // n
    for i in range(n):
        for j in range(n):
            d.rectangle([i * step, j * step, (i + 1) * step, (j + 1) * step],
                        fill=c1 if (i + j) % 2 == 0 else c2)


PATTERNS = [tiles_with_letters, tiles_with_letters, blobs, stripes, checker]

for k in range(N):
    img = Image.new("RGB", (SIZE, SIZE))
    pattern = random.choice(PATTERNS)
    pattern(ImageDraw.Draw(img))
    img = img.rotate(random.choice([0, 90, 180, 270]))
    if random.random() < 0.3:
        img = img.filter(ImageFilter.GaussianBlur(random.uniform(1, 3)))
    img.save(os.path.join(OUT, f"tex_{k:03d}.png"))
    print(f"tex_{k:03d}.png  ({pattern.__name__})")

print(f"Done: {N} textures in {OUT}")