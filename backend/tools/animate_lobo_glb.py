"""Add restrained secondary body motion to the kiosk wolf's existing GLB clips."""

from __future__ import annotations

import json
import math
import struct
import sys
from pathlib import Path


MODEL = Path(__file__).resolve().parents[1] / "static" / "kiosk" / "models" / "lobo-upvt-rigged.glb"
BACKUP = MODEL.with_name("lobo-upvt-rigged.glb.pre-fullbody-20261120.glb")
TARGET_BONES = {
    "Tail_01", "Tail_02", "Tail_03", "Tail_04", "Tail_05", "Tail_06",
    "Ear_L", "Ear_R", "Foot_L", "Foot_R", "Thigh_L", "Thigh_R",
    "Shin_L", "Shin_R", "Chest", "Hips", "Hip_Bridge", "Head",
}
KEY_COUNT = 9
LOWER_ARMS_RADIANS = math.radians(38)


def read_glb(path: Path) -> tuple[dict, bytes, bytes]:
    raw = path.read_bytes()
    magic, version, total_length = struct.unpack_from("<4sII", raw, 0)
    if magic != b"glTF" or version != 2 or total_length != len(raw):
        raise ValueError("GLB inválido o versión no compatible.")
    offset = 12
    document = binary = None
    while offset < len(raw):
        size, kind = struct.unpack_from("<I4s", raw, offset)
        offset += 8
        chunk = raw[offset:offset + size]
        offset += size
        if kind == b"JSON":
            document = json.loads(chunk.decode("utf-8"))
        elif kind == b"BIN\x00":
            binary = chunk
    if document is None or binary is None:
        raise ValueError("Al GLB le falta JSON o BIN.")
    return document, binary, raw


def accessor_values(document: dict, binary: bytes, accessor_index: int) -> list[tuple[float, ...]]:
    accessor = document["accessors"][accessor_index]
    view = document["bufferViews"][accessor["bufferView"]]
    components = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[accessor["type"]]
    stride = view.get("byteStride", components * 4)
    start = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
    return [
        struct.unpack_from("<" + "f" * components, binary, start + index * stride)
        for index in range(accessor["count"])
    ]


def quaternion_multiply(a: tuple[float, ...], b: tuple[float, ...]) -> tuple[float, ...]:
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    )


def axis_quaternion(axis: str, angle: float) -> tuple[float, ...]:
    half = angle / 2
    sine = math.sin(half)
    return (sine if axis == "x" else 0, sine if axis == "y" else 0, sine if axis == "z" else 0, math.cos(half))


def profile(clip_name: str, bone: str, progress: float) -> float:
    phase = 2 * math.pi * progress
    wave = math.sin(phase)
    wave2 = math.sin(phase * 2 + 0.35)
    one_shot = math.sin(math.pi * progress)
    absolute = math.sin(math.pi * progress * 2)
    if bone.startswith("Tail_"):
        segment = int(bone[-1])
        amplitude = (0.035 + segment * 0.010) * {
            "Idle": 0.70, "Hablar": 0.90, "Explicar": 1.0,
            "Saludo": 1.05, "Pensar": 0.75, "Celebrar": 1.35,
        }[clip_name]
        return amplitude * (wave if clip_name in {"Idle", "Hablar", "Explicar"} else absolute) * (1 if segment % 2 else -1)
    if bone in {"Ear_L", "Ear_R"}:
        amplitude = 0.060 if bone == "Ear_L" else 0.054
        factor = 0.45 if clip_name == "Idle" else 1.0
        flick = wave2 if clip_name in {"Hablar", "Explicar", "Idle"} else absolute
        return amplitude * factor * flick * (1 if bone == "Ear_L" else -1)
    side = 1 if bone.endswith("_L") else -1
    if bone in {"Thigh_L", "Thigh_R"}:
        return side * (0.035 if clip_name == "Celebrar" else 0.012) * (absolute if clip_name not in {"Hablar", "Explicar", "Idle"} else wave)
    if bone in {"Shin_L", "Shin_R", "Foot_L", "Foot_R"}:
        amplitude = 0.050 if clip_name == "Celebrar" else 0.018 if bone.startswith("Foot") else 0.012
        return side * amplitude * (absolute if clip_name not in {"Hablar", "Explicar", "Idle"} else wave)
    if bone in {"Hips", "Hip_Bridge"}:
        return (0.028 if clip_name == "Celebrar" else 0.012) * wave
    if bone == "Chest":
        return (0.018 if clip_name == "Celebrar" else 0.010) * wave2
    if bone == "Head" and clip_name != "Pensar":
        return (0.040 if clip_name == "Saludo" else 0.018) * (one_shot if clip_name not in {"Hablar", "Explicar", "Idle"} else wave2)
    return 0.0


