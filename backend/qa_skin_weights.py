import bpy
from pathlib import Path

path = Path(__file__).parent / "static/kiosk/models/lobo-upvt-rigged.glb"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(path))
mesh = next(obj for obj in bpy.context.scene.objects if obj.type == "MESH" and obj.name == "Lobo_UPVT_Modelo")
arm = next(obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE")
print("MESH", mesh.name, "vertices", len(mesh.data.vertices), "groups", len(mesh.vertex_groups), "arm_mods", [(m.name, m.object.name if m.object else None) for m in mesh.modifiers if m.type == "ARMATURE"])
for name in ("clavicle.L", "upper_arm.L", "forearm.L", "hand.L", "clavicle.R", "upper_arm.R", "forearm.R", "hand.R"):
    group = mesh.vertex_groups.get(name)
    bone = arm.data.bones.get(name)
    weighted = []
    if group:
        for vertex in mesh.data.vertices:
            try:
                weight = group.weight(vertex.index)
            except RuntimeError:
                continue
            if weight > 0.25:
                weighted.append(vertex.co.copy())
    if weighted:
        mins = tuple(round(min(v[i] for v in weighted), 3) for i in range(3))
        maxs = tuple(round(max(v[i] for v in weighted), 3) for i in range(3))
    else:
        mins = maxs = None
    print("BONE", name, "rest", tuple(round(v, 3) for v in bone.head_local), tuple(round(v, 3) for v in bone.tail_local), "weighted_vertices", len(weighted), "bounds", mins, maxs)

edges = mesh.data.edges
adj = [[] for _ in mesh.data.vertices]
for edge in edges:
    a, b = edge.vertices
    adj[a].append(b)
    adj[b].append(a)
seen = set()
components = []
for start in range(len(adj)):
    if start in seen:
        continue
    stack = [start]
    seen.add(start)
    comp = []
    while stack:
        current = stack.pop()
        comp.append(current)
        for nxt in adj[current]:
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    components.append(comp)
components.sort(key=len, reverse=True)
print("COMPONENTS", len(components), [len(c) for c in components[:20]])
