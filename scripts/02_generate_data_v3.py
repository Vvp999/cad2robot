"""02_generate_data_v3.py - v3: textured part (tiles, flowers, letters) and darker scenes.

Everything new compared to v2 is marked with  # NEW v3
Run with Isaac Sim's Python:
    C:\\isaacsim\\python.bat scripts\\02_generate_data_v3.py
"""
import glob                                            # NEW v3
import math
import os
import random

from isaacsim import SimulationApp
simulation_app = SimulationApp(launch_config={"headless": False})

import carb.settings
import omni.usd
import omni.replicator.core as rep
import isaacsim.core.experimental.utils.stage as stage_utils
from pxr import Gf, Sdf, UsdGeom, UsdLux, UsdShade, Vt   # NEW v3: Sdf, UsdShade

# ---- Settings you can change ----
NUM_FRAMES = 1000                      # test with 20, then set to 1000
OUT_DIR = r"C:\cad2robot\data\v3"                       # NEW v3
TEXTURE_DIR = r"C:\cad2robot\data\textures"             # NEW v3
TABLE_TOP_Z = 0.2
NUM_DISTRACTORS = 5


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
    """Give the whole object one colour."""
    pv = UsdGeom.Gprim(prim).CreateDisplayColorPrimvar()
    pv.SetInterpolation(UsdGeom.Tokens.constant)
    pv.Set(Vt.Vec3fArray([color]))


# NEW v3: the part is now a mesh we build ourselves, so we can tell each face
# which part of the texture atlas to show ("UV coordinates").
# The built-in Cube shape has no UVs, which is why textures and per-face colours failed in v2.
def make_textured_cube(path):
    h = 0.5                                            # unit cube, centred; scaled later
    # For each face: 4 corners, going counter-clockwise when you look at the face from outside.
    # Corner 1 = bottom-left of the picture, 2 = bottom-right, 3 = top-right, 4 = top-left.
    faces = [
        [(h, -h, -h), (h, h, -h), (h, h, h), (h, -h, h)],        # +X  -> atlas cell 0
        [(-h, h, -h), (-h, -h, -h), (-h, -h, h), (-h, h, h)],    # -X  -> atlas cell 1
        [(h, h, -h), (-h, h, -h), (-h, h, h), (h, h, h)],        # +Y  -> atlas cell 2
        [(-h, -h, -h), (h, -h, -h), (h, -h, h), (-h, -h, h)],    # -Y  -> atlas cell 3
        [(-h, -h, h), (h, -h, h), (h, h, h), (-h, h, h)],        # +Z  -> atlas cell 4
        [(h, -h, -h), (-h, -h, -h), (-h, h, -h), (h, h, -h)],    # -Z  -> atlas cell 5
    ]
    normals = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
    pad = 0.003                                        # stay slightly inside each cell (no colour bleeding)
    points, uvs, nrm = [], [], []
    for f, corners in enumerate(faces):
        col, row = f % 3, f // 3                       # atlas is 3 cells wide, 2 high
        u0, u1 = col / 3 + pad, (col + 1) / 3 - pad
        v0, v1 = (1 - row) / 2 + pad, (2 - row) / 2 - pad   # row 0 is the TOP of the image (v = 0.5..1)
        points += corners
        uvs += [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
        nrm += [normals[f]] * 4
    mesh = UsdGeom.Mesh.Define(stage, path)
    mesh.CreatePointsAttr(Vt.Vec3fArray([Gf.Vec3f(*p) for p in points]))
    mesh.CreateFaceVertexCountsAttr(Vt.IntArray([4] * 6))
    mesh.CreateFaceVertexIndicesAttr(Vt.IntArray(list(range(24))))
    mesh.CreateNormalsAttr(Vt.Vec3fArray([Gf.Vec3f(*n) for n in nrm]))
    mesh.SetNormalsInterpolation(UsdGeom.Tokens.faceVarying)
    mesh.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)   # keep sharp edges, no smoothing
    st = UsdGeom.PrimvarsAPI(mesh).CreatePrimvar("st", Sdf.ValueTypeNames.TexCoord2fArray,
                                                 UsdGeom.Tokens.faceVarying)
    st.Set(Vt.Vec2fArray([Gf.Vec2f(*uv) for uv in uvs]))
    return mesh.GetPrim()