def axes_for(bone: str) -> tuple[str, float]:
    if bone.startswith("Tail_"):
        return "y", 1.0
    if bone.startswith("Ear_"):
        return "z", 1.0
    if bone.startswith("Foot_") or bone.startswith("Shin_"):
        return "x", 1.0
    if bone.startswith("Thigh_"):
        return "z", 1.0
    if bone in {"Hips", "Hip_Bridge"}:
        return "y", 1.0
    if bone == "Head":
        return "x", 1.0
    return "x", 1.0


def make_animation(document: dict, binary: bytearray, animation: dict, name: str, duration: float) -> int:
    nodes = document["nodes"]
    tracks: dict[str, tuple[int, dict]] = {}
    for channel in animation["channels"]:
        target = channel["target"]
        if target.get("path") != "rotation":
            continue
        bone = nodes[target["node"]].get("name", "")
        if bone in TARGET_BONES:
            tracks[bone] = (channel["sampler"], animation["samplers"][channel["sampler"]])
    if not TARGET_BONES.intersection(tracks):
        raise ValueError(f"No se encontraron huesos secundarios en {name}.")

    times = [duration * index / (KEY_COUNT - 1) for index in range(KEY_COUNT)]
    while len(binary) % 4:
        binary.append(0)
    input_offset = len(binary)
    binary.extend(struct.pack("<" + "f" * len(times), *times))
    input_view = len(document["bufferViews"])
    document["bufferViews"].append({"buffer": 0, "byteOffset": input_offset, "byteLength": 4 * len(times)})
    input_accessor = len(document["accessors"])
    document["accessors"].append({
        "bufferView": input_view,
        "componentType": 5126,
        "count": len(times),
        "type": "SCALAR",
        "min": [0.0],
        "max": [duration],
    })

    for bone, (sampler_index, sampler) in tracks.items():
        if bone == "Head" and name == "Pensar":
            continue
        node_index = next(index for index, node in enumerate(nodes) if node.get("name") == bone)
        channel = next(channel for channel in animation["channels"] if channel["sampler"] == sampler_index)
        original = accessor_values(document, bytes(binary), sampler["output"])
        base = original[0]
        axis, direction = axes_for(bone)
        quaternions = [
            quaternion_multiply(base, axis_quaternion(axis, direction * profile(name, bone, t / duration)))
            for t in times
        ]
        while len(binary) % 4:
            binary.append(0)
        output_offset = len(binary)
        for quaternion in quaternions:
            binary.extend(struct.pack("<ffff", *quaternion))
        output_view = len(document["bufferViews"])
        document["bufferViews"].append({"buffer": 0, "byteOffset": output_offset, "byteLength": 16 * len(quaternions)})
        output_accessor = len(document["accessors"])
        document["accessors"].append({
            "bufferView": output_view,
            "componentType": 5126,
            "count": len(quaternions),
            "type": "VEC4",
        })
        sampler["input"] = input_accessor
        sampler["output"] = output_accessor
        sampler["interpolation"] = "LINEAR"
        channel["target"]["node"] = node_index
    return len(tracks)


