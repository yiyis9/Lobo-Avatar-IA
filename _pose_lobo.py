import bpy
from pathlib import Path
p=Path(r'C:\Users\irisg\Documents\LoboUPVT\lobo_upvt_nuevo.blend')
bpy.ops.wm.open_mainfile(filepath=str(p))
rig=bpy.data.objects['Lobo_UPVT_Rig']; scene=bpy.context.scene
act=bpy.data.actions['Saludo']; rig.animation_data.action=act
for f, upper, fore, wrist in [(1,0,0,0),(4,.35,.2,0),(8,1.05,1.75,0),(12,1.05,1.75,.45),(16,1.05,1.75,-.45),(20,1.05,1.75,.45),(24,1.05,1.75,-.45),(28,1.05,1.75,.45),(32,1.05,1.75,0),(42,0,0,0)]:
 scene.frame_set(f)
 for n,v in [('upper_arm.L',upper),('forearm.L',fore),('hand.L',wrist)]:
  pb=rig.pose.bones[n]; pb.rotation_mode='XYZ'; pb.rotation_euler=(0,0,v); pb.keyframe_insert(data_path='rotation_euler',frame=f,group=n)
for layer in act.layers:
 for strip in layer.strips:
  for bag in strip.channelbags:
   for fc in bag.fcurves:
    for kp in fc.keyframe_points: kp.interpolation='BEZIER';kp.handle_left_type='AUTO_CLAMPED';kp.handle_right_type='AUTO_CLAMPED'
scene.frame_set(20)
for n in ['upper_arm.L','forearm.L','hand.L']:
 pb=rig.pose.bones[n]; print(n,tuple(round(x,3) for x in pb.head),tuple(round(x,3) for x in pb.tail))
scene.render.filepath=str(p.parent/'lobo_upvt_nuevo_saludo_v2.png')
bpy.ops.render.render(write_still=True)
scene.frame_set(1);rig.animation_data.action=bpy.data.actions['Idle'];bpy.ops.wm.save_as_mainfile(filepath=str(p))
