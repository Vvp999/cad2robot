"""00_make_part.py - design the two test parts as 3D models (no CAD program needed).

Part A: V-block      - a standard workshop part that holds round workpieces.
                       50 x 30 x 25 mm, 90-degree V-groove on top, relief slot underneath,
                       chamfered top edges. Made by drawing its side profile and pushing it
                       50 mm deep ("extrusion").
Part B: flanged bushing - round, flange 40 mm, body 25 mm, 30 mm high, 12 mm bore.
                       Made by drawing half its cross-section and spinning it around
                       the centre axis ("revolve", like a lathe).

Every number is a setting below, so a new part variant is one edit away.

Run in the training venv (needs numpy + matplotlib, both came with ultralytics):
    .venv\\Scripts\\activate
    python scripts\\00_make_part.py

Output in C:\\cad2robot\\cad\\
    part_a_vblock.stl, part_b_bushing.stl   -> for the 3D printer (millimetres)
    part_a_vblock.obj, part_b_bushing.obj   -> for Isaac Sim (metres)
    _preview.png                            -> picture of both parts
"""
import math
import os
import struct

import matplotlib
matplotlib.use("Agg")                      # draw to a file, no window
import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

OUT_DIR = r"C:\cad2robot\cad"

# ---- Part A settings (millimetres) ----
A_WIDTH, A_HEIGHT, A_LENGTH = 30.0, 25.0, 50.0
A_V_OPEN, A_V_DEPTH = 16.0, 8.0            # V-groove: 16 mm wide at the top, 8 mm deep (= 90 degrees)
A_SLOT_W, A_SLOT_D = 8.0, 3.0              # relief slot underneath
A_CHAMFER = 2.0                            # chamfer on the two outer top edges

# ---- Part B settings (millimetres) ----
B_FLANGE_D, B_FLANGE_H = 40.0, 6.0
B_BODY_D, B_HEIGHT = 25.0, 30.0
B_BORE_D = 12.0
B_CHAMFER = 1.0                            # small chamfer on the top outer edge
B_SEGMENTS = 96                            # how round the circle is (more = smoother)


# ---------- geometry helpers ----------
def triangulate(poly):
    """Split a simple polygon (counter-clockwise list of (x, y)) into triangles ("ear clipping")."""
    idx = list(range(len(poly)))
    tris = []

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    def inside(p, a, b, c):
        return cross(a, b, p) >= 0 and cross(b, c, p) >= 0 and cross(c, a, p) >= 0

    while len(idx) > 3:
        for k in range(len(idx)):
            i0, i1, i2 = idx[k - 1], idx[k], idx[(k + 1) % len(idx)]
            a, b, c = poly[i0], poly[i1], poly[i2]
            if cross(a, b, c) <= 0:                       # not a convex corner -> not an ear
                continue
            if any(inside(poly[j], a, b, c) for j in idx if j not in (i0, i1, i2)):
                continue
            tris.append((i0, i1, i2))
            idx.pop(k)
            break
        else:
            raise ValueError("Profile could not be triangulated - check that it does not cross itself")
    tris.append(tuple(idx))
    return tris


def extrude(profile, length):
    """Profile in the X-Z plane (counter-clockwise, seen from the front), pushed 'length' along Y."""
    n = len(profile)
    front = [(x, -length / 2, z) for x, z in profile]
    back = [(x, length / 2, z) for x, z in profile]
    verts = front + back
    faces = []
    for t in triangulate(profile):                       # front cap faces -Y, back cap faces +Y
        faces.append((t[0], t[2], t[1]))
        faces.append((t[0] + n, t[1] + n, t[2] + n))
    for i in range(n):                                   # side walls: one quad (2 triangles) per edge
        j = (i + 1) % n
        faces.append((i, j, j + n))
        faces.append((i, j + n, i + n))
    return np.array(verts, float), np.array(faces, int)


def revolve(profile, segments):
    """Half cross-section as (radius, z) points, spun around the Z axis (like a lathe)."""
    n = len(profile)
    verts = []
    for s in range(segments):
        a = 2 * math.pi * s / segments
        for r, z in profile:
            verts.append((r * math.cos(a), r * math.sin(a), z))
    faces = []
    for s in range(segments):
        t = (s + 1) % segments
        for i in range(n):
            j = (i + 1) % n
            p0, p1 = s * n + i, s * n + j
            q0, q1 = t * n + i, t * n + j
            faces.append((p0, q0, q1))
            faces.append((p0, q1, p1))
    return np.array(verts, float), np.array(faces, int)


