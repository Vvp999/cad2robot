"""03_check_labels.py - draw the saved boxes onto the images to verify them."""
import glob
import json
import os

import numpy as np
from PIL import Image, ImageDraw

DATA = r"C:\cad2robot\data\v4"
OUT = os.path.join(DATA, "check")
os.makedirs(OUT, exist_ok=True)

for img_path in sorted(glob.glob(os.path.join(DATA, "rgb_*.png"))):
    idx = img_path[-8:-4]                       # "0000", "0001", ...
    boxes = np.load(os.path.join(DATA, f"bounding_box_2d_tight_{idx}.npy"))
    with open(os.path.join(DATA, f"bounding_box_2d_tight_labels_{idx}.json")) as f:
        labels = json.load(f)

    img = Image.open(img_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    for b in boxes:
        name = labels.get(str(b["semanticId"]), {}).get("class", "?")
        draw.rectangle([b["x_min"], b["y_min"], b["x_max"], b["y_max"]], outline="red", width=2)
        draw.text((b["x_min"], b["y_min"] - 12), name, fill="red")

    img.save(os.path.join(OUT, f"check_{idx}.png"))
    print(f"{idx}: {len(boxes)} box(es)", [(int(b['x_min']), int(b['y_min']), int(b['x_max']), int(b['y_max'])) for b in boxes])
