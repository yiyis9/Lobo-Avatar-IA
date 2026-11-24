import bpy,json
from collections import Counter,defaultdict
from mathutils import Vector
TARGET=r"C:\Users\irisg\Documents\LoboUPVT\_working\rig_fix_20261122\Lobo_nuevo_working.blend"
if bpy.data.filepath.replace('/','\\').lower()!=TARGET.lower(): raise RuntimeError('Safety stop')
rig=bpy.data.objects['Mesh_0_Rig']; obj=bpy.data.objects['Mesh_0']; group={g.index:g.name for g in obj.vertex_groups}
segments={}
for side in ('L','R'):
 for part in ('UpperArm','Forearm','Hand'):
  b=rig.data.bones.get(f'{part}_{side}')
  if b: segments[f'{part}_{side}']=(Vector(b.head_local),Vector(b.tail_local))
def dist(p,a,b):
 ab=b-a;t=max(0,min(1,(p-a).dot(ab)/(ab.length_squared or 1)));return (p-(a+t*ab)).length
adj=[set() for _ in obj.data.vertices]
for e in obj.data.edges:a,b=e.vertices;adj[a].add(b);adj[b].add(a)
bad=defaultdict(list);pattern=Counter()
for v in obj.data.vertices:
 ws={group[x.group]:x.weight for x in v.groups if x.weight>.005}
 if not ws:continue
 dom=max(ws,key=ws.get)
 if dom not in ('Spine','Root'):continue
 nearby=sorted((dist(v.co,*line),n) for n,line in segments.items())
 d,name=nearby[0]
 if d<0.20:
  neigh=Counter()
  for j in adj[v.index]:
   wj={group[x.group]:x.weight for x in obj.data.vertices[j].groups}
   if wj:neigh[max(wj,key=wj.get)]+=1
  arm_neigh=sum(n for k,n in neigh.items() if k.startswith(('UpperArm_','Forearm_','Hand_')))
  key=(dom,tuple(sorted((k,round(x,2)) for k,x in ws.items())),name,round(d,2),arm_neigh)
  pattern[key]+=1
  if arm_neigh>=2:bad[key].append({'i':v.index,'co':[round(x,4) for x in v.co],'weights':sorted([(k,round(w,3)) for k,w in ws.items()],key=lambda x:-x[1]),'neighbors':dict(neigh)})
out={'pattern_counts':[{'pattern':str(k),'count':n} for k,n in pattern.most_common(60)],'adjacent_arm_candidates':[{'pattern':str(k),'count':len(v),'examples':v[:12]} for k,v in sorted(bad.items(),key=lambda kv:-len(kv[1]))]}
path=TARGET[:-6]+'_weight_outliers.json'
with open(path,'w',encoding='utf8') as f:json.dump(out,f,ensure_ascii=False,indent=2)
print(json.dumps({'patterns':out['pattern_counts'][:20],'candidates':out['adjacent_arm_candidates'][:20]},ensure_ascii=False))
print('OUTPUT='+path)
