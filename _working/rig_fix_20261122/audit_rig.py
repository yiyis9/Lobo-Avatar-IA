import bpy
import json
import math
from mathutils import Euler


def edge_lengths(mesh_obj, depsgraph=None):
    if depsgraph:
        evaluated = mesh_obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        matrix = evaluated.matrix_world
        coords = [matrix @ v.co for v in mesh.vertices]
        edges = [tuple(e.vertices) for e in mesh.edges]
        lengths = [(coords[a] - coords[b]).length for a, b in edges]
        evaluated.to_mesh_clear()
        return lengths
    mesh = mesh_obj.data
    coords = [mesh_obj.matrix_world @ v.co for v in mesh.vertices]
    return [(coords[e.vertices[0]] - coords[e.vertices[1]]).length for e in mesh.edges]


def evaluated_coords(mesh_obj, depsgraph):
    evaluated = mesh_obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    coords = [tuple(evaluated.matrix_world @ v.co) for v in mesh.vertices]
    evaluated.to_mesh_clear()
    return coords


scene = bpy.context.scene
armatures = [o for o in scene.objects if o.type == "ARMATURE"]
meshes = [o for o in scene.objects if o.type == "MESH"]
report = {
    "file": bpy.data.filepath,
    "scene": scene.name,
    "mode": bpy.context.mode,
    "objects": [{"name": o.name, "type": o.type, "parent": o.parent.name if o.parent else None} for o in scene.objects],
    "armatures": [],
    "meshes": [],
    "pose_tests": [],
}

for rig in armatures:
    report["armatures"].append({
        "name": rig.name,
        "bone_count": len(rig.data.bones),
        "bones": [{
            "name": b.name,
            "parent": b.parent.name if b.parent else None,
            "connected": b.use_connect,
            "head": [round(x, 5) for x in b.head_local],
            "tail": [round(x, 5) for x in b.tail_local],
            "length": round(b.length, 5),
        } for b in rig.data.bones],
    })

for obj in meshes:
    modifiers = [{"name": m.name, "type": m.type, "object": m.object.name if m.type == "ARMATURE" and m.object else None}
                 for m in obj.modifiers]
    group_names = [g.name for g in obj.vertex_groups]
    group_index = {g.index: g.name for g in obj.vertex_groups}
    weight_report = {}
    for rig in armatures:
        bone_names = {b.name for b in rig.data.bones}
        matching = bone_names.intersection(group_names)
        for bone_name in matching:
            total = 0.0
            affected = 0
            max_weight = 0.0
            weighted_z = []
            group = obj.vertex_groups.get(bone_name)
            for vert in obj.data.vertices:
                for assignment in vert.groups:
                    if assignment.group == group.index and assignment.weight > 0:
                        w = assignment.weight
                        total += w
                        affected += 1
                        max_weight = max(max_weight, w)
                        weighted_z.append((vert.co.z, w))
            if affected:
                weight_report[bone_name] = {
                    "vertex_count": affected,
                    "weight_sum": round(total, 4),
                    "max_weight": round(max_weight, 4),
                    "weighted_z_min": round(min(z for z, _ in weighted_z), 5),
                    "weighted_z_max": round(max(z for z, _ in weighted_z), 5),
                }
    report["meshes"].append({
        "name": obj.name,
        "vertices": len(obj.data.vertices),
        "edges": len(obj.data.edges),
        "groups": group_names,
        "modifiers": modifiers,
        "armature_weights": weight_report,
    })

# Non-destructive pose stress test in memory only. Restore all bone transforms before exit.
for rig in armatures:
    targets = [pb for pb in rig.pose.bones if any(token in pb.name.lower() for token in ("upperarm", "arm_upper", "forearm", "lowerarm"))]
    attached = [o for o in meshes if any(m.type == "ARMATURE" and m.object == rig for m in o.modifiers)]
    for mesh_obj in attached:
        saved = {pb.name: (pb.location.copy(), pb.rotation_mode, pb.rotation_euler.copy(), pb.rotation_quaternion.copy(), pb.scale.copy()) for pb in rig.pose.bones}
        for pb in rig.pose.bones:
            pb.location = (0.0, 0.0, 0.0)
            pb.rotation_mode = "QUATERNION"
            pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
            pb.scale = (1.0, 1.0, 1.0)
        bpy.context.view_layer.update()
        depsgraph = bpy.context.evaluated_depsgraph_get()
        baseline = edge_lengths(mesh_obj, depsgraph)
        base_coords = evaluated_coords(mesh_obj, depsgraph)
        for pb in targets:
            for axis in (0, 2):
                for degrees in (-90, 90):
                    pb.rotation_quaternion = Euler(tuple(math.radians(degrees) if i == axis else 0.0 for i in range(3)), "XYZ").to_quaternion()
                    bpy.context.view_layer.update()
                    depsgraph = bpy.context.evaluated_depsgraph_get()
                    lengths = edge_lengths(mesh_obj, depsgraph)
                    coords = evaluated_coords(mesh_obj, depsgraph)
                    meaningful_edges = [(old, new) for old, new in zip(baseline, lengths) if old > 0.005]
                    ratios = [new / old for old, new in meaningful_edges]
                    displacement = [(math.dist(a, b)) for a, b in zip(base_coords, coords)]
                    report["pose_tests"].append({
                        "rig": rig.name,
                        "mesh": mesh_obj.name,
                        "bone": pb.name,
                        "local_axis": "XYZ"[axis],
                        "degrees": degrees,
                        "meaningful_edges": len(ratios),
                        "excluded_near_zero_edges": len(baseline) - len(ratios),
                        "edge_ratio_p95": round(sorted(ratios)[int(0.95 * (len(ratios) - 1))], 4) if ratios else None,
                        "edge_ratio_p99": round(sorted(ratios)[int(0.99 * (len(ratios) - 1))], 4) if ratios else None,
                        "edge_ratio_max": round(max(ratios), 4) if ratios else None,
                        "edges_ratio_gt_2": sum(r > 2 for r in ratios),
                        "edges_ratio_gt_3": sum(r > 3 for r in ratios),
                        "max_vertex_displacement": round(max(displacement), 5) if displacement else None,
                    })
        for pb in rig.pose.bones:
            loc, mode, euler, quat, scale = saved[pb.name]
            pb.location = loc
            pb.rotation_mode = mode
            pb.rotation_euler = euler
            pb.rotation_quaternion = quat
            pb.scale = scale
        bpy.context.view_layer.update()

output_path = bpy.data.filepath.rsplit(".", 1)[0] + "_audit.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print("RIG_AUDIT_OUTPUT=" + output_path)
print(json.dumps({"file": report["file"], "objects": len(report["objects"]), "armatures": [(a["name"], a["bone_count"]) for a in report["armatures"]], "meshes": [(m["name"], m["vertices"], m["edges"]) for m in report["meshes"]], "pose_tests": len(report["pose_tests"])}, ensure_ascii=False))