def fix_orientation(v, f):
    """Make sure all triangles face outwards (needed for printing and for correct lighting)."""
    tri = v[f]
    volume = np.sum(np.einsum("ij,ij->i", tri[:, 0], np.cross(tri[:, 1], tri[:, 2]))) / 6
    return (f[:, ::-1] if volume < 0 else f), abs(volume)


def check_watertight(f):
    """Every edge must be shared by exactly 2 triangles, else the printer slicer complains."""
    edges = {}
    for a, b, c in f:
        for e in ((a, b), (b, c), (c, a)):
            key = tuple(sorted(e))
            edges[key] = edges.get(key, 0) + 1
    return all(count == 2 for count in edges.values())


def save_stl(path, v, f):
    """Binary STL in millimetres (what 3D printer software expects)."""
    tri = v[f]
    normals = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    normals /= np.linalg.norm(normals, axis=1, keepdims=True)
    with open(path, "wb") as fh:
        fh.write(b"cad2robot part".ljust(80, b" "))
        fh.write(struct.pack("<I", len(f)))
        for nrm, t in zip(normals, tri):
            fh.write(struct.pack("<12fH", *nrm, *t[0], *t[1], *t[2], 0))


def save_obj(path, v, f):
    """OBJ in metres (Isaac Sim's stage is in metres)."""
    with open(path, "w") as fh:
        for x, y, z in v / 1000.0:
            fh.write(f"v {x:.6f} {y:.6f} {z:.6f}\n")
        for a, b, c in f + 1:                            # OBJ counts from 1
            fh.write(f"f {a} {b} {c}\n")


# ---------- Part A: V-block (side profile, counter-clockwise) ----------
w, h = A_WIDTH / 2, A_HEIGHT
profile_a = [
    (-w, 0), (-A_SLOT_W / 2, 0), (-A_SLOT_W / 2, A_SLOT_D),            # bottom, into the slot
    (A_SLOT_W / 2, A_SLOT_D), (A_SLOT_W / 2, 0), (w, 0),               # out of the slot
    (w, h - A_CHAMFER), (w - A_CHAMFER, h),                            # right side + chamfer
    (A_V_OPEN / 2, h), (0, h - A_V_DEPTH), (-A_V_OPEN / 2, h),         # the V-groove
    (-w + A_CHAMFER, h), (-w, h - A_CHAMFER),                          # left chamfer
]
va, fa = extrude(profile_a, A_LENGTH)

# ---------- Part B: flanged bushing (half cross-section, radius vs height) ----------
rb, rf, rbody = B_BORE_D / 2, B_FLANGE_D / 2, B_BODY_D / 2
profile_b = [
    (rb, 0), (rf, 0), (rf, B_FLANGE_H), (rbody, B_FLANGE_H),
    (rbody, B_HEIGHT - B_CHAMFER), (rbody - B_CHAMFER, B_HEIGHT), (rb, B_HEIGHT),
]
vb, fb = revolve(profile_b, B_SEGMENTS)

# ---------- Save and check ----------
os.makedirs(OUT_DIR, exist_ok=True)
parts = [("part_a_vblock", va, fa), ("part_b_bushing", vb, fb)]
for name, v, f in parts:
    f, vol = fix_orientation(v, f)
    ok = check_watertight(f)
    size = v.max(axis=0) - v.min(axis=0)
    save_stl(os.path.join(OUT_DIR, name + ".stl"), v, f)
    save_obj(os.path.join(OUT_DIR, name + ".obj"), v, f)
    print(f"{name}: {size[0]:.1f} x {size[1]:.1f} x {size[2]:.1f} mm, volume {vol / 1000:.1f} cm3, "
          f"{len(f)} triangles, watertight: {ok}")

# ---------- Preview picture ----------
fig = plt.figure(figsize=(10, 5))
for k, (name, v, f) in enumerate(parts):
    ax = fig.add_subplot(1, 2, k + 1, projection="3d")
    ax.add_collection3d(Poly3DCollection(v[f], facecolor="#9aa4ad", edgecolor="#4a525a", linewidths=0.2))
    lim = np.abs(v).max()
    ax.set_xlim(-lim, lim); ax.set_ylim(-lim, lim); ax.set_zlim(0, 2 * lim)
    ax.view_init(elev=28, azim=-55)
    ax.set_title(name.replace("_", " "))
    ax.set_xlabel("x mm"); ax.set_ylabel("y mm"); ax.set_zlabel("z mm")
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "_preview.png"), dpi=120)
print("Done. Open", os.path.join(OUT_DIR, "_preview.png"))
