"""Build a fresh, proportioned Lobo mascot with a clean arm/wrist rig."""
from pathlib import Path
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
OUT_BLEND = ROOT / "lobo_upvt_nuevo.blend"
OUT_GLB = ROOT / "lobo_upvt_nuevo.glb"
PREVIEW = ROOT / "lobo_upvt_nuevo_saludo.png"

MATERIALS = {}
PARTS = []


def material(name, color, roughness=0.78):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Roughness"].default_value = roughness
    MATERIALS[name] = mat
    return mat


def finish_part(obj, name, mat, bone):
    obj.name = name
    obj.data.materials.append(mat)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    group = obj.vertex_groups.new(name=bone)
    if obj.data.vertices:
        group.add(list(range(len(obj.data.vertices))), 1.0, "REPLACE")
    PARTS.append(obj)
    return obj


def sphere(name, loc, scale, mat, bone, segments=16, rings=10):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, location=loc)
    obj = bpy.context.object
    obj.scale = scale
    bpy.ops.object.shade_smooth()
    return finish_part(obj, name, mat, bone)


def cylinder_between(name, start, end, radius_start, radius_end, mat, bone, sides=14):
    start, end = Vector(start), Vector(end)
    delta = end - start
    bpy.ops.mesh.primitive_cone_add(
        vertices=sides, radius1=radius_start, radius2=radius_end,
        depth=delta.length, location=(start + end) / 2,
    )
    obj = bpy.context.object
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(delta.normalized())
    bpy.ops.object.shade_smooth()
    return finish_part(obj, name, mat, bone)


def add_bone(edit_bones, name, head, tail, parent=None, front_roll=False, deform=True):
    bone = edit_bones.new(name)
    bone.head, bone.tail = head, tail
    bone.use_deform = deform
    if parent:
        bone.parent = edit_bones[parent]
    if front_roll:
        # Orient the local Z axis toward the character's front. Rotating it
        # raises an arm in the body plane and swings the wrist side to side.
        bone.align_roll(Vector((0, -1, 0)))
    return bone


def key_action(rig, scene, name, frames):
    action = bpy.data.actions.new(name)
    action.use_fake_user = True
    rig.animation_data.action = action
    for frame, changes in frames:
        scene.frame_set(frame)
        for pose_bone in rig.pose.bones:
            pose_bone.rotation_mode = "XYZ"
            pose_bone.rotation_euler = changes.get(pose_bone.name, (0, 0, 0))
            pose_bone.keyframe_insert(
                data_path="rotation_euler", frame=frame, group=pose_bone.name
            )
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for curve in bag.fcurves:
                    for point in curve.keyframe_points:
                        point.interpolation = "BEZIER"
                        point.handle_left_type = "AUTO_CLAMPED"
                        point.handle_right_type = "AUTO_CLAMPED"
    return action


