"""Create reusable rig animations and export the Lobo UPVT kiosk GLB."""

from pathlib import Path
import os

import bpy


ROOT = Path(__file__).resolve().parents[1]
BLEND_OUTPUT = Path(os.environ.get("LOBO_BLEND_OUTPUT", ROOT / "lobito art animado.blend"))
GLB_OUTPUT = Path(os.environ.get("LOBO_GLB_OUTPUT", ROOT / "backend" / "static" / "kiosk" / "models" / "lobo-upvt-rigged.glb"))

armature = bpy.data.objects.get("LoboUrbano_Rig")
model = bpy.data.objects.get("LoboUrbano_Modelo")
if armature is None or model is None:
    raise RuntimeError("No se encontraron LoboUrbano_Rig y LoboUrbano_Modelo en el archivo.")

scene = bpy.context.scene
scene.render.fps = 24
armature.animation_data_create()

# Avoid pulling the wrist out of its sleeve when an IK target is raised.
for pose_bone in armature.pose.bones:
    for constraint in pose_bone.constraints:
        if constraint.type == "IK":
            constraint.use_stretch = False


def reset_pose():
    for bone in armature.pose.bones:
        bone.location = (0.0, 0.0, 0.0)
        bone.rotation_mode = "XYZ"
        bone.rotation_euler = (0.0, 0.0, 0.0)
        bone.scale = (1.0, 1.0, 1.0)
    bpy.context.view_layer.update()


def create_action(name, frames):
    reset_pose()
    action = bpy.data.actions.new(name)
    action.use_fake_user = True
    armature.animation_data.action = action
    for frame, changes in frames:
        scene.frame_set(frame)
        for bone_name, values in changes.items():
            bone = armature.pose.bones.get(bone_name)
            if bone is None:
                raise RuntimeError(f"No existe el hueso {bone_name!r} para {name}.")
            if "location" in values:
                bone.location = values["location"]
                bone.keyframe_insert(data_path="location", frame=frame, group=bone_name)
            if "rotation" in values:
                bone.rotation_euler = values["rotation"]
                bone.keyframe_insert(data_path="rotation_euler", frame=frame, group=bone_name)
    scene.frame_set(1)
    return action


create_action("Idle", [
    (1, {"chest": {"rotation": (0.0, 0.0, 0.0)}, "tail_1": {"rotation": (0.0, 0.0, -0.025)}}),
    (12, {"chest": {"rotation": (0.018, 0.0, 0.0)}, "tail_1": {"rotation": (0.0, 0.0, 0.035)}, "tail_2": {"rotation": (0.0, 0.0, 0.02)}}),
    (24, {"chest": {"rotation": (0.0, 0.0, 0.0)}, "tail_1": {"rotation": (0.0, 0.0, -0.025)}, "tail_2": {"rotation": (0.0, 0.0, -0.015)}}),
])

create_action("Saludo", [
    (1, {"hand_IK.L": {"location": (0.0, 0.0, 0.0)}}),
    (7, {"hand_IK.L": {"location": (0.0, -0.20, 0.0)}}),
    (11, {"hand_IK.L": {"location": (0.01, -0.20, 0.0)}}),
    (15, {"hand_IK.L": {"location": (-0.01, -0.20, 0.0)}}),
    (19, {"hand_IK.L": {"location": (0.01, -0.20, 0.0)}}),
    (23, {"hand_IK.L": {"location": (-0.01, -0.20, 0.0)}}),
    (30, {"hand_IK.L": {"location": (0.0, 0.0, 0.0)}}),
])

create_action("Hablar", [
    (1, {"head": {"rotation": (0.0, 0.0, 0.0)}, "hand_IK.L": {"location": (0.0, 0.0, 0.0)}}),
    (8, {"head": {"rotation": (0.025, 0.0, 0.0)}, "hand_IK.L": {"location": (0.015, -0.025, 0.0)}}),
    (16, {"head": {"rotation": (-0.02, 0.0, 0.0)}, "hand_IK.L": {"location": (-0.015, -0.01, 0.0)}}),
    (24, {"head": {"rotation": (0.0, 0.0, 0.0)}, "hand_IK.L": {"location": (0.0, 0.0, 0.0)}}),
])

create_action("Pensar", [
    (1, {"head": {"rotation": (0.0, 0.0, 0.0)}, "hand_IK.L": {"location": (0.0, 0.0, 0.0)}}),
    (8, {"head": {"rotation": (0.0, 0.0, 0.10)}, "hand_IK.L": {"location": (-0.045, -0.08, 0.0)}}),
    (24, {"head": {"rotation": (0.0, 0.0, 0.10)}, "hand_IK.L": {"location": (-0.045, -0.08, 0.0)}}),
    (32, {"head": {"rotation": (0.0, 0.0, 0.0)}, "hand_IK.L": {"location": (0.0, 0.0, 0.0)}}),
])

create_action("Celebrar", [
    (1, {"hand_IK.L": {"location": (0.0, 0.0, 0.0)}, "hand_IK.R": {"location": (0.0, 0.0, 0.0)}, "tail_1": {"rotation": (0.0, 0.0, 0.0)}}),
    (8, {"hand_IK.L": {"location": (0.025, -0.13, 0.0)}, "hand_IK.R": {"location": (-0.025, -0.13, 0.0)}, "tail_1": {"rotation": (0.0, 0.0, 0.10)}}),
    (16, {"hand_IK.L": {"location": (0.025, -0.13, 0.0)}, "hand_IK.R": {"location": (-0.025, -0.13, 0.0)}, "tail_1": {"rotation": (0.0, 0.0, -0.10)}}),
    (24, {"hand_IK.L": {"location": (0.0, 0.0, 0.0)}, "hand_IK.R": {"location": (0.0, 0.0, 0.0)}, "tail_1": {"rotation": (0.0, 0.0, 0.0)}}),
])

reset_pose()
armature.animation_data.action = None
scene.frame_set(1)

for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == "VIEW_3D":
            area.spaces.active.shading.type = "MATERIAL"

bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_OUTPUT), check_existing=False)

bpy.ops.object.select_all(action="DESELECT")
for obj in bpy.context.scene.objects:
    if obj == armature or obj == model or (obj.type == "MESH" and obj.parent == armature):
        obj.select_set(True)
bpy.context.view_layer.objects.active = armature

result = bpy.ops.export_scene.gltf(
    filepath=str(GLB_OUTPUT),
    export_format="GLB",
    use_selection=True,
    export_skins=True,
    export_animations=True,
    export_animation_mode="ACTIONS",
    export_frame_range=False,
    export_materials="EXPORT",
    export_image_format="AUTO",
    export_cameras=False,
    export_lights=False,
    export_yup=True,
    export_apply=False,
    export_leaf_bone=False,
)
if "FINISHED" not in result:
    raise RuntimeError(f"No se pudo exportar el avatar: {result}")
print("ANIMACIONES_EXPORTADAS", [action.name for action in bpy.data.actions if action.name in {"Idle", "Saludo", "Hablar", "Pensar", "Celebrar"}])
print("BLEND_GUARDADO", BLEND_OUTPUT)
print("GLB_EXPORTADO", GLB_OUTPUT)
