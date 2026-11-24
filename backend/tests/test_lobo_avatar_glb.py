import json
import struct
import unittest
from pathlib import Path


ASSET = Path(__file__).parents[1] / "static" / "kiosk" / "models" / "lobo-upvt-rigged.glb"


def read_glb(path):
    data = path.read_bytes()
    if data[:4] != b"glTF" or struct.unpack_from("<I", data, 8)[0] != len(data):
        raise ValueError("Invalid GLB container")
    offset = 12
    document = None
    binary = b""
    while offset < len(data):
        size, kind = struct.unpack_from("<II", data, offset)
        offset += 8
        chunk = data[offset : offset + size]
        offset += size
        if kind == 0x4E4F534A:
            document = json.loads(chunk.decode("utf-8").rstrip(" \0"))
        elif kind == 0x004E4942:
            binary = chunk
    if document is None:
        raise ValueError("GLB JSON chunk is missing")
    return document, binary


def read_vec_accessor(document, binary, accessor_index):
    accessor = document["accessors"][accessor_index]
    view = document["bufferViews"][accessor["bufferView"]]
    width = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[accessor["type"]]
    if accessor["componentType"] != 5126:
        raise ValueError("Expected float animation accessor")
    stride = view.get("byteStride", width * 4)
    start = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
    return [
        struct.unpack_from("<" + "f" * width, binary, start + index * stride)
        for index in range(accessor["count"])
    ]


def animation_values(document, binary, animation_name, bone_name, path_name):
    nodes = document["nodes"]
    animation = next(item for item in document["animations"] if item["name"] == animation_name)
    channel = next(
        item for item in animation["channels"]
        if nodes[item["target"]["node"]].get("name") == bone_name
        and item["target"]["path"] == path_name
    )
    sampler = animation["samplers"][channel["sampler"]]
    return read_vec_accessor(document, binary, sampler["output"])


class LoboAvatarGlbTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document, cls.binary = read_glb(ASSET)

    def test_glb_has_only_the_avatar_and_the_expected_rig_and_clips(self):
        names = {node.get("name", "") for node in self.document["nodes"]}
        self.assertFalse(names.intersection({"Cube", "Icosphere", "Camera", "Light"}))
        self.assertEqual(len(self.document["meshes"]), 1)
        self.assertEqual(len(self.document["meshes"][0]["primitives"]), 1)
        self.assertEqual(len(self.document["skins"][0]["joints"]), 29)
        joint_names = {
            self.document["nodes"][index].get("name", "")
            for index in self.document["skins"][0]["joints"]
        }
        self.assertTrue(
            {"UpperArm_R", "Forearm_R", "Hand_R", "Foot_L", "Ear_L", "Tail_01"}
            <= joint_names
        )
        self.assertEqual(
            {item["name"] for item in self.document["animations"]},
            {"Idle", "Hablar", "Pensar", "Saludo", "Celebrar", "Explicar"},
        )

    def test_idle_starts_arms_down_and_salute_returns_to_idle(self):
        for bone in ("UpperArm_L", "Forearm_L", "Hand_L", "UpperArm_R", "Forearm_R", "Hand_R"):
            idle = animation_values(self.document, self.binary, "Idle", bone, "rotation")
            salute = animation_values(self.document, self.binary, "Saludo", bone, "rotation")
            self.assertGreaterEqual(len(idle), 2)
            self.assertGreaterEqual(len(salute), 2)
            self.assertTrue(
                all(max(abs(a - b) for a, b in zip(value, idle[0])) < 1e-5 for value in idle),
                f"{bone} must remain relaxed while the avatar waits",
            )
            self.assertLess(
                max(abs(a - b) for a, b in zip(salute[0], idle[0])),
                1e-5,
                f"{bone} must start in the idle pose",
            )
            self.assertLess(
                max(abs(a - b) for a, b in zip(salute[-1], idle[0])),
                1e-5,
                f"{bone} must return to the idle pose after greeting",
            )

    def test_salute_moves_shoulder_elbow_and_wrist_without_raising_other_arm(self):
        for bone in ("UpperArm_R", "Forearm_R", "Hand_R"):
            salute = animation_values(self.document, self.binary, "Saludo", bone, "rotation")
            self.assertGreater(len(salute), 2, f"{bone} needs animated keyframes")
            self.assertTrue(
                any(max(abs(a - b) for a, b in zip(value, salute[0])) > 0.05 for value in salute[1:]),
                f"{bone} rotation should change during the greeting",
            )

        for bone in ("UpperArm_L", "Forearm_L", "Hand_L"):
            salute = animation_values(self.document, self.binary, "Saludo", bone, "rotation")
            self.assertTrue(
                all(max(abs(a - b) for a, b in zip(value, salute[0])) < 1e-5 for value in salute),
                f"{bone} should stay relaxed during the greeting",
            )


if __name__ == "__main__":
    unittest.main()
