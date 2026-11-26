import bpy
bpy.ops.wm.open_mainfile(filepath=r'C:\Users\irisg\Documents\LoboUPVT\ahora_si_lobo_articulado.blend')
r=bpy.data.objects['Lobo_UPVT_Rig']
for up,fo in [(.05,.7),(.15,.7),(.2,.8),(.25,.75),(.25,.9),(.35,.75),(.15,1.0)]:
 for pb in r.pose.bones:pb.rotation_mode='XYZ';pb.rotation_euler=(0,0,0)
 r.pose.bones['upper_arm.L'].rotation_euler.x=up;r.pose.bones['forearm.L'].rotation_euler.x=fo;bpy.context.view_layer.update()
 print(up,fo,tuple(round(v,3) for v in r.pose.bones['forearm.L'].head),tuple(round(v,3) for v in r.pose.bones['forearm.L'].tail),tuple(round(v,3) for v in r.pose.bones['hand.L'].tail))