def main():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    MATERIALS.clear()
    PARTS.clear()

    fur = material("Marfil · pelaje", (.86, .84, .82))
    fur_light = material("Crema · hocico", (.97, .95, .91))
    fur_shadow = material("Gris · marcas", (.47, .49, .51))
    inner_ear = material("Rosa · orejas", (.62, .31, .36))
    burgundy = material("Guinda · chamarra", (.15, .018, .035))
    burgundy_light = material("Ribete claro", (.83, .77, .74))
    shirt = material("Blanco · camiseta", (.96, .94, .90))
    pants = material("Gris · pantalón", (.39, .42, .45))
    pants_light = material("Costuras", (.60, .61, .61))
    black = material("Negro · ojos y nariz", (.025, .03, .035), .32)
    paw_pad = material("Almohadillas", (.17, .18, .19), .88)
    metal = material("Broches", (.68, .67, .62), .3)

    # Rest skeleton is built in the relaxed standing pose, not in a T pose.
    arm_data = bpy.data.armatures.new("Lobo nuevo · esqueleto")
    rig = bpy.data.objects.new("Lobo_UPVT_Rig", arm_data)
    bpy.context.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm_data.edit_bones
    add_bone(eb, "root", (0, 0, .04), (0, 0, .18), deform=False)
    add_bone(eb, "hips", (0, 0, .76), (0, 0, .94), "root")
    add_bone(eb, "spine", (0, 0, .94), (0, 0, 1.12), "hips", True)
    add_bone(eb, "chest", (0, 0, 1.12), (0, 0, 1.32), "spine", True)
    add_bone(eb, "neck", (0, 0, 1.32), (0, 0, 1.43), "chest", True)
    add_bone(eb, "head", (0, 0, 1.43), (0, 0, 1.72), "neck", True)

    arm_rest = {}
    for sign, side in ((1, "L"), (-1, "R")):
        clavicle_head = (sign * .16, 0, 1.27)
        shoulder = (sign * .25, 0, 1.25)
        elbow = (sign * .34, 0, 1.00)
        wrist = (sign * .39, -.005, .80)
        palm_end = (sign * .395, -.015, .69)
        add_bone(eb, f"clavicle.{side}", clavicle_head, shoulder, "chest", True)
        add_bone(eb, f"upper_arm.{side}", shoulder, elbow, f"clavicle.{side}", True)
        add_bone(eb, f"forearm.{side}", elbow, wrist, f"upper_arm.{side}", True)
        add_bone(eb, f"hand.{side}", wrist, palm_end, f"forearm.{side}", True)
        arm_rest[side] = (shoulder, elbow, wrist, palm_end)

    for sign, side in ((1, "L"), (-1, "R")):
        hip = (sign * .125, 0, .88)
        knee = (sign * .135, -.005, .50)
        ankle = (sign * .13, -.01, .16)
        toe = (sign * .13, -.13, .055)
        add_bone(eb, f"thigh.{side}", hip, knee, "hips")
        add_bone(eb, f"shin.{side}", knee, ankle, f"thigh.{side}", True)
        add_bone(eb, f"foot.{side}", ankle, toe, f"shin.{side}", True)

    add_bone(eb, "tail_1", (0, .12, .78), (-.12, .24, .72), "hips", True)
    add_bone(eb, "tail_2", (-.12, .24, .72), (-.27, .31, .64), "tail_1", True)
    add_bone(eb, "tail_3", (-.27, .31, .64), (-.42, .36, .59), "tail_2", True)
    bpy.ops.object.mode_set(mode="OBJECT")
    rig.show_in_front = True

    # Jacket torso and the open front panels.
    sphere("Chamarra", (0, 0, 1.10), (.285, .17, .325), burgundy, "chest", 20, 14)
    sphere("Camiseta", (0, -.153, 1.105), (.155, .028, .265), shirt, "chest", 16, 12)
    for sign, side in ((1, "L"), (-1, "R")):
        sphere(f"Solapa {side}", (sign * .105, -.171, 1.12), (.135, .028, .25), burgundy, "chest")
        for z in (1.29, 1.18, 1.07, .96):
            sphere(f"Broche {side} {z}", (sign * .19, -.20, z), (.012, .008, .012), metal, "chest", 10, 6)
        # Shoulder pads and continuous-looking sleeve sections overlap at the elbow.
        shoulder, elbow, wrist, palm_end = arm_rest[side]
        sphere(f"Hombro {side}", shoulder, (.112, .12, .115), burgundy, f"upper_arm.{side}")
        cylinder_between(f"Manga superior {side}", shoulder, elbow, .104, .089, fur, f"upper_arm.{side}")
        sphere(f"Codo {side}", elbow, (.091, .09, .09), fur, f"forearm.{side}")
        cylinder_between(f"Manga inferior {side}", elbow, wrist, .087, .071, fur, f"forearm.{side}")

        # Wrist joint is buried inside a cuff that stays with the forearm.
        cuff_end = Vector(wrist) + (Vector(palm_end) - Vector(wrist)).normalized() * .065
        cylinder_between(f"Puño guinda {side}", Vector(wrist) - (Vector(palm_end) - Vector(wrist)).normalized() * .012,
                         cuff_end, .076, .074, burgundy, f"forearm.{side}")
        cuff_stripe_start = Vector(wrist) + (Vector(palm_end) - Vector(wrist)).normalized() * .035
        cuff_stripe_end = cuff_stripe_start + (Vector(palm_end) - Vector(wrist)).normalized() * .014
        cylinder_between(f"Raya del puño {side}", cuff_stripe_start, cuff_stripe_end,
                         .077, .077, burgundy_light, f"forearm.{side}")

        # Palm starts inside the cuff; fingers and pads share the hand bone.
        palm_center = Vector(wrist) + (Vector(palm_end) - Vector(wrist)).normalized() * .073
        sphere(f"Palma {side}", palm_center, (.071, .052, .074), fur_light, f"hand.{side}")
        for digit, offset in enumerate((-.041, 0, .041)):
            sphere(f"Dedo {digit+1} {side}", (sign*.395 + offset, -.018, .648),
                   (.023, .031, .047), fur_light, f"hand.{side}", 12, 8)
        sphere(f"Pulgar {side}", (sign*.452, -.025, .705), (.032, .031, .045), fur_light, f"hand.{side}", 12, 8)
        for pad, offset in enumerate((-.035, 0, .035)):
            sphere(f"Almohadilla {pad+1} {side}", (sign*.395 + offset, -.065, .654),
                   (.013, .007, .018), paw_pad, f"hand.{side}", 10, 6)

    # Collar, waistband, and jacket details.
    for sign, side in ((1, "L"), (-1, "R")):
        sphere(f"Cuello de chamarra {side}", (sign*.085, -.11, 1.365), (.10, .055, .045), burgundy_light, "chest")
        sphere(f"Bolsillo {side}", (sign*.19, -.181, .93), (.07, .018, .055), burgundy, "chest")
    cylinder_between("Ribete inferior", (-.21, -.13, .84), (.21, -.13, .84), .012, .012, burgundy_light, "chest")

    # Hips, separated legs, cargo pockets, and paw-shaped shoes.
    sphere("Cadera del pantalón", (0, .005, .78), (.245, .155, .17), pants, "hips")
    for sign, side in ((1, "L"), (-1, "R")):
        sphere(f"Muslo {side}", (sign*.125, 0, .62), (.12, .135, .235), pants, f"thigh.{side}")
        sphere(f"Rodilla {side}", (sign*.135, -.002, .49), (.103, .12, .10), pants, f"shin.{side}")
        cylinder_between(f"Pantalón inferior {side}", (sign*.135, -.003, .49), (sign*.13, -.012, .16),
                         .092, .078, pants, f"shin.{side}")
        sphere(f"Bota {side}", (sign*.13, -.085, .105), (.12, .205, .09), fur_light, f"foot.{side}")
        for toe, offset in enumerate((-.052, 0, .052)):
            sphere(f"Dedos de bota {toe} {side}", (sign*.13+offset, -.222, .11),
                   (.035, .055, .045), fur, f"foot.{side}", 12, 8)
        sphere(f"Bolsillo cargo {side}", (sign*.22, -.123, .59), (.055, .018, .075), pants_light, f"thigh.{side}")
        cylinder_between(f"Costura pantalón {side}", (sign*.125, -.12, .73), (sign*.13, -.10, .26),
                         .004, .004, pants_light, f"thigh.{side}", 8)

    # Wolf head, tall ears, muzzle, brows, and a clear face silhouette.
    sphere("Cabeza", (0, 0, 1.56), (.19, .145, .195), fur, "head", 20, 14)
    for sign, side in ((1, "L"), (-1, "R")):
        bpy.ops.mesh.primitive_cone_add(vertices=16, radius1=.075, radius2=.002,
                                        depth=.25, location=(sign*.125, .006, 1.79))
        ear = bpy.context.object
        bpy.ops.object.shade_smooth()
        finish_part(ear, f"Oreja puntiaguda {side}", fur, "head")
        bpy.ops.mesh.primitive_cone_add(vertices=16, radius1=.039, radius2=.001,
                                        depth=.145, location=(sign*.125, -.055, 1.79))
        inner = bpy.context.object
        bpy.ops.object.shade_smooth()
        finish_part(inner, f"Interior oreja {side}", inner_ear, "head")
        sphere(f"Ojo {side}", (sign*.071, -.135, 1.59), (.025, .021, .043), black, "head", 12, 8)
        sphere(f"Ceja {side}", (sign*.073, -.137, 1.646), (.048, .019, .014), fur_shadow, "head", 12, 8)
        sphere(f"Mejilla {side}", (sign*.105, -.116, 1.51), (.071, .045, .048), fur_light, "head")
    sphere("Hocico", (0, -.154, 1.515), (.087, .067, .057), fur_light, "head")
    sphere("Nariz", (0, -.213, 1.535), (.035, .024, .026), black, "head", 12, 8)
    sphere("Flequillo", (0, -.055, 1.69), (.115, .09, .075), fur_shadow, "head")

    # Tail is three overlapping, separately weighted fluffy sections.
    sphere("Cola base", (-.10, .22, .72), (.16, .135, .13), fur_shadow, "tail_1")
    sphere("Cola media", (-.25, .31, .65), (.18, .13, .14), fur, "tail_2")
    sphere("Cola punta", (-.405, .36, .59), (.18, .12, .12), fur_light, "tail_3")

    # Join all pieces into one skinned mesh. Cuffs cover the wrist boundary;
    # the palm and digits are one hand group, so they rotate together without gaps.
    bpy.ops.object.select_all(action="DESELECT")
    for obj in PARTS:
        obj.select_set(True)
    model = PARTS[0]
    bpy.context.view_layer.objects.active = model
    bpy.ops.object.join()
    model.name = "Lobo_UPVT_Modelo"
    model.data.name = "Lobo_UPVT_Malla_Nueva"
    modifier = model.modifiers.new("Rig corporal nuevo", "ARMATURE")
    modifier.object = rig
    modifier.use_deform_preserve_volume = True
    model.parent = rig

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x, scene.render.resolution_y = 720, 900
    scene.render.resolution_percentage = 60
    scene.eevee.taa_render_samples = 8
    scene.world.color = (.12, .13, .14)
    cam_data = bpy.data.cameras.new("Cámara de presentación")
    camera = bpy.data.objects.new("Cámara de presentación", cam_data)
    scene.collection.objects.link(camera)
    camera.location = (0, -3.5, 1.02)
    camera.rotation_euler = (Vector((0, 0, .92)) - camera.location).to_track_quat("-Z", "Y").to_euler()
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 2.02
    scene.camera = camera
    light_data = bpy.data.lights.new("Luz suave", "AREA")
    light = bpy.data.objects.new("Luz suave", light_data)
    scene.collection.objects.link(light)
    light.location = (-1.3, -2.1, 2.7)
    light_data.energy, light_data.size = 260, 2.4
    light.rotation_euler = (Vector((0, 0, .9)) - light.location).to_track_quat("-Z", "Y").to_euler()

    scene.render.image_settings.file_format = "PNG"
    rig.animation_data_create()
    zero = {}
    key_action(rig, scene, "Idle", [(1, zero), (2, zero)])
    key_action(rig, scene, "Hablar", [
        (1, zero),
        (8, {"head": (.025, 0, 0), "chest": (.012, 0, 0), "upper_arm.L": (0, 0, .08)}),
        (16, zero),
        (24, {"head": (-.02, 0, 0), "chest": (-.01, 0, 0), "upper_arm.L": (0, 0, .06)}),
        (32, zero),
    ])
    key_action(rig, scene, "Pensar", [
        (1, zero),
        (8, {"head": (0, .08, 0), "upper_arm.L": (0, 0, .62), "forearm.L": (0, 0, .78)}),
        (20, {"head": (0, .08, 0), "upper_arm.L": (0, 0, .62), "forearm.L": (0, 0, .78)}),
        (28, zero),
    ])
    salute_frames = [
        (1, zero),
        (4, {"upper_arm.L": (0, 0, .35), "forearm.L": (0, 0, .2)}),
        (8, {"upper_arm.L": (0, 0, 1.45), "forearm.L": (0, 0, 2.35)}),
        (12, {"upper_arm.L": (0, 0, 1.45), "forearm.L": (0, 0, 2.35), "hand.L": (0, 0, .45)}),
        (16, {"upper_arm.L": (0, 0, 1.45), "forearm.L": (0, 0, 2.35), "hand.L": (0, 0, -.45)}),
        (20, {"upper_arm.L": (0, 0, 1.45), "forearm.L": (0, 0, 2.35), "hand.L": (0, 0, .45)}),
        (24, {"upper_arm.L": (0, 0, 1.45), "forearm.L": (0, 0, 2.35), "hand.L": (0, 0, -.45)}),
        (28, {"upper_arm.L": (0, 0, 1.45), "forearm.L": (0, 0, 2.35), "hand.L": (0, 0, .45)}),
        (32, {"upper_arm.L": (0, 0, 1.45), "forearm.L": (0, 0, 2.35)}),
        (42, zero),
    ]
    key_action(rig, scene, "Saludo", salute_frames)
    key_action(rig, scene, "Celebrar", [
        (1, zero),
        (8, {"upper_arm.L": (0, 0, .62), "forearm.L": (0, 0, .45),
             "upper_arm.R": (0, 0, -.62), "forearm.R": (0, 0, -.45), "chest": (.02, 0, 0)}),
        (20, {"upper_arm.L": (0, 0, .62), "forearm.L": (0, 0, .45),
              "upper_arm.R": (0, 0, -.62), "forearm.R": (0, 0, -.45)}),
        (30, zero),
    ])

    scene.frame_end = 42
    scene.frame_set(1)
    rig.animation_data.action = bpy.data.actions["Idle"]
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.object.select_all(action="DESELECT")
    rig.select_set(True)
    model.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT_BLEND))

    rig.animation_data.action = bpy.data.actions["Saludo"]
    scene.frame_set(20)
    scene.render.filepath = str(PREVIEW)
    bpy.ops.render.render(write_still=True)
    scene.frame_set(1)
    rig.animation_data.action = bpy.data.actions["Idle"]
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT_BLEND))

    bpy.ops.object.select_all(action="DESELECT")
    rig.select_set(True)
    model.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.export_scene.gltf(
        filepath=str(OUT_GLB), export_format="GLB", use_selection=True,
        export_animations=True, export_animation_mode="ACTIONS",
        export_nla_strips=False, export_force_sampling=True,
    )
    print("NEW_RIG", [(bone.name, tuple(round(v, 3) for v in bone.head_local),
                       tuple(round(v, 3) for v in bone.tail_local)) for bone in arm_data.bones])
    print("NEW_CLIPS", sorted(a.name for a in bpy.data.actions if a.name in
                               {"Idle", "Hablar", "Pensar", "Saludo", "Celebrar"}))
    print("GLB", OUT_GLB)


if __name__ == "__main__":
    main()
