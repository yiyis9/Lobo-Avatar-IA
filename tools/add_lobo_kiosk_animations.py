"""Add the animation names expected by the kiosk and export a candidate GLB."""
from pathlib import Path
import bpy

ROOT = Path(__file__).resolve().parents[1]
BLEND = ROOT / "ahora_si_lobo_articulado.blend"
OUT_BLEND = ROOT / "ahora_si_lobo_kiosk_candidate.blend"
OUT_GLB = ROOT / "ahora_si_lobo_kiosk_candidate.glb"
POSE_PREVIEW = ROOT / "lobo_kiosk_saludo_natural.png"

# El GLB de origen tiene los brazos en cruz. Este reposo relajado se anima
# explícitamente para que nunca vuelva a esa pose al terminar un gesto.
REST_L = (-0.9, 0.0, 0.0)
REST_R = (-0.9, 0.0, 0.0)
FORE_L = (-0.9, 0.0, 0.0)
FORE_R = (-0.9, 0.0, 0.0)
HANDS = (0.0, 0.0, 0.0)


def relaxed():
    return {
        "upper_arm.L": REST_L, "forearm.L": FORE_L, "hand.L": HANDS,
        "upper_arm.R": REST_R, "forearm.R": FORE_R, "hand.R": HANDS,
    }


def create_action(rig, name, frames):
    action = bpy.data.actions.new(name)
    action.use_fake_user = True
    rig.animation_data.action = action
    for frame, poses in frames:
        bpy.context.scene.frame_set(frame)
        for bone_name, rotation in poses.items():
            pose_bone = rig.pose.bones[bone_name]
            pose_bone.rotation_mode = "XYZ"
            pose_bone.rotation_euler = rotation
            pose_bone.keyframe_insert(data_path="rotation_euler", frame=frame, group=bone_name)
    return action


def main():
    bpy.ops.wm.open_mainfile(filepath=str(BLEND))
    rig = bpy.data.objects["Lobo_UPVT_Rig"]
    model = bpy.data.objects["Lobo_UPVT_Modelo"]
    scene = bpy.context.scene
    rig.animation_data_clear()
    rig.animation_data_create()
    for action in list(bpy.data.actions):
        if action.name.split(".")[0] in {"Idle", "Hablar", "Pensar", "Saludo", "Celebrar"}:
            bpy.data.actions.remove(action, do_unlink=True)

    create_action(rig, "Idle", [
        (1, {**relaxed(), "head": (0, 0, 0), "chest": (0, 0, 0)}),
        (2, {**relaxed(), "head": (0, 0, 0), "chest": (0, 0, 0)}),
    ])
    create_action(rig, "Hablar", [
        (1, {**relaxed(), "head": (0, 0, 0), "chest": (0, 0, 0)}),
        (6, {**relaxed(), "upper_arm.L": (-.72, 0, 0), "head": (.025, 0, 0), "chest": (.012, 0, 0)}),
        (12, {**relaxed(), "head": (0, 0, 0), "chest": (0, 0, 0)}),
        (18, {**relaxed(), "upper_arm.L": (-.72, 0, 0), "head": (-.02, 0, 0), "chest": (-.01, 0, 0)}),
        (24, {**relaxed(), "head": (0, 0, 0), "chest": (0, 0, 0)}),
    ])
    create_action(rig, "Pensar", [
        (1, {**relaxed(), "head": (0, 0, 0)}),
        (8, {**relaxed(), "head": (0, .10, 0), "upper_arm.L": (-.15, 0, 0), "forearm.L": (.75, 0, 0)}),
        (18, {**relaxed(), "head": (0, .10, 0), "upper_arm.L": (-.15, 0, 0), "forearm.L": (.75, 0, 0)}),
        (27, {**relaxed(), "head": (0, 0, 0)}),
    ])
    create_action(rig, "Saludo", [
        (1, {**relaxed()}),
        # Levanta el brazo sin estirarlo: hombro moderado y codo flexionado.
        (4, {**relaxed(), "upper_arm.L": (-.32, 0, 0), "forearm.L": (-.15, 0, 0)}),
        (8, {**relaxed(), "upper_arm.L": (.05, 0, 0), "forearm.L": (.70, 0, 0)}),
        # La muñeca hace el saludo lateral sobre su eje local Y; no apunta
        # la palma hacia arriba ni repite el gesto de levantar el brazo.
        (12, {**relaxed(), "upper_arm.L": (.05, 0, 0), "forearm.L": (.70, 0, 0), "hand.L": (0, .55, 0)}),
        (17, {**relaxed(), "upper_arm.L": (.05, 0, 0), "forearm.L": (.70, 0, 0), "hand.L": (0, -.55, 0)}),
        (22, {**relaxed(), "upper_arm.L": (.05, 0, 0), "forearm.L": (.70, 0, 0), "hand.L": (0, .55, 0)}),
        (27, {**relaxed(), "upper_arm.L": (.05, 0, 0), "forearm.L": (.70, 0, 0), "hand.L": (0, -.55, 0)}),
        (32, {**relaxed(), "upper_arm.L": (.05, 0, 0), "forearm.L": (.70, 0, 0), "hand.L": (0, .55, 0)}),
        (37, {**relaxed(), "upper_arm.L": (.05, 0, 0), "forearm.L": (.70, 0, 0)}),
        (44, {**relaxed()}),
    ])
    create_action(rig, "Celebrar", [
        (1, {**relaxed(), "chest": (0, 0, 0)}),
        (8, {**relaxed(), "upper_arm.L": (.35, 0, 0), "forearm.L": (.45, 0, 0), "upper_arm.R": (.35, 0, 0), "forearm.R": (.45, 0, 0), "chest": (.025, 0, 0)}),
        (15, {**relaxed(), "upper_arm.L": (.35, 0, 0), "forearm.L": (.45, 0, 0), "upper_arm.R": (.35, 0, 0), "forearm.R": (.45, 0, 0), "chest": (-.015, 0, 0)}),
        (23, {**relaxed(), "upper_arm.L": (.35, 0, 0), "forearm.L": (.45, 0, 0), "upper_arm.R": (.35, 0, 0), "forearm.R": (.45, 0, 0), "chest": (.025, 0, 0)}),
        (31, {**relaxed(), "chest": (0, 0, 0)}),
    ])

    # Set a neutral preview frame and save the five clips as separate Blender actions.
    scene.frame_set(1)
    rig.animation_data.action = bpy.data.actions["Idle"]
    scene.frame_end = 44
    scene.render.resolution_percentage = 45
    scene.render.resolution_x = 600
    scene.render.resolution_y = 680
    scene.eevee.taa_render_samples = 8
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT_BLEND))

    # Show a representative mid-wave pose and restore the editable file afterwards.
    rig.animation_data.action = bpy.data.actions["Saludo"]
    scene.frame_set(22)
    scene.render.filepath = str(POSE_PREVIEW)
    bpy.ops.render.render(write_still=True)
    scene.frame_set(1)
    rig.animation_data.action = bpy.data.actions["Idle"]
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT_BLEND))

    bpy.ops.object.select_all(action="DESELECT")
    model.select_set(True)
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.export_scene.gltf(filepath=str(OUT_GLB), export_format="GLB", use_selection=True,
                              export_animations=True, export_animation_mode="ACTIONS",
                              export_nla_strips=False, export_force_sampling=True)
    print("ACTIONS", [(a.name, tuple(a.frame_range), len(a.slots)) for a in bpy.data.actions])
    print("EXPORTED", OUT_GLB)


if __name__ == "__main__":
    main()
