"""Add a restrained, alternating explanation gesture to the kiosk wolf rig."""
from pathlib import Path
import bpy

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "ahora_si_lobo_articulado.blend"
OUTPUT_BLEND = ROOT / "ahora_si_lobo_articulado.blend"
OUTPUT_GLB = ROOT / "backend" / "static" / "kiosk" / "models" / "lobo-upvt-rigged.glb"


def key_pose(rig, frame, pose):
    bpy.context.scene.frame_set(frame)
    for name, angles in pose.items():
        bone = rig.pose.bones[name]
        bone.rotation_mode = "XYZ"
        bone.rotation_euler = angles
        bone.keyframe_insert(data_path="rotation_euler", frame=frame, group=name)


bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
rig = bpy.data.objects["Lobo_UPVT_Rig"]
model = bpy.data.objects["Lobo_UPVT_Modelo"]
scene = bpy.context.scene

old = bpy.data.actions.get("Explicar")
if old:
    bpy.data.actions.remove(old, do_unlink=True)

rest = {
    "upper_arm.L": (-0.9, 0, 0), "forearm.L": (-0.9, 0, 0), "hand.L": (0, 0, 0),
    "upper_arm.R": (-0.9, 0, 0), "forearm.R": (-0.9, 0, 0), "hand.R": (0, 0, 0),
    "head": (0, 0, 0), "chest": (0, 0, 0),
}
left_explain = {
    **rest, "upper_arm.L": (-0.68, 0, 0), "forearm.L": (-0.35, 0, 0),
    "hand.L": (0, 0.08, 0), "head": (0.012, 0, 0), "chest": (0.008, 0, 0),
}
right_explain = {
    **rest, "upper_arm.R": (-0.68, 0, 0), "forearm.R": (-0.35, 0, 0),
    "hand.R": (0, -0.08, 0), "head": (-0.012, 0, 0), "chest": (-0.008, 0, 0),
}

action = bpy.data.actions.new("Explicar")
action.use_fake_user = True
rig.animation_data_create()
rig.animation_data.action = action
for frame, pose in ((1, rest), (8, left_explain), (15, rest), (22, right_explain), (29, rest), (36, left_explain), (43, rest)):
    key_pose(rig, frame, pose)

scene.frame_end = 43
scene.frame_set(1)
rig.animation_data.action = bpy.data.actions.get("Idle") or action
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT_BLEND))

bpy.ops.object.select_all(action="DESELECT")
model.select_set(True)
rig.select_set(True)
bpy.context.view_layer.objects.active = rig
bpy.ops.export_scene.gltf(
    filepath=str(OUTPUT_GLB), export_format="GLB", use_selection=True,
    export_animations=True, export_animation_mode="ACTIONS",
    export_nla_strips=False, export_force_sampling=True,
)
print("EXPLICAR_EXPORTED", OUTPUT_GLB)
