"""Separate the existing weighted hand islands into independently editable meshes."""

from pathlib import Path
import os
import runpy

import bmesh
import bpy


ROOT = Path(__file__).resolve().parents[1]
BLEND_OUTPUT = ROOT / "lobito art - manos movibles.blend"
GLB_STAGING = ROOT / "backend" / "static" / "kiosk" / "models" / "lobo-upvt-hands-movable.glb"

model = bpy.data.objects.get("LoboUrbano_Modelo")
armature = bpy.data.objects.get("LoboUrbano_Rig")
if model is None or armature is None or model.type != "MESH":
    raise RuntimeError("No se encontraron la malla y el rig originales del Lobo.")

group_names = {group.index: group.name for group in model.vertex_groups}
original_mesh = model.data.copy()
original_face_indices = set(range(len(original_mesh.polygons)))
source_bmesh = bmesh.new()
source_bmesh.from_mesh(original_mesh)
source_bmesh.faces.ensure_lookup_table()
source_bmesh.faces.index_update()
remaining = set(source_bmesh.faces)
hand_faces: dict[str, set[int]] = {"L": set(), "R": set()}

while remaining:
    first = remaining.pop()
    stack = [first]
    island = [first]
    while stack:
        face = stack.pop()
        for edge in face.edges:
            for neighbor in edge.link_faces:
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    stack.append(neighbor)
                    island.append(neighbor)

    vertices = {vertex for face in island for vertex in face.verts}
    if not vertices:
        continue
    center_x = sum(vertex.co.x for vertex in vertices) / len(vertices)
    center_y = sum(vertex.co.y for vertex in vertices) / len(vertices)
    center_z = sum(vertex.co.z for vertex in vertices) / len(vertices)
    if not (0.20 < abs(center_x) < 0.42 and -0.23 < center_y < 0.34 and 0.56 < center_z < 0.79):
        continue

    side = "L" if center_x > 0 else "R"
    hand_group = f"hand.{side}"
    total_weight = 0.0
    for vertex in vertices:
        for assignment in model.data.vertices[vertex.index].groups:
            if group_names.get(assignment.group) == hand_group:
                total_weight += assignment.weight
    average_hand_weight = total_weight / len(vertices)
    if average_hand_weight >= 0.45:
        hand_faces[side].update(face.index for face in island)

source_bmesh.free()
if not hand_faces["L"] or not hand_faces["R"]:
    raise RuntimeError("No se identificaron las dos mallas de las manos; no se modificó el modelo.")

all_hand_faces = hand_faces["L"] | hand_faces["R"]


def mesh_without_faces(source_mesh, excluded_face_indices, name):
    mesh = source_mesh.copy()
    mesh.name = name
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()
    bm.faces.index_update()
    to_remove = [face for face in bm.faces if face.index in excluded_face_indices]
    bmesh.ops.delete(bm, geom=to_remove, context="FACES")
    loose_vertices = [vertex for vertex in bm.verts if not vertex.link_faces]
    if loose_vertices:
        bmesh.ops.delete(bm, geom=loose_vertices, context="VERTS")
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return mesh


collection = model.users_collection[0] if model.users_collection else bpy.context.scene.collection
model.data = mesh_without_faces(original_mesh, all_hand_faces, "Lobo_Cuerpo_con_manos_separadas")
model.name = "LoboUrbano_Modelo"

for side, label in (("L", "Izquierda"), ("R", "Derecha")):
    bone_group_name = f"hand.{side}"
    hand_obj = model.copy()
    # Build each hand from the untouched mesh snapshot retained before the body split.
    hand_mesh = mesh_without_faces(original_mesh, set(original_face_indices) - hand_faces[side], f"Lobo_Mano_{label}")
    hand_obj.data = hand_mesh
    hand_obj.name = f"Lobo_Mano_{label}"
    hand_obj["parte_avatar"] = f"Mano {label.lower()} del Lobo UPVT"
    # Keep the hand at the natural wrist seam; the separate mesh and bone weight
    # provide articulation without translating the paw away from the sleeve.
    hand_bone = armature.data.bones.get(bone_group_name)
    if hand_bone is None:
        raise RuntimeError(f"No se encontró el hueso {bone_group_name!r}.")

    # Preserve the source's blended wrist weights so the paw follows the arm
    # smoothly when the IK chain bends instead of shearing at the cuff.
    hand_obj.data.update()
    collection.objects.link(hand_obj)

bpy.data.meshes.remove(original_mesh)
os.environ["LOBO_BLEND_OUTPUT"] = str(BLEND_OUTPUT)
os.environ["LOBO_GLB_OUTPUT"] = str(GLB_STAGING)
runpy.run_path(str(ROOT / "tools" / "build_lobo_animation_assets.py"))

print("MANOS_SEPARADAS", {side: len(indices) for side, indices in hand_faces.items()})
print("OBJETOS", [obj.name for obj in bpy.context.scene.objects if obj.type == "MESH"])
print("ANIMACIONES", [action.name for action in bpy.data.actions if action.name in {"Idle", "Saludo", "Hablar", "Pensar", "Celebrar"}])
print("GLB_PREPARADO", GLB_STAGING)
