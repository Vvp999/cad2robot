"""02_generate_data_v2.py - v2: much more randomisation to close the sim-to-real gap."""
import math
import os
import random

from isaacsim import SimulationApp
simulation_app = SimulationApp(launch_config={"headless": False})

import carb.settings
import omni.usd
import omni.replicator.core as rep
import isaacsim.core.experimental.utils.stage as stage_utils
from pxr import Gf, UsdGeom, UsdLux, Vt

# ---- Settings you can change ----
NUM_FRAMES = 1000                    # test with 20, then set to 1000
OUT_DIR = r"C:\cad2robot\data\v2"
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
part = rep.functional.create.cube(parent="/World", name="Part")
rep.functional.modify.semantics(part, {"class": "part"}, mode="add")

floor = stage.GetPrimAtPath("/World/Floor")
floor_t, _, floor_s = add_ops(floor)
floor_t.Set(Gf.Vec3d(0.0, 0.0, -0.005))
floor_s.Set(Gf.Vec3f(6.0, 6.0, 0.01))

table = stage.GetPrimAtPath("/World/Table")
table_t, _, table_s = add_ops(table)
table_t.Set(Gf.Vec3d(0.55, 0.0, 0.1))
table_s.Set(Gf.Vec3f(0.8, 1.0, 0.2))

part_prim = stage.GetPrimAtPath("/World/Part")
part_t, part_r, part_s = add_ops(part_prim)

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


# ---- 4. Writer ----
os.makedirs(OUT_DIR, exist_ok=True)
backend = rep.backends.get("DiskBackend")
backend.initialize(output_dir=OUT_DIR)
writer = rep.writers.get("BasicWriter")
writer.initialize(backend=backend, rgb=True, bounding_box_2d_tight=True)
writer.attach(rp)

# ---- 5. Randomise and capture ----
for i in range(NUM_FRAMES):
    # Part: random size, place, rotation, colour
    size = random.uniform(0.04, 0.07)
    px, py = 0.55 + random.uniform(-0.25, 0.25), random.uniform(-0.35, 0.35)
    part_s.Set(Gf.Vec3f(size, size, size))
    part_t.Set(Gf.Vec3d(px, py, TABLE_TOP_Z + size / 2))
    part_r.Set(Gf.Vec3f(0.0, 0.0, random.uniform(0, 360)))
    set_color(part_prim, rand_color())

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

    # Lighting: from very dim to bright, sun from a random direction
    dome.GetAttribute("inputs:intensity").Set(10 ** random.uniform(math.log10(30), math.log10(1500)))
    dome.GetAttribute("inputs:color").Set(rand_color(0.75))
    sun.GetIntensityAttr().Set(random.uniform(0, 2500))
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