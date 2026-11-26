"""02_generate_data_v4.py - v4: textures everywhere, plain parts too, box-shaped clutter.

Goal: the only thing that always marks the part is its CUBE SHAPE.
  - floor and table can be textured  -> "detailed" is no longer a shortcut
  - box distractors (never cubes) with packaging / tile / cube textures, also on the floor
  - the part itself is plain 25% of the time -> "no pattern" still means part
Everything new compared to v3 is marked with  # NEW v4
Run with Isaac Sim's Python:
    C:\\isaacsim\\python.bat scripts\\02_generate_data_v4.py
"""
import glob
import math
import os
import random

from isaacsim import SimulationApp
simulation_app = SimulationApp(launch_config={"headless": False})

import carb.settings
import omni.usd
import omni.replicator.core as rep
import isaacsim.core.experimental.utils.stage as stage_utils
from pxr import Gf, Sdf, UsdGeom, UsdLux, UsdShade, Vt

# ---- Settings you can change ----
NUM_FRAMES = 1000                      # test with 20, then set to 1000
OUT_DIR = r"C:\cad2robot\data\v4"                               # NEW v4
TEXTURE_DIR = r"C:\cad2robot\data\textures"                     # cube atlases (v3)
BG_TEXTURE_DIR = r"C:\cad2robot\data\bg_textures"               # NEW v4: floor/table/box textures
TABLE_TOP_Z = 0.2
NUM_DISTRACTORS = 5                  # spheres, cylinders, cones (as in v2/v3)
NUM_BOXES = 6                        # NEW v4: box-shaped clutter, on the table or on the floor
PART_PLAIN_SHARE = 0.25              # NEW v4: how often the part has one plain colour
TABLE_TEXTURED_SHARE = 0.5           # NEW v4
FLOOR_TEXTURED_SHARE = 0.6           # NEW v4


def add_ops(prim):
    """Give an object its own move / rotate / scale controls."""
    if prim.IsA(UsdGeom.Cube):
        UsdGeom.Cube(prim).GetSizeAttr().Set(1.0)
    xf = UsdGeom.Xformable(prim)
    xf.ClearXformOpOrder()
    return (xf.AddTranslateOp(opSuffix="c2r"),
            xf.AddRotateXYZOp(opSuffix="c2r"),
            xf.AddScaleOp(opSuffix="c2r"))


def rand_color(min_v=0.0):
    return Gf.Vec3f(random.uniform(min_v, 1), random.uniform(min_v, 1), random.uniform(min_v, 1))


def set_color(prim, color):
    """Give the whole object one colour (for the plain spheres, cylinders and cones)."""
    pv = UsdGeom.Gprim(prim).CreateDisplayColorPrimvar()
    pv.SetInterpolation(UsdGeom.Tokens.constant)
    pv.Set(Vt.Vec3fArray([color]))


# NEW v4: one function builds every box-shaped mesh (part, table, floor, box distractors).
# uv_mode "atlas": each face shows its own cell of a cube atlas (the part, as in v3)
# uv_mode "tile":  each face shows the whole picture, repeated 'repeat' times (floor, table, boxes)
def make_box_mesh(path, uv_mode="tile", repeat=1.0):
    h = 0.5
    faces = [
        [(h, -h, -h), (h, h, -h), (h, h, h), (h, -h, h)],        # +X
        [(-h, h, -h), (-h, -h, -h), (-h, -h, h), (-h, h, h)],    # -X
        [(h, h, -h), (-h, h, -h), (-h, h, h), (h, h, h)],        # +Y
        [(-h, -h, -h), (h, -h, -h), (h, -h, h), (-h, -h, h)],    # -Y
        [(-h, -h, h), (h, -h, h), (h, h, h), (-h, h, h)],        # +Z
        [(h, -h, -h), (-h, -h, -h), (-h, h, -h), (h, h, -h)],    # -Z
    ]
    normals = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
    pad = 0.003
    points, uvs, nrm = [], [], []
    for f, corners in enumerate(faces):
        if uv_mode == "atlas":
            col, row = f % 3, f // 3
            u0, u1 = col / 3 + pad, (col + 1) / 3 - pad
            v0, v1 = (1 - row) / 2 + pad, (2 - row) / 2 - pad
        else:
            u0, u1, v0, v1 = 0.0, repeat, 0.0, repeat
        points += corners
        uvs += [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
        nrm += [normals[f]] * 4
    mesh = UsdGeom.Mesh.Define(stage, path)
    mesh.CreatePointsAttr(Vt.Vec3fArray([Gf.Vec3f(*p) for p in points]))
    mesh.CreateFaceVertexCountsAttr(Vt.IntArray([4] * 6))
    mesh.CreateFaceVertexIndicesAttr(Vt.IntArray(list(range(24))))
    mesh.CreateNormalsAttr(Vt.Vec3fArray([Gf.Vec3f(*n) for n in nrm]))
    mesh.SetNormalsInterpolation(UsdGeom.Tokens.faceVarying)
    mesh.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)
    st = UsdGeom.PrimvarsAPI(mesh).CreatePrimvar("st", Sdf.ValueTypeNames.TexCoord2fArray,
                                                 UsdGeom.Tokens.faceVarying)
    st.Set(Vt.Vec2fArray([Gf.Vec2f(*uv) for uv in uvs]))
    return mesh.GetPrim()


