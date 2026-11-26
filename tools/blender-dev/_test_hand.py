import bpy
bpy.ops.wm.open_mainfile(filepath=r'C:\Users\irisg\Documents\LoboUPVT\ahora_si_lobo_articulado.blend')
r=bpy.data.objects['Lobo_UPVT_Rig']
for hx,hz in [(0,0),(-.8,0),(-.8,.5),(.8,0),(.8,.5)]:
 for pb in r.pose.bones:pb.rotation_mode='XYZ';pb.rotation_euler=(0,0,0)
 r.pose.bones['upper_arm.L'].rotation_euler.x=.05;r.pose.bones['forearm.L'].rotation_euler.x=.7;r.pose.bones['hand.L'].rotation_euler=(hx,0,hz);bpy.context.view_layer.update()
 p=r.pose.bones['hand.L']; print(hx,hz,'head',tuple(round(v,3) for v in p.head),'tail',tuple(round(v,3) for v in p.tail))
