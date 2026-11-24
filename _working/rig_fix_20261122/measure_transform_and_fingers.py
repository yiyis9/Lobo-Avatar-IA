import bpy,json
from mathutils import Vector
TARGET=r"C:\Users\irisg\Documents\LoboUPVT\_working\rig_fix_20261122\Lobo_nuevo_candidate_v2.blend"
if bpy.data.filepath.replace('/','\\').lower()!=TARGET.lower():raise RuntimeError('Safety stop')
rig=bpy.data.objects['Mesh_0_Rig'];mesh=bpy.data.objects['Mesh_0'];g={x.index:x.name for x in mesh.vertex_groups}
def point_seg(p,a,b):
 d=b-a;t=max(0,min(1,(p-a).dot(d)/(d.dot(d) or 1)));return (p-(a+t*d)).length
digitbones=[b for b in rig.data.bones if b.name.startswith(('Index_','Middle_','Ring_','Pinky_'))]
counts={b.name:{'lt_04':0,'lt_06':0,'lt_08':0,'lt_10':0,'spine_dominant':0,'spine_dominant_lt_06':0} for b in digitbones}
ids=[3518,3524,3783,3813,3892,9534,9650,9929,9990]
examples=[]
for v in mesh.data.vertices:
 co_world=mesh.matrix_world@v.co
 ws={g[x.group]:x.weight for x in v.groups if x.weight>.001}
 spine=ws.get('Spine',0)
 near=sorted((point_seg(co_world,rig.matrix_world@b.head_local,rig.matrix_world@b.tail_local),b.name) for b in digitbones)
 if near:
  d,n=near[0];c=counts[n];c['lt_04']+=d<.04;c['lt_06']+=d<.06;c['lt_08']+=d<.08;c['lt_10']+=d<.10;c['spine_dominant']+=spine>.5 and spine>=max(ws.values());c['spine_dominant_lt_06']+=spine>.5 and spine>=max(ws.values()) and d<.06
 if v.index in ids:
  examples.append({'id':v.index,'local':list(v.co),'world':list(co_world),'weights':ws,'near_digits':near[:3],'rig_world':[[list(rig.matrix_world@b.head_local),list(rig.matrix_world@b.tail_local)] for b in digitbones if b.name in [x[1] for x in near[:1]]]})
out={'rig_matrix':[[*r] for r in rig.matrix_world],'mesh_matrix':[[*r] for r in mesh.matrix_world],'digit_counts':counts,'examples':examples}
path=TARGET[:-6]+'_finger_measure.json'
with open(path,'w',encoding='utf8') as f:json.dump(out,f,ensure_ascii=False,indent=2)
print(json.dumps(out,ensure_ascii=False));print('OUTPUT='+path)
