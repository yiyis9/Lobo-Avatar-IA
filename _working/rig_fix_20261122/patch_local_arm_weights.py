import bpy,json,math
from collections import Counter
from mathutils import Vector
TARGET=r"C:\Users\irisg\Documents\LoboUPVT\_working\rig_fix_20261122\Lobo_nuevo_candidate_v2.blend"
def norm(p):return bpy.path.abspath(p).replace('/','\\').lower()
if norm(bpy.data.filepath)!=norm(TARGET):raise RuntimeError('Safety stop: candidate path mismatch')
rig=bpy.data.objects.get('Mesh_0_Rig'); obj=bpy.data.objects.get('Mesh_0')
if not rig or not obj:raise RuntimeError('Expected rig/mesh missing')
groups={g.index:g.name for g in obj.vertex_groups}; byname={g.name:g for g in obj.vertex_groups}
armset={g.index for g in obj.vertex_groups if g.name.startswith(('UpperArm_','Forearm_','Hand_','Thumb_','Index_','Middle_','Ring_','Pinky_'))}
segments={}
for b in rig.data.bones:
 if b.name.startswith(('UpperArm_','Forearm_','Hand_','Thumb_','Index_','Middle_','Ring_','Pinky_')):segments[b.name]=(Vector(b.head_local),Vector(b.tail_local))
def dist(p,a,b):
 ab=b-a;t=max(0.0,min(1.0,(p-a).dot(ab)/(ab.length_squared or 1.0)));return (p-(a+t*ab)).length
adj=[set() for _ in obj.data.vertices]
for e in obj.data.edges:a,b=e.vertices;adj[a].add(b);adj[b].add(a)
changed=[]
for v in obj.data.vertices:
 cur={g.group:g.weight for g in v.groups if g.weight>1e-6}
 spine=cur.get(byname['Spine'].index,0.0); root=cur.get(byname['Root'].index,0.0)
 nearest=min((dist(v.co,*line),n) for n,line in segments.items())
 if nearest[0]>0.15:continue
 near_digit=nearest[0]<=0.065 and nearest[1].startswith(('Thumb_','Index_','Middle_','Ring_','Pinky_'))
 if not ((spine>=0.80 and root>=0.10) or (spine>=0.50) or (near_digit and spine>=0.40)):continue
 if spine<0.80 and not nearest[1].startswith(('Hand_','Thumb_','Index_','Middle_','Ring_','Pinky_')):continue
 arm_neighbours=[]
 for j in adj[v.index]:
  w=obj.data.vertices[j]
  weights={g.group:g.weight for g in w.groups if g.weight>1e-6}
  dominant=max(weights,key=weights.get) if weights else None
  if dominant in armset:
   arm_neighbours.append(weights)
 if len(arm_neighbours)<1 and not near_digit:continue
 # Average adjacent moving-region weights; for an isolated, high-confidence digit vertex,
 # use its nearest finger bone rather than leaving it attached to the torso.
 avg={}
 if arm_neighbours:
  for ws in arm_neighbours:
   for i,w in ws.items():avg[i]=avg.get(i,0.0)+w/len(arm_neighbours)
 elif near_digit:
  avg[byname[nearest[1]].index]=1.0
 asum=sum(avg.values())
 if asum<=1e-8:continue
 avg={i:w/asum for i,w in avg.items()}
 # Local transition: smooth the default Spine/Root-only assignment toward real neighboring arm weights.
 strength=1.0 if (spine>=0.80 and root>=0.10) or (near_digit and not arm_neighbours) else 0.85
 merged={i:(1.0-strength)*w for i,w in cur.items()}
 for i,w in avg.items():merged[i]=merged.get(i,0.0)+strength*w
 total=sum(merged.values());merged={i:w/total for i,w in merged.items() if w/total>1e-5}
 old=cur.copy()
 for i in list(cur):
  try:byname[groups[i]].remove([v.index])
  except Exception:pass
 for i,w in merged.items():byname[groups[i]].add([v.index],w,'REPLACE')
 changed.append({'vertex':v.index,'nearest_bone':nearest[1],'dist':round(nearest[0],5),'neighbors':len(arm_neighbours),'old':{groups[i]:round(w,4) for i,w in old.items()},'new':{groups[i]:round(w,4) for i,w in merged.items()}})
if not changed:raise RuntimeError('No high-confidence vertices met repair criteria; nothing saved.')
out=TARGET[:-6]+'_patch_report.json'
with open(out,'w',encoding='utf8') as f:json.dump({'blend':TARGET,'method':'85% local arm-neighbor weights + 15% original Spine/Root weights','changed_count':len(changed),'vertices':changed},f,ensure_ascii=False,indent=2)
bpy.ops.wm.save_as_mainfile(filepath=TARGET)
print(json.dumps({'file':bpy.data.filepath,'changed_count':len(changed),'output':out,'examples':changed[:12]},ensure_ascii=False))