def lower_arm_poses(document: dict, binary: bytearray) -> None:
    nodes = document["nodes"]
    node_by_name = {node.get("name", ""): index for index, node in enumerate(nodes)}
    parents = {
        child: parent
        for parent, node in enumerate(nodes)
        for child in node.get("children", [])
    }
    for animation in document["animations"]:
        rotation_channels: dict[int, tuple[dict, dict]] = {}
        first_rotations: dict[int, tuple[float, ...]] = {}
        for channel in animation["channels"]:
            target = channel["target"]
            if target.get("path") != "rotation":
                continue
            sampler = animation["samplers"][channel["sampler"]]
            values = accessor_values(document, bytes(binary), sampler["output"])
            rotation_channels[target["node"]] = (channel, sampler)
            first_rotations[target["node"]] = values[0]

        world_rotation_cache: dict[int, tuple[float, ...]] = {}

        def world_rotation(node_index: int) -> tuple[float, ...]:
            if node_index in world_rotation_cache:
                return world_rotation_cache[node_index]
            local = first_rotations.get(node_index, nodes[node_index].get("rotation", (0.0, 0.0, 0.0, 1.0)))
            parent = parents.get(node_index)
            world = local if parent is None else quaternion_multiply(world_rotation(parent), local)
            world_rotation_cache[node_index] = world
            return world

        for side, sign in (("L", -1.0), ("R", 1.0)):
            node_index = node_by_name[f"UpperArm_{side}"]
            if node_index not in rotation_channels:
                continue
            _, sampler = rotation_channels[node_index]
            original = accessor_values(document, bytes(binary), sampler["output"])
            parent_rotation = world_rotation(parents[node_index])
            world_delta = axis_quaternion("z", sign * LOWER_ARMS_RADIANS)
            local_delta = quaternion_multiply(
                quaternion_multiply(( -parent_rotation[0], -parent_rotation[1], -parent_rotation[2], parent_rotation[3]), world_delta),
                parent_rotation,
            )
            lowered = [quaternion_multiply(local_delta, quaternion) for quaternion in original]
            while len(binary) % 4:
                binary.append(0)
            output_offset = len(binary)
            for quaternion in lowered:
                binary.extend(struct.pack("<ffff", *quaternion))
            output_view = len(document["bufferViews"])
            document["bufferViews"].append({"buffer": 0, "byteOffset": output_offset, "byteLength": 16 * len(lowered)})
            output_accessor = len(document["accessors"])
            document["accessors"].append({
                "bufferView": output_view,
                "componentType": 5126,
                "count": len(lowered),
                "type": "VEC4",
            })
            sampler["output"] = output_accessor


def main() -> None:
    if not MODEL.exists():
        raise SystemExit(f"No existe el avatar: {MODEL}")
    source = BACKUP if BACKUP.exists() else MODEL
    document, original_binary, original_raw = read_glb(source)
    document = json.loads(json.dumps(document))
    binary = bytearray(original_binary)
    updated = {}
    for animation in document["animations"]:
        name = animation.get("name", "")
        if name == "Idle":
            # After a visitor stops interacting the avatar remains fully still.
            updated[name] = 0
            continue
        duration = max(
            max(accessor_values(document, bytes(binary), sampler["input"])[-1][0] for sampler in animation["samplers"]),
            0.5,
        )
        updated[name] = make_animation(document, binary, animation, name, duration)

    lower_arm_poses(document, binary)

    document["buffers"][0]["byteLength"] = len(binary)
    json_chunk = json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    while len(json_chunk) % 4:
        json_chunk += b" "
    while len(binary) % 4:
        binary.append(0)
    chunks = struct.pack("<I4s", len(json_chunk), b"JSON") + json_chunk
    chunks += struct.pack("<I4s", len(binary), b"BIN\x00") + binary
    new_glb = struct.pack("<4sII", b"glTF", 2, 12 + len(chunks)) + chunks

    if not BACKUP.exists():
        BACKUP.write_bytes(original_raw)
    MODEL.write_bytes(new_glb)
    check_document, check_binary, _ = read_glb(MODEL)
    for animation in check_document["animations"]:
        for sampler in animation["samplers"]:
            if len(accessor_values(check_document, check_binary, sampler["input"])) != len(accessor_values(check_document, check_binary, sampler["output"])):
                raise RuntimeError(f"El clip {animation.get('name')} tiene entradas y salidas incompatibles.")
    print(f"Avatar actualizado: {MODEL}")
    print(f"Respaldo: {BACKUP}")
    print("Huesos secundarios actualizados por clip:", updated)


if __name__ == "__main__":
    main()
