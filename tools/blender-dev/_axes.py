import bpy
bpy.ops.wm.open_mainfile(filepath=r'C:\Users\irisg\Documents\LoboUPVT\ahora_si_lobo_articulado.blend')
a=bpy.data.objects['Lobo_UPVT_Rig'].data
for n in ['upper_arm.L','forearm.L','hand.L']:
 b=a.bones[n]; print(n,'X',tuple(round(x,2) for x in b.matrix_local.to_3x3().col[0]),'Y',tuple(round(x,2) for x in b.matrix_local.to_3x3().col[1]),'Z',tuple(round(x,2) for x in b.matrix_local.to_3x3().col[2]))