# NEW v3: a material that reads a picture file and paints it onto the mesh using the UVs
def make_texture_material(path):
    mat = UsdShade.Material.Define(stage, path)
    surface = UsdShade.Shader.Define(stage, path + "/Surface")
    surface.CreateIdAttr("UsdPreviewSurface")
    surface.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
    roughness = surface.CreateInput("roughness", Sdf.ValueTypeNames.Float)

    st_reader = UsdShade.Shader.Define(stage, path + "/StReader")
    st_reader.CreateIdAttr("UsdPrimvarReader_float2")
    st_reader.CreateInput("varname", Sdf.ValueTypeNames.String).Set("st")
    st_reader.CreateOutput("result", Sdf.ValueTypeNames.Float2)

    tex = UsdShade.Shader.Define(stage, path + "/Texture")
    tex.CreateIdAttr("UsdUVTexture")
    file_input = tex.CreateInput("file", Sdf.ValueTypeNames.Asset)
    tex.CreateInput("sourceColorSpace", Sdf.ValueTypeNames.Token).Set("sRGB")
    tex.CreateInput("wrapS", Sdf.ValueTypeNames.Token).Set("clamp")
    tex.CreateInput("wrapT", Sdf.ValueTypeNames.Token).Set("clamp")
    tex.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(st_reader.ConnectableAPI(), "result")
    tex.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)

    surface.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).ConnectToSource(tex.ConnectableAPI(), "rgb")
    mat.CreateSurfaceOutput().ConnectToSource(surface.ConnectableAPI(), "surface")
    return mat, file_input, roughness


# ---- 0. Find the textures from 01_make_textures.py ----        # NEW v3
atlases = sorted(glob.glob(os.path.join(TEXTURE_DIR, "atlas_*.png")))
if not atlases:
    raise SystemExit(f"No atlas_*.png found in {TEXTURE_DIR}. Run 01_make_textures.py first.")
print(f"Found {len(atlases)} texture atlases")

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
rep.functional.create.cube(parent="/World", name="Floor")
rep.functional.create.cube(parent="/World", name="Table")

floor = stage.GetPrimAtPath("/World/Floor")
floor_t, _, floor_s = add_ops(floor)
floor_t.Set(Gf.Vec3d(0.0, 0.0, -0.005))
floor_s.Set(Gf.Vec3f(6.0, 6.0, 0.01))

table = stage.GetPrimAtPath("/World/Table")
table_t, _, table_s = add_ops(table)
table_t.Set(Gf.Vec3d(0.55, 0.0, 0.1))
table_s.Set(Gf.Vec3f(0.8, 1.0, 0.2))

# NEW v3: textured mesh cube instead of a plain cube
part_prim = make_textured_cube("/World/Part")
rep.functional.modify.semantics(part_prim, {"class": "part"}, mode="add")
part_t, part_r, part_s = add_ops(part_prim)
part_mat, part_tex_file, part_roughness = make_texture_material("/World/Looks/PartMat")
UsdShade.MaterialBindingAPI.Apply(part_prim).Bind(part_mat)

dome = stage.GetPrimAtPath("/World/DomeLight")

# A "sun" light that casts real shadows from a random direction
sun = UsdLux.DistantLight.Define(stage, "/World/Sun")
_, sun_r, _ = add_ops(sun.GetPrim())

# Distractors: unlabelled spheres, cylinders and cones (no cubes, those would confuse the label)
distractors = []
for k in range(NUM_DISTRACTORS):
    kind = random.choice([UsdGeom.Sphere, UsdGeom.Cylinder, UsdGeom.Cone])
    g = kind.Define(stage, f"/World/Distractor{k}")
    g.GetRadiusAttr().Set(0.5)
    if kind is not UsdGeom.Sphere:
        g.GetHeightAttr().Set(1.0)
    distractors.append((g.GetPrim(), *add_ops(g.GetPrim())))

# ---- 3. Camera: our own plain camera, fully controlled by us ----
cam = UsdGeom.Camera.Define(stage, "/World/MyCam")
cam.GetFocalLengthAttr().Set(18.0)                    # wide angle, similar to a webcam
cam.GetClippingRangeAttr().Set(Gf.Vec2f(0.01, 100.0))
cam_op = UsdGeom.Xformable(cam.GetPrim()).AddTransformOp(opSuffix="c2r")
rp = rep.create.render_product("/World/MyCam", (640, 640), name="PartCam")


