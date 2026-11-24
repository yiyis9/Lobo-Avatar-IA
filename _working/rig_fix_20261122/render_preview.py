import bpy
scene = bpy.context.scene
scene.render.resolution_x = 900
scene.render.resolution_y = 900
scene.render.resolution_percentage = 100
scene.render.filepath = r"C:\Users\irisg\Documents\LoboUPVT\_working\rig_fix_20261122\Lobo_nuevo_preview.png"
scene.render.image_settings.file_format = "PNG"
bpy.ops.render.render(write_still=True)
print("PREVIEW=" + scene.render.filepath)
