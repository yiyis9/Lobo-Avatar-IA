import bpy
from pathlib import Path
root=Path(r'C:\Users\irisg\Documents\LoboUPVT')
bpy.ops.wm.open_mainfile(filepath=str(root/'lobo_referencia_rig.blend'))
rig=bpy.data.objects['Lobo_UPVT_Rig'];sc=bpy.context.scene;rig.animation_data.action=bpy.data.actions['Saludo']
sc.render.resolution_percentage=35;sc.eevee.taa_render_samples=4
for f in (18,22):
 sc.frame_set(f);sc.render.filepath=str(root/f'hand_pose_{f}.png');bpy.ops.render.render(write_still=True)