def place_camera(eye, target):
    """Point the camera from 'eye' at 'target' (Z is up)."""
    view = Gf.Matrix4d().SetLookAt(Gf.Vec3d(*eye), Gf.Vec3d(*target), Gf.Vec3d(0, 0, 1))
    cam_op.Set(view.GetInverse())


# ---- 3b. Texture warm-up ----                                   # NEW v3
# The renderer loads picture files in the background. Without this, the first frames
# that use a new atlas could show an untextured (grey or black) cube.
# Here we show every atlas once, close to the camera, BEFORE any image is saved.
part_s.Set(Gf.Vec3f(0.06, 0.06, 0.06))
part_t.Set(Gf.Vec3d(0.55, 0.0, TABLE_TOP_Z + 0.03))
place_camera((0.85, 0.0, 0.45), (0.55, 0.0, TABLE_TOP_Z))
for k, path in enumerate(atlases):
    part_tex_file.Set(Sdf.AssetPath(path))
    for _ in range(3):
        simulation_app.update()
    if (k + 1) % 20 == 0:
        print(f"Warm-up: loaded {k + 1}/{len(atlases)} textures")

# ---- 4. Writer ----
os.makedirs(OUT_DIR, exist_ok=True)
backend = rep.backends.get("DiskBackend")
backend.initialize(output_dir=OUT_DIR)
writer = rep.writers.get("BasicWriter")
writer.initialize(backend=backend, rgb=True, bounding_box_2d_tight=True)
writer.attach(rp)

# ---- 5. Randomise and capture ----
for i in range(NUM_FRAMES):
    # Part: random size, place, rotation, texture
    size = random.uniform(0.04, 0.07)
    px, py = 0.55 + random.uniform(-0.25, 0.25), random.uniform(-0.35, 0.35)
    part_s.Set(Gf.Vec3f(size, size, size))
    part_t.Set(Gf.Vec3d(px, py, TABLE_TOP_Z + size / 2))
    # NEW v3: also tip the cube onto a random face (90 degree steps), so letters are not always upright
    part_r.Set(Gf.Vec3f(random.choice([0, 90, 180, 270]), random.choice([0, 90, 180, 270]),
                        random.uniform(0, 360)))
    part_tex_file.Set(Sdf.AssetPath(random.choice(atlases)))   # NEW v3: random cube pattern
    part_roughness.Set(random.uniform(0.2, 0.8))               # NEW v3: from glossy plastic to matt

    # Table and floor: random colours (often light, like real tables)
    set_color(table, rand_color(0.5) if random.random() < 0.6 else rand_color())
    set_color(floor, rand_color())

    # Distractors: some visible on the table, some hidden
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

    # Lighting: NEW v3: darker range (dome down to 8 instead of 30) and the sun is off 40% of the time
    dome.GetAttribute("inputs:intensity").Set(10 ** random.uniform(math.log10(8), math.log10(1500)))
    dome.GetAttribute("inputs:color").Set(rand_color(0.75))
    sun.GetIntensityAttr().Set(0.0 if random.random() < 0.4 else random.uniform(0, 2500))
    sun_r.Set(Gf.Vec3f(random.uniform(20, 70), 0.0, random.uniform(0, 360)))

    # Camera: random distance and angle, aimed near the part
    dist = random.uniform(0.45, 1.4)
    az = math.radians(random.uniform(-90, 90))
    el = math.radians(random.uniform(30, 70))
    target = (px + random.uniform(-0.08, 0.08), py + random.uniform(-0.08, 0.08), TABLE_TOP_Z)
    eye = (target[0] + dist * math.cos(el) * math.cos(az),
           target[1] + dist * math.cos(el) * math.sin(az),
           target[2] + dist * math.sin(el))
    place_camera(eye, target)

    # Let all changes reach the renderer before capturing
    for _ in range(3):
        simulation_app.update()

    print(f"Frame {i + 1}/{NUM_FRAMES}")
    rep.orchestrator.step(rt_subframes=8)

rep.orchestrator.wait_until_complete()
writer.detach()
rp.destroy()
simulation_app.close()
