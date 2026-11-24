import bpy
bpy.ops.wm.open_mainfile(filepath=r'C:\Users\irisg\Documents\LoboUPVT\lobo_upvt_nuevo.blend')
r=bpy.data.objects['Lobo_UPVT_Rig']; r.animation_data.action=bpy.data.actions['Saludo']
for f in [1,8,12,16,20,42]:
 bpy.context.scene.frame_set(f); print('F',f)
 for n in ['upper_arm.L','forearm.L','hand.L']:
  p=r.pose.bones[n];print(n,tuple(round(x,3) for x in p.head),tuple(round(x,3) for x in p.tail))