def make_texture_material(path, wrap):
    """Material that paints a picture file onto the mesh (as in v3; wrap is now a choice)."""
    mat = UsdShade.Material.Define(stage, path)
    surface = UsdShade.Shader.Define(stage, path + "/Surface")
    surface.CreateIdAttr("UsdPreviewSurface")
    surface.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
    roughness = surface.CreateInput("roughness", Sdf.ValueTypeNames.Float)
    roughness.Set(0.5)
    st_reader = UsdShade.Shader.Define(stage, path + "/StReader")
    st_reader.CreateIdAttr("UsdPrimvarReader_float2")
    st_reader.CreateInput("varname", Sdf.ValueTypeNames.String).Set("st")
    st_reader.CreateOutput("result", Sdf.ValueTypeNames.Float2)
    tex = UsdShade.Shader.Define(stage, path + "/Texture")
    tex.CreateIdAttr("UsdUVTexture")
    file_input = tex.CreateInput("file", Sdf.ValueTypeNames.Asset)
    tex.CreateInput("sourceColorSpace", Sdf.ValueTypeNames.Token).Set("sRGB")
    tex.CreateInput("wrapS", Sdf.ValueTypeNames.Token).Set(wrap)
    tex.CreateInput("wrapT", Sdf.ValueTypeNames.Token).Set(wrap)
    tex.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(st_reader.ConnectableAPI(), "result")
    tex.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
    surface.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).ConnectToSource(tex.ConnectableAPI(), "rgb")
    mat.CreateSurfaceOutput().ConnectToSource(surface.ConnectableAPI(), "surface")
    return mat, file_input, roughness


# NEW v4: a plain one-colour material, so an object can switch between "textured" and "plain"
def make_plain_material(path):
    mat = UsdShade.Material.Define(stage, path)
    surface = UsdShade.Shader.Define(stage, path + "/Surface")
    surface.CreateIdAttr("UsdPreviewSurface")
    surface.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
    roughness = surface.CreateInput("roughness", Sdf.ValueTypeNames.Float)
    roughness.Set(0.5)
    color = surface.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f)
    mat.CreateSurfaceOutput().ConnectToSource(surface.ConnectableAPI(), "surface")
    return mat, color, roughness


# NEW v4: every mesh object gets BOTH materials; each frame we bind one of them
class Look:
    def __init__(self, prim, name, wrap):
        self.prim = prim
        self.binding = UsdShade.MaterialBindingAPI.Apply(prim)
        self.tex_mat, self.tex_file, self.tex_rough = make_texture_material(f"/World/Looks/{name}Tex", wrap)
        self.plain_mat, self.plain_color, self.plain_rough = make_plain_material(f"/World/Looks/{name}Plain")

    def textured(self, path, roughness=0.5):
        self.tex_file.Set(Sdf.AssetPath(path))
        self.tex_rough.Set(roughness)
        self.binding.Bind(self.tex_mat)

    def plain(self, color, roughness=0.5):
        self.plain_color.Set(color)
        self.plain_rough.Set(roughness)
        self.binding.Bind(self.plain_mat)


def plain_part_color():
    """Plain colours for the part: often grey/black/white like real metal and plastic parts."""
    if random.random() < 0.4:
        v = random.uniform(0.03, 0.9)
        return Gf.Vec3f(v, v, v)
    return rand_color()


# ---- 0. Find the textures ----
atlases = sorted(glob.glob(os.path.join(TEXTURE_DIR, "atlas_*.png")))
bg_textures = sorted(glob.glob(os.path.join(BG_TEXTURE_DIR, "bg_*.png")))    # NEW v4
if not atlases:
    raise SystemExit(f"No atlas_*.png in {TEXTURE_DIR}. Run 01_make_textures.py first.")
if not bg_textures:
    raise SystemExit(f"No bg_*.png in {BG_TEXTURE_DIR}. Run 01_make_bg_textures.py first.")
print(f"Found {len(atlases)} cube atlases and {len(bg_textures)} background textures")

# ---- 1. Stage: Z-up, metres ----
stage_utils.create_new_stage()
stage = omni.usd.get_context().get_stage()
UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
UsdGeom.SetStageMetersPerUnit(stage, 1.0)
rep.orchestrator.set_capture_on_play(False)
carb.settings.get_settings().set("rtx/post/dlss/execMode", 2)

