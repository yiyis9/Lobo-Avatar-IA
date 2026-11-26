"""Create kiosk-ready motion clips for Buggy's Mixamo-style humanoid rig.

Run with Blender:
  blender -b --python animate_buggy_glb.py -- <source.glb> <output.glb>
"""

from __future__ import annotations

import sys
from pathlib import Path

import bpy


def cli_paths() -> tuple[Path, Path]:
    args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    if len(args) != 2:
        raise SystemExit("Uso: animate_buggy_glb.py -- <modelo.glb> <salida.glb>")
    return Path(args[0]).resolve(), Path(args[1]).resolve()


def pose(
    left_arm: float = -0.90,
    right_arm: float = 0.90,
    left_forearm: float = 0.0,
    right_forearm: float = 0.0,
    left_hand_roll: float = 0.0,
    right_hand_roll: float = 0.0,
    spine_breath: float = 0.0,
    head_nod: float = 0.0,
    head_turn: float = 0.0,
    left_finger_curl: float = 0.12,
    right_finger_curl: float = 0.12,
) -> dict[str, tuple[float, float, float]]:
    result = {
        "mixamorig:LeftArm": (left_arm, 0.0, 0.0),
        "mixamorig:RightArm": (right_arm, 0.0, 0.0),
        "mixamorig:LeftForeArm": (left_forearm, 0.0, 0.0),
        "mixamorig:RightForeArm": (right_forearm, 0.0, 0.0),
        "mixamorig:LeftHand": (0.0, left_hand_roll, 0.0),
        "mixamorig:RightHand": (0.0, right_hand_roll, 0.0),
        "mixamorig:Spine2": (spine_breath, 0.0, 0.0),
        "mixamorig:Head": (0.0, head_turn, head_nod),
    }
    for side, curl in (("Left", left_finger_curl), ("Right", right_finger_curl)):
        for finger in ("Index", "Middle", "Ring", "Pinky", "Thumb"):
            for segment in (1, 2, 3):
                result[f"mixamorig:{side}Hand{finger}{segment}"] = (curl, 0.0, 0.0)
    return result


