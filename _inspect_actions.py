import bpy
p=r'C:\Users\irisg\Documents\LoboUPVT\ahora_si_lobo_articulado.blend'; bpy.ops.wm.open_mainfile(filepath=p)
rig=bpy.data.objects['Lobo_UPVT_Rig']; model=bpy.data.objects['Lobo_UPVT_Modelo']
print('TRANSFORMS',tuple(model.location),tuple(model.rotation_euler),tuple(model.scale),tuple(rig.location),tuple(rig.scale))
for an in ['Idle','Saludo']:
 a=bpy.data.actions[an]; print('ACTION',an,'range',a.frame_range)
 rig.animation_data.action=a
 for f in [1,8,12,16,20,24,32,42]:
  bpy.context.scene.frame_set(f)
  if f==1 or an=='Saludo':
   print('F',f,[(n,tuple(round(v,3) for v in rig.pose.bones[n].rotation_euler),tuple(round(v,3) for v in rig.pose.bones[n].tail)) for n in ['upper_arm.L','forearm.L','hand.L']])
print('GROUP WTS SAMPLE')
for g in ['upper_arm.L','forearm.L','hand.L']:
 vg=model.vertex_groups.get(g); vals=[]
 for v in model.data.vertices:
  for e in v.groups:
   if e.group==vg.index and e.weight>.01: vals.append((round(model.matrix_world@v.co,3),round(e.weight,2)))
 print(g,len(vals),vals[:3],vals[-3:])
