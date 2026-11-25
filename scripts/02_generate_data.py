"""02_generate_data.py - synthetic training images of one part on a table."""
import os
import random

from isaacsim import SimulationApp
simulation_app = SimulationApp(launch_config={"headless": False})

import carb.settings
import omni.usd
import omni.replicator.core as rep
import isaacsim.core.experimental.utils.stage as stage_utils
from pxr import Gf, UsdGeom

# ---- Settings you can change ----
NUM_FRAMES = 500
OUT_DIR = r"C:\cad2robot\data\v1"
TABLE_TOP_Z = 0.2      # table height in metres
PART_SIZE = 0.05       # 5 cm cube


def add_ops(prim):
    """Give an object its own move / rotate / scale controls."""
    if prim.IsA(UsdGeom.Cube):                     # NEW: make every cube exactly 1 m before scaling
        UsdGeom.Cube(prim).GetSizeAttr().Set(1.0)
    xf = UsdGeom.Xformable(prim)
    xf.ClearXformOpOrder()
    return (xf.AddTranslateOp(opSuffix="c2r"),
            xf.AddRotateXYZOp(opSuffix="c2r"),
            xf.AddScaleOp(opSuffix="c2r"))


# ---- 1. Scene ----
stage_utils.create_new_stage()
stage = omni.usd.get_context().get_stage()

print("BEFORE: up axis =", UsdGeom.GetStageUpAxis(stage),            # NEW: show what the stage was
      "| metres per unit =", UsdGeom.GetStageMetersPerUnit(stage))
UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)                      # NEW: Z is height, like the GUI scene
UsdGeom.SetStageMetersPerUnit(stage, 1.0)                            # NEW: 1 unit = 1 metre
print("AFTER:  up axis =", UsdGeom.GetStageUpAxis(stage),
      "| metres per unit =", UsdGeom.GetStageMetersPerUnit(stage))

rep.orchestrator.set_capture_on_play(False)
carb.settings.get_settings().set("rtx/post/dlss/execMode", 2)

rep.functional.create.xform(name="World")
rep.functional.create.dome_light(intensity=500, parent="/World", name="DomeLight")
rep.functional.create.cube(parent="/World", name="Floor")
rep.functional.create.cube(parent="/World", name="Table")
part = rep.functional.create.cube(parent="/World", name="Part")
rep.functional.modify.semantics(part, {"class": "part"}, mode="add")

floor_t, _, floor_s = add_ops(stage.GetPrimAtPath("/World/Floor"))
floor_t.Set(Gf.Vec3d(0.0, 0.0, -0.005))
floor_s.Set(Gf.Vec3f(4.0, 4.0, 0.01))

table_t, _, table_s = add_ops(stage.GetPrimAtPath("/World/Table"))
table_t.Set(Gf.Vec3d(0.55, 0.0, 0.1))
table_s.Set(Gf.Vec3f(0.6, 0.8, 0.2))

part_t, part_r, part_s = add_ops(stage.GetPrimAtPath("/World/Part"))
part_s.Set(Gf.Vec3f(PART_SIZE, PART_SIZE, PART_SIZE))

light = stage.GetPrimAtPath("/World/DomeLight")

# ---- 2. Camera (fixed, like a camera mounted over a real work cell) ----
cam = rep.functional.create.camera(position=(1.5, 0.0, 1.1),
                                   look_at=(0.55, 0.0, 0.2),
                                   parent="/World", name="Camera")
rp = rep.create.render_product(cam, (640, 640), name="PartCam")

# ---- 3. Writer ----
os.makedirs(OUT_DIR, exist_ok=True)
backend = rep.backends.get("DiskBackend")
backend.initialize(output_dir=OUT_DIR)
writer = rep.writers.get("BasicWriter")
writer.initialize(backend=backend, rgb=True, bounding_box_2d_tight=True)
writer.attach(rp)

# ---- 4. Randomise and capture ----
for i in range(NUM_FRAMES):
    x = 0.55 + random.uniform(-0.2, 0.2)
    y = 0.0 + random.uniform(-0.2, 0.2)
    part_t.Set(Gf.Vec3d(x, y, TABLE_TOP_Z + PART_SIZE / 2))
    part_r.Set(Gf.Vec3f(0.0, 0.0, random.uniform(0, 360)))

    light.GetAttribute("inputs:intensity").Set(random.uniform(200, 1500))
    light.GetAttribute("inputs:color").Set(
        Gf.Vec3f(random.uniform(0.8, 1), random.uniform(0.8, 1), random.uniform(0.8, 1)))

    print(f"Frame {i + 1}/{NUM_FRAMES}")
    rep.orchestrator.step(rt_subframes=8)

rep.orchestrator.wait_until_complete()
writer.detach()
rp.destroy()
simulation_app.close()