# ---- 2. Scene objects ----
rep.functional.create.xform(name="World")
rep.functional.create.dome_light(intensity=500, parent="/World", name="DomeLight")

# NEW v4: floor and table are meshes now, so they can carry textures
floor = make_box_mesh("/World/Floor", "tile", repeat=6.0)      # picture repeats 6x across 6 m
floor_t, _, floor_s = add_ops(floor)
floor_t.Set(Gf.Vec3d(0.0, 0.0, -0.005))
floor_s.Set(Gf.Vec3f(6.0, 6.0, 0.01))
floor_look = Look(floor, "Floor", "repeat")

table = make_box_mesh("/World/Table", "tile", repeat=1.0)
table_t, _, table_s = add_ops(table)
table_t.Set(Gf.Vec3d(0.55, 0.0, 0.1))
table_s.Set(Gf.Vec3f(0.8, 1.0, 0.2))
table_look = Look(table, "Table", "repeat")

# The part: textured mesh cube as in v3, but it can also be plain now
part_prim = make_box_mesh("/World/Part", "atlas")
rep.functional.modify.semantics(part_prim, {"class": "part"}, mode="add")
part_t, part_r, part_s = add_ops(part_prim)
part_look = Look(part_prim, "Part", "clamp")

dome = stage.GetPrimAtPath("/World/DomeLight")
sun = UsdLux.DistantLight.Define(stage, "/World/Sun")
_, sun_r, _ = add_ops(sun.GetPrim())

# Distractors from v2/v3: plain spheres, cylinders and cones
distractors = []
for k in range(NUM_DISTRACTORS):
    kind = random.choice([UsdGeom.Sphere, UsdGeom.Cylinder, UsdGeom.Cone])
    g = kind.Define(stage, f"/World/Distractor{k}")
    g.GetRadiusAttr().Set(0.5)
    if kind is not UsdGeom.Sphere:
        g.GetHeightAttr().Set(1.0)
    distractors.append((g.GetPrim(), *add_ops(g.GetPrim())))

# NEW v4: box distractors (packaging-like). Never cubes: the longest side is at least 2x the shortest.
boxes = []
for k in range(NUM_BOXES):
    prim = make_box_mesh(f"/World/Box{k}", "tile", repeat=1.0)
    boxes.append((prim, *add_ops(prim), Look(prim, f"Box{k}", "repeat")))


def box_dims():
    """Three side lengths in metres, clearly not a cube."""
    longest = random.uniform(0.06, 0.25)
    shortest = random.uniform(0.015, longest / 2)
    middle = random.uniform(shortest, longest)
    dims = [longest, shortest, middle]
    random.shuffle(dims)
    return dims


def floor_spot():
    """A random spot on the floor around the table (not under it)."""
    while True:
        x, y = random.uniform(-0.6, 1.7), random.uniform(-1.3, 1.3)
        if abs(x - 0.55) > 0.5 or abs(y) > 0.6:
            return x, y


# ---- 3. Camera ----
cam = UsdGeom.Camera.Define(stage, "/World/MyCam")
cam.GetFocalLengthAttr().Set(18.0)
cam.GetClippingRangeAttr().Set(Gf.Vec2f(0.01, 100.0))
cam_op = UsdGeom.Xformable(cam.GetPrim()).AddTransformOp(opSuffix="c2r")
rp = rep.create.render_product("/World/MyCam", (640, 640), name="PartCam")


def place_camera(eye, target):
    view = Gf.Matrix4d().SetLookAt(Gf.Vec3d(*eye), Gf.Vec3d(*target), Gf.Vec3d(0, 0, 1))
    cam_op.Set(view.GetInverse())


# ---- 3b. Texture warm-up: load every picture once before any image is saved ----
part_s.Set(Gf.Vec3f(0.06, 0.06, 0.06))
part_t.Set(Gf.Vec3d(0.55, 0.0, TABLE_TOP_Z + 0.03))
place_camera((1.0, 0.0, 0.6), (0.55, 0.0, TABLE_TOP_Z))
for k, path in enumerate(atlases + bg_textures):                  # NEW v4: background textures too
    if path in atlases:
        part_look.textured(path)
    else:
        table_look.textured(path)
    for _ in range(3):
        simulation_app.update()
    if (k + 1) % 20 == 0:
        print(f"Warm-up: loaded {k + 1}/{len(atlases) + len(bg_textures)} textures")

# ---- 4. Writer ----
os.makedirs(OUT_DIR, exist_ok=True)
backend = rep.backends.get("DiskBackend")
backend.initialize(output_dir=OUT_DIR)
writer = rep.writers.get("BasicWriter")
writer.initialize(backend=backend, rgb=True, bounding_box_2d_tight=True)
writer.attach(rp)

