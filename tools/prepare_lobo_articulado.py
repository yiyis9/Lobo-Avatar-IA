"""Create a clean, weight-painted rigged copy of the provided Lobo GLB."""
from pathlib import Path
import bpy
from mathutils import Vector

SOURCE = Path(r"C:\Users\irisg\Downloads\ahora si lobo.glb")
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "ahora_si_lobo_articulado_v2.blend"
EXPORT = ROOT / "ahora_si_lobo_articulado_v2.glb"
PREVIEW = ROOT / "ahora_si_lobo_articulado_v2_preview.png"


def add_bone(eb, name, head, tail, parent=None, connected=False, deform=True):
    item = eb.new(name)
    item.head, item.tail, item.use_deform = head, tail, deform
    if parent:
        item.parent = parent
        item.use_connect = connected
    return item


def segment_distance(point, start, end):
    direction = end - start
    length2 = direction.length_squared
    t = max(0.0, min(1.0, (point - start).dot(direction) / length2)) if length2 else 0.0
    return (point - (start + direction * t)).length


def main():
    if not SOURCE.is_file():
        raise FileNotFoundError(SOURCE)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=str(SOURCE))
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if len(meshes) != 1:
        raise RuntimeError(f"Esperaba una malla del GLB, recibí {len(meshes)}")
    model = meshes[0]
    model.name = "Lobo_UPVT_Modelo"
    model.data.name = "Lobo_UPVT_Malla"

    arm_data = bpy.data.armatures.new("Lobo_UPVT_Esqueleto")
    rig = bpy.data.objects.new("Lobo_UPVT_Rig", arm_data)
    bpy.context.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm_data.edit_bones

    root = add_bone(eb, "root", (0, 0, -.305), (0, 0, -.245), deform=False)
    hips = add_bone(eb, "hips", (0, 0, -.205), (0, 0, -.125), root)
    spine = add_bone(eb, "spine", (0, 0, -.125), (0, 0, -.025), hips)
    chest = add_bone(eb, "chest", (0, 0, -.025), (0, 0, .080), spine, connected=True)
    neck = add_bone(eb, "neck", (0, 0, .080), (0, 0, .150), chest, connected=True)
    add_bone(eb, "head", (0, 0, .150), (0, 0, .305), neck, connected=True)

    for sign, side in ((1, "L"), (-1, "R")):
        clavicle = add_bone(eb, f"clavicle.{side}", (0, 0, .055), (sign*.085, 0, .095), chest)
        upper = add_bone(eb, f"upper_arm.{side}", (sign*.085, 0, .095), (sign*.165, 0, .095), clavicle, connected=True)
        fore = add_bone(eb, f"forearm.{side}", (sign*.165, 0, .095), (sign*.245, 0, .095), upper, connected=True)
        add_bone(eb, f"hand.{side}", (sign*.245, 0, .095), (sign*.305, -.005, .095), fore, connected=True)

    for sign, side in ((1, "L"), (-1, "R")):
        thigh = add_bone(eb, f"thigh.{side}", (sign*.045, 0, -.125), (sign*.052, 0, -.220), hips)
        shin = add_bone(eb, f"shin.{side}", (sign*.052, 0, -.220), (sign*.060, 0, -.285), thigh, connected=True)
        foot = add_bone(eb, f"foot.{side}", (sign*.060, 0, -.285), (sign*.060, -.105, -.295), shin, connected=True)
        add_bone(eb, f"toe.{side}", (sign*.060, -.105, -.295), (sign*.060, -.140, -.295), foot, connected=True)

    # The source has a large side-swept tail. Its own chain prevents it from being pulled by a leg.
    tail1 = add_bone(eb, "tail_1", (-.015, .035, -.145), (-.075, .045, -.165), hips)
    tail2 = add_bone(eb, "tail_2", (-.075, .045, -.165), (-.145, .050, -.185), tail1, connected=True)
    tail3 = add_bone(eb, "tail_3", (-.145, .050, -.185), (-.220, .050, -.205), tail2, connected=True)
    add_bone(eb, "tail_4", (-.220, .050, -.205), (-.300, .050, -.220), tail3, connected=True)
    bpy.ops.object.mode_set(mode="OBJECT")
    rig.show_in_front = True
    rig.data.display_type = "OCTAHEDRAL"

    # Keep the chest/jacket weighted to the torso; only the pale outer sleeves follow the arms.
    image = next((n.image for mat in model.data.materials if mat and mat.use_nodes
                  for n in mat.node_tree.nodes if n.type == "TEX_IMAGE" and n.image), None)
    uv_layer = model.data.uv_layers.active
    color_samples = [[] for _ in model.data.vertices]
    if image and uv_layer:
        width, height = image.size[:]
        pixels = image.pixels[:]
        for polygon in model.data.polygons:
            for loop_index in polygon.loop_indices:
                uv = uv_layer.data[loop_index].uv
                x = max(0, min(width-1, int(uv.x * width)))
                y = max(0, min(height-1, int(uv.y * height)))
                offset = (y * width + x) * 4
                color_samples[model.data.loops[loop_index].vertex_index].append(tuple(pixels[offset:offset+3]))

    deform_bones = [b for b in arm_data.bones if b.use_deform]
    groups = {b.name: model.vertex_groups.new(name=b.name) for b in deform_bones}
    indices_by_group = {name: [] for name in groups}
    weights_by_group = {name: [] for name in groups}

    def choose_candidates(point, rgb):
        x, y, z = point
        side = "L" if x >= 0 else "R"
        red_jacket = bool(rgb and rgb[0] > rgb[1]*1.22 and rgb[0] > rgb[2]*1.18 and rgb[0] > .025)
        # Jacket/body vertices around the shoulder must remain on the chest even when red/white edges meet.
        if .015 <= z <= .155 and abs(x) < .155 and (red_jacket or abs(x) < .115):
            names = ["spine", "chest", "clavicle." + side]
        elif .015 <= z <= .16 and abs(x) >= .115:
            ax = abs(x)
            names = (["clavicle."+side, "upper_arm."+side, "forearm."+side] if ax < .205
                     else ["upper_arm."+side, "forearm."+side, "hand."+side] if ax < .260
                     else ["forearm."+side, "hand."+side])
        elif z > .135:
            names = ["neck", "head"]
        elif z < -.12 and x < -.14 and z > -.285:
            names = ["tail_1", "tail_2", "tail_3", "tail_4"]
        elif z < -.105:
            names = ["hips", "thigh."+side, "shin."+side, "foot."+side, "toe."+side]
        else:
            names = ["hips", "spine", "chest", "neck"]
        return [arm_data.bones[name] for name in names if name in arm_data.bones]

    for vertex in model.data.vertices:
        point = model.matrix_world @ vertex.co
        samples = color_samples[vertex.index]
        rgb = tuple(sum(c[i] for c in samples) / len(samples) for i in range(3)) if samples else None
        candidates = choose_candidates(point, rgb)
        ranked = sorted((segment_distance(point, b.head_local, b.tail_local), b.name) for b in candidates)[:2]
        influence = [(name, 1.0 / ((distance + .024) ** 3)) for distance, name in ranked]
        total = sum(weight for _, weight in influence) or 1.0
        for name, weight in influence:
            indices_by_group[name].append(vertex.index)
            weights_by_group[name].append(weight / total)
    for name, group in groups.items():
        for vertex_index, weight in zip(indices_by_group[name], weights_by_group[name]):
            group.add([vertex_index], weight, "REPLACE")
    modifier = model.modifiers.new("Esqueleto Lobo UPVT", "ARMATURE")
    modifier.object = rig
    modifier.use_deform_preserve_volume = True
    model.parent = rig

    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                area.spaces.active.region_3d.view_distance = 1.25
                area.spaces.active.region_3d.view_location = (0, 0, 0)
                area.spaces.active.shading.type = "MATERIAL"

    notes = bpy.data.texts.new("LEEME - Lobo articulado")
    notes.write("LOBO UPVT - MODELO ARTICULADO\n\nModelo y textura originales conservados. Rig centrado sobre cráneo, hombros, codos, cadera, rodillas, tobillos y cola.\nSelecciona Lobo_UPVT_Rig y usa Pose Mode (Ctrl+Tab). Para saludar, rota upper_arm.L y forearm.L sobre su eje local X para elevar y flexionar el brazo, y hand.L sobre su eje local Y para oscilar la mano de lado a lado.\nLas mangas siguen los huesos del brazo y el torso de la chamarra permanece ponderado al pecho para reducir estiramientos.\nEl GLB de kiosko se exporta después de validar aquí. Archivo original en Descargas intacto.\n")

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x, scene.render.resolution_y = 900, 1000
    scene.render.resolution_percentage = 100
    scene.world.color = (.08, .08, .08)
    camera_data = bpy.data.cameras.new("Preview Camera")
    camera = bpy.data.objects.new("Preview Camera", camera_data)
    scene.collection.objects.link(camera)
    camera.location = (0, -1.65, .08)
    camera.rotation_euler = (Vector((0, 0, 0)) - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = 1.08
    scene.camera = camera
    light_data = bpy.data.lights.new("Preview Light", "AREA")
    light = bpy.data.objects.new("Preview Light", light_data)
    scene.collection.objects.link(light)
    light.location = (-.65, -1.0, 1.0)
    light_data.energy, light_data.size = 180, 1.1
    light.rotation_euler = (Vector((0, 0, 0)) - light.location).to_track_quat("-Z", "Y").to_euler()
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(PREVIEW)
    bpy.ops.render.render(write_still=True)

    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.object.select_all(action="DESELECT")
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT))
    bpy.ops.object.select_all(action="DESELECT")
    model.select_set(True)
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.export_scene.gltf(filepath=str(EXPORT), export_format="GLB", use_selection=True, export_animations=False)
    print(f"DONE bones={len(arm_data.bones)} groups={len(model.vertex_groups)} vertices={len(model.data.vertices)}")


if __name__ == "__main__":
    main()
