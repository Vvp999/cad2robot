"""04_to_yolo.py - convert Isaac Sim BasicWriter output into a YOLO dataset."""
import glob
import json
import os
import random
import shutil

import numpy as np
from PIL import Image

# ---- Settings ----
SRC = r"C:\cad2robot\data\v2"          # Isaac Sim output
DST = r"C:\cad2robot\data\yolo_v2"     # YOLO dataset
CLASSES = ["part"]                     # class 0 = "part"
VAL_SHARE = 0.1                        # 10% for validation
random.seed(0)                         # same split every run

for split in ("train", "val"):
    os.makedirs(os.path.join(DST, "images", split), exist_ok=True)
    os.makedirs(os.path.join(DST, "labels", split), exist_ok=True)

images = sorted(glob.glob(os.path.join(SRC, "rgb_*.png")))
random.shuffle(images)
n_val = int(len(images) * VAL_SHARE)
stats = {"train": 0, "val": 0, "boxes": 0, "empty_images": 0}

for k, img_path in enumerate(images):
    split = "val" if k < n_val else "train"
    idx = os.path.basename(img_path)[4:-4]          # "rgb_0042.png" -> "0042"
    w, h = Image.open(img_path).size

    boxes = np.load(os.path.join(SRC, f"bounding_box_2d_tight_{idx}.npy"))
    with open(os.path.join(SRC, f"bounding_box_2d_tight_labels_{idx}.json")) as f:
        labels = json.load(f)

    lines = []
    for b in boxes:
        name = labels.get(str(b["semanticId"]), {}).get("class")
        if name not in CLASSES:
            continue
        # clip to the image, then convert corners -> normalised centre + size
        x0, x1 = max(0.0, float(b["x_min"])), min(float(w), float(b["x_max"]))
        y0, y1 = max(0.0, float(b["y_min"])), min(float(h), float(b["y_max"]))
        if x1 <= x0 or y1 <= y0:
            continue
        cx, cy = (x0 + x1) / 2 / w, (y0 + y1) / 2 / h
        bw, bh = (x1 - x0) / w, (y1 - y0) / h
        lines.append(f"{CLASSES.index(name)} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")

    shutil.copy(img_path, os.path.join(DST, "images", split, f"{idx}.png"))
    with open(os.path.join(DST, "labels", split, f"{idx}.txt"), "w") as f:
        f.write("\n".join(lines))

    stats[split] += 1
    stats["boxes"] += len(lines)
    stats["empty_images"] += (len(lines) == 0)

# data.yaml tells YOLO where everything is
with open(os.path.join(DST, "data.yaml"), "w") as f:
    f.write(f"path: {DST.replace(chr(92), '/')}\n")
    f.write("train: images/train\nval: images/val\n")
    f.write("names:\n" + "".join(f"  {i}: {n}\n" for i, n in enumerate(CLASSES)))

print("Done:", stats)
print("Dataset:", DST)