# ---- 5. Randomise and capture ----
for i in range(NUM_FRAMES):
    # Part: random size, place, rotation; textured OR plain (NEW v4)
    size = random.uniform(0.04, 0.07)
    px, py = 0.55 + random.uniform(-0.25, 0.25), random.uniform(-0.35, 0.35)
    part_s.Set(Gf.Vec3f(size, size, size))
    part_t.Set(Gf.Vec3d(px, py, TABLE_TOP_Z + size / 2))
    part_r.Set(Gf.Vec3f(random.choice([0, 90, 180, 270]), random.choice([0, 90, 180, 270]),
                        random.uniform(0, 360)))
    if random.random() < PART_PLAIN_SHARE:
        part_look.plain(plain_part_color(), random.uniform(0.2, 0.8))
    else:
        part_look.textured(random.choice(atlases), random.uniform(0.2, 0.8))

    # NEW v4: table and floor are plain or textured
    if random.random() < TABLE_TEXTURED_SHARE:
        table_look.textured(random.choice(bg_textures), random.uniform(0.3, 0.9))
    else:
        table_look.plain(rand_color(0.5) if random.random() < 0.6 else rand_color(), random.uniform(0.3, 0.9))
    if random.random() < FLOOR_TEXTURED_SHARE:
        floor_look.textured(random.choice(bg_textures), random.uniform(0.3, 0.9))
    else:
        floor_look.plain(rand_color(), random.uniform(0.3, 0.9))

    # Plain distractors (as in v3)
    for prim, t, r, s in distractors:
        img = UsdGeom.Imageable(prim)
        if random.random() < 0.7:
            img.MakeVisible()
            d = random.uniform(0.02, 0.10)
            s.Set(Gf.Vec3f(d, d, d))
            t.Set(Gf.Vec3d(0.55 + random.uniform(-0.38, 0.38), random.uniform(-0.48, 0.48),
                           TABLE_TOP_Z + d / 2))
            r.Set(Gf.Vec3f(random.choice([0, 90]), 0, random.uniform(0, 360)))
            set_color(prim, rand_color() if random.random() < 0.7 else Gf.Vec3f(0.03, 0.03, 0.03))
        else:
            img.MakeInvisible()

    # NEW v4: box distractors, on the table (not touching the part) or on the floor around it
    for prim, t, r, s, look in boxes:
        img = UsdGeom.Imageable(prim)
        if random.random() < 0.8:
            img.MakeVisible()
            dx, dy, dz = box_dims()
            s.Set(Gf.Vec3f(dx, dy, dz))
            if random.random() < 0.5:
                while True:
                    bx, by = 0.55 + random.uniform(-0.3, 0.3), random.uniform(-0.4, 0.4)
                    if math.hypot(bx - px, by - py) > 0.06 + max(dx, dy) / 2:
                        break
                base_z = TABLE_TOP_Z
            else:
                bx, by = floor_spot()
                base_z = 0.0
            t.Set(Gf.Vec3d(bx, by, base_z + dz / 2))
            r.Set(Gf.Vec3f(0, 0, random.uniform(0, 360)))
            pick = random.random()
            if pick < 0.5:
                look.textured(random.choice(bg_textures), random.uniform(0.2, 0.9))   # packaging etc.
            elif pick < 0.8:
                look.textured(random.choice(atlases), random.uniform(0.2, 0.9))       # cube-like print!
            else:
                look.plain(rand_color(), random.uniform(0.2, 0.9))
        else:
            img.MakeInvisible()

    # Lighting (as in v3: down to very dark)
    dome.GetAttribute("inputs:intensity").Set(10 ** random.uniform(math.log10(8), math.log10(1500)))
    dome.GetAttribute("inputs:color").Set(rand_color(0.75))
    sun.GetIntensityAttr().Set(0.0 if random.random() < 0.4 else random.uniform(0, 2500))
    sun_r.Set(Gf.Vec3f(random.uniform(20, 70), 0.0, random.uniform(0, 360)))

    # Camera (as in v3)
    dist = random.uniform(0.45, 1.4)
    az = math.radians(random.uniform(-90, 90))
    el = math.radians(random.uniform(30, 70))
    target = (px + random.uniform(-0.08, 0.08), py + random.uniform(-0.08, 0.08), TABLE_TOP_Z)
    eye = (target[0] + dist * math.cos(el) * math.cos(az),
           target[1] + dist * math.cos(el) * math.sin(az),
           target[2] + dist * math.sin(el))
    place_camera(eye, target)

    for _ in range(3):
        simulation_app.update()

    print(f"Frame {i + 1}/{NUM_FRAMES}")
    rep.orchestrator.step(rt_subframes=8)

rep.orchestrator.wait_until_complete()
writer.detach()
rp.destroy()
simulation_app.close()