def make_clips(armature: bpy.types.Object) -> list[str]:
    frames = {
        "Idle": [
            (1, pose(spine_breath=-0.015, head_turn=-0.025)),
            (23, pose(spine_breath=0.015, head_turn=0.0, head_nod=0.015)),
            (46, pose(spine_breath=-0.015, head_turn=0.025)),
            (68, pose(spine_breath=0.015, head_turn=0.0, head_nod=-0.015)),
            (91, pose(spine_breath=-0.015, head_turn=-0.025)),
        ],
        "Hablar": [
            (1, pose(spine_breath=0.0, head_nod=-0.025)),
            (10, pose(left_arm=-0.82, right_arm=0.82, left_forearm=0.04, right_forearm=-0.04, spine_breath=0.025, head_nod=0.035)),
            (20, pose(spine_breath=-0.01, head_nod=-0.02)),
            (30, pose(left_arm=-0.84, right_arm=0.84, left_forearm=0.02, right_forearm=-0.02, spine_breath=0.02, head_nod=0.03)),
            (40, pose()),
        ],
        "Explicar": [
            (1, pose()),
            (14, pose(left_arm=-0.22, right_arm=0.50, left_forearm=0.08, right_forearm=-0.06, left_hand_roll=-0.06, spine_breath=0.02, head_turn=-0.04)),
            (28, pose(left_arm=-0.38, right_arm=0.20, left_forearm=0.04, right_forearm=-0.08, right_hand_roll=0.08, spine_breath=-0.015, head_turn=0.04)),
            (42, pose(left_arm=-0.22, right_arm=0.48, left_forearm=0.07, right_forearm=-0.06, left_hand_roll=0.06, spine_breath=0.02, head_turn=-0.03)),
            (55, pose()),
        ],
        "Pensar": [
            (1, pose()),
            (10, pose(right_arm=-0.10, right_forearm=-0.82, right_hand_roll=0.12, head_turn=-0.06, head_nod=0.04)),
            (20, pose(right_arm=-0.10, right_forearm=-0.82, right_hand_roll=-0.08, head_turn=0.06, head_nod=-0.025)),
            (31, pose(right_arm=-0.10, right_forearm=-0.82, right_hand_roll=0.12, head_turn=-0.04, head_nod=0.035)),
            (40, pose()),
        ],
        "Saludo": [
            (1, pose()),
            (12, pose(left_arm=0.12, left_forearm=1.12, left_hand_roll=0.10, head_turn=-0.05, head_nod=0.025, left_finger_curl=0.02)),
            (23, pose(left_arm=0.12, left_forearm=1.12, left_hand_roll=-0.42, head_turn=-0.04, left_finger_curl=0.02)),
            (34, pose(left_arm=0.12, left_forearm=1.12, left_hand_roll=0.42, head_turn=-0.04, left_finger_curl=0.02)),
            (45, pose(left_arm=0.12, left_forearm=1.12, left_hand_roll=-0.40, head_turn=-0.04, left_finger_curl=0.02)),
            (56, pose(left_arm=0.12, left_forearm=1.12, left_hand_roll=0.40, head_turn=-0.04, left_finger_curl=0.02)),
            (68, pose(left_arm=0.12, left_forearm=1.12, left_hand_roll=0.0, head_turn=-0.03, left_finger_curl=0.02)),
            (85, pose()),
        ],
        "Celebrar": [
            (1, pose()),
            (12, pose(left_arm=0.72, right_arm=-0.72, left_forearm=0.45, right_forearm=-0.45, head_nod=-0.04, spine_breath=0.03, left_finger_curl=0.0, right_finger_curl=0.0)),
            (24, pose(left_arm=0.88, right_arm=-0.88, left_forearm=0.62, right_forearm=-0.62, head_nod=0.04, spine_breath=-0.02, left_finger_curl=0.0, right_finger_curl=0.0)),
            (36, pose(left_arm=0.72, right_arm=-0.72, left_forearm=0.45, right_forearm=-0.45, head_nod=-0.03, spine_breath=0.025, left_finger_curl=0.0, right_finger_curl=0.0)),
            (48, pose()),
        ],
        "Presentar": [
            (1, pose()),
            (14, pose(left_arm=-0.30, right_arm=0.30, left_forearm=0.12, right_forearm=-0.12, left_finger_curl=0.02, right_finger_curl=0.02, head_nod=0.015)),
            (29, pose(left_arm=-0.18, right_arm=0.18, left_forearm=0.18, right_forearm=-0.18, left_finger_curl=0.02, right_finger_curl=0.02, head_turn=0.025)),
            (44, pose(left_arm=-0.30, right_arm=0.30, left_forearm=0.12, right_forearm=-0.12, left_finger_curl=0.02, right_finger_curl=0.02, head_turn=-0.025)),
            (58, pose()),
        ],
        "Senalar": [
            (1, pose()),
            (12, pose(right_arm=-0.12, right_forearm=-0.05, right_hand_roll=0.08, right_finger_curl=0.90, head_turn=-0.06)),
            (27, pose(right_arm=-0.12, right_forearm=-0.05, right_hand_roll=0.08, right_finger_curl=0.90, head_turn=-0.03)),
            (42, pose()),
        ],
        "Asentir": [
            (1, pose(head_nod=-0.02)),
            (10, pose(head_nod=0.11)),
            (18, pose(head_nod=-0.08)),
            (27, pose(head_nod=0.09)),
            (35, pose(head_nod=-0.015)),
        ],
        "Escuchar": [
            (1, pose()),
            (12, pose(right_arm=-0.12, right_forearm=-0.82, right_hand_roll=0.10, head_turn=-0.05, head_nod=0.025)),
            (26, pose(right_arm=-0.12, right_forearm=-0.82, right_hand_roll=0.10, head_turn=0.035, head_nod=-0.02)),
            (40, pose()),
        ],
    }

    all_names = set().union(*(set(pose_data) for clip in frames.values() for _, pose_data in clip))
    missing = sorted(name for name in all_names if name not in armature.pose.bones)
    if missing:
        raise RuntimeError("Faltan huesos requeridos: " + ", ".join(missing))

    for name in all_names:
        armature.pose.bones[name].rotation_mode = "XYZ"

    for clip_name, keyframes in frames.items():
        action = bpy.data.actions.new(clip_name)
        armature.animation_data_create()
        armature.animation_data.action = action
        for frame_number, transforms in keyframes:
            for bone_name in all_names:
                bone = armature.pose.bones[bone_name]
                bone.rotation_euler = transforms.get(bone_name, (0.0, 0.0, 0.0))
                bone.keyframe_insert(data_path="rotation_euler", frame=frame_number, group=bone_name)
        action.use_fake_user = True

    armature.animation_data.action = None
    return list(frames)


def main() -> None:
    source, output = cli_paths()
    if not source.is_file():
        raise SystemExit(f"No existe el modelo de entrada: {source}")
    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(source))
    armatures = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
    if len(armatures) != 1:
        raise SystemExit(f"Se esperaba un armature; se encontraron {len(armatures)}")
    armature = armatures[0]
    clips = make_clips(armature)
    bpy.context.scene.render.fps = 30
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = 91
    bpy.ops.export_scene.gltf(
        filepath=str(output),
        export_format="GLB",
        export_animations=True,
        export_animation_mode="ACTIONS",
        export_nla_strips=False,
        export_skins=True,
        export_apply=False,
        export_cameras=False,
        export_lights=False,
    )
    print("BUGGY_ANIMATION_EXPORT", output)
    print("BUGGY_ANIMATION_CLIPS", ",".join(clips))


if __name__ == "__main__":
    main()
