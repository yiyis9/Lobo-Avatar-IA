import bpy
from pathlib import Path
ROOT=Path(r'C:\Users\irisg\Documents\LoboUPVT')
SOURCE=ROOT/'ahora_si_lobo_articulado.blend'
OUT=ROOT/'lobo_referencia_rig.blend'
GLB=ROOT/'lobo_referencia_rig.glb'
PREVIEW=ROOT/'lobo_referencia_saludo.png'
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
rig=bpy.data.objects['Lobo_UPVT_Rig']; model=bpy.data.objects['Lobo_UPVT_Modelo']; scene=bpy.context.scene
old=bpy.data.actions.get('Saludo')
if old: bpy.data.actions.remove(old)
a=bpy.data.actions.new('Saludo'); a.use_fake_user=True
rig.animation_data_create(); rig.animation_data.action=a
frames=[
 (1,-.90,-.90,0.0),
 (8,0.0,.35,0.0),
 (16,.05,.7,.75),
 (23,.05,.7,1.15),
 (31,.05,.7,.35),
 (39,.05,.7,1.15),
 (47,.05,.7,.35),
 (55,.05,.7,.75),
 (61,-.20,-.35,0.0),
 (68,-.90,-.90,0.0),
]
for frame, upper, fore, wrist in frames:
 scene.frame_set(frame)
 for name, euler in [('upper_arm.L',(upper,0,0)),('forearm.L',(fore,0,0)),('hand.L',(wrist,0,0))]:
  pb=rig.pose.bones[name]; pb.rotation_mode='XYZ'; pb.rotation_euler=euler
  pb.keyframe_insert(data_path='rotation_euler',frame=frame,group=name)
for layer in a.layers:
 for strip in layer.strips:
  for bag in strip.channelbags:
   for fc in bag.fcurves:
    for k in fc.keyframe_points:
     k.interpolation='BEZIER'; k.handle_left_type='AUTO_CLAMPED'; k.handle_right_type='AUTO_CLAMPED'
scene.frame_end=68; scene.frame_set(31)
for n in ['upper_arm.L','forearm.L','hand.L']:
 pb=rig.pose.bones[n]; print('POSE',n,'head',tuple(round(x,3) for x in pb.head),'tail',tuple(round(x,3) for x in pb.tail))
scene.render.resolution_percentage=60
scene.render.filepath=str(PREVIEW)
bpy.ops.render.render(write_still=True)
scene.frame_set(1); rig.animation_data.action=bpy.data.actions['Idle']
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(OUT))
bpy.ops.object.select_all(action='DESELECT'); rig.select_set(True); model.select_set(True); bpy.context.view_layer.objects.active=rig
bpy.ops.export_scene.gltf(filepath=str(GLB),export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='ACTIONS',export_nla_strips=False,export_force_sampling=True)
print('CLIPS',sorted(x.name for x in bpy.data.actions))






