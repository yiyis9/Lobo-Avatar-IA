import bpy, json, sys
from mathutils import Vector
args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
if len(args)!=2: raise RuntimeError('Usage: -- <allowed-blend> <output-json>')
target,out=args
allowed={r'C:\Users\irisg\Documents\LoboUPVT\_working\rig_fix_20261122\Lobo_nuevo_working.blend'.lower()}
if target.lower() not in allowed or bpy.data.filepath.replace('/','\\').lower()!=target.lower(): raise RuntimeError('Safety stop')
rig=bpy.data.objects['Mesh_0_Rig']; obj=bpy.data.objects['Mesh_0']; groups={g.index:g.name for g in obj.vertex_groups}
def segdist(p,a,b):
 ab=b-a; t=max(0,min(1,(p-a).dot(ab)/(ab.length_squared or 1))); return (p-(a+t*ab)).length
segments={b.name:(Vector(b.head_local),Vector(b.tail_local)) for b in rig.data.bones if b.name.startswith(('Hand_R','Index_','Middle_','Ring_','Pinky_'))}
adj=[set() for _ in obj.data.vertices]
for e in obj.data.edges:a,b=e.vertices;adj[a].add(b);adj[b].add(a)
result=[]
for v in obj.data.vertices:
 d,n=min((segdist(v.co,*s),n) for n,s in segments.items())
 if d<.09:
  result.append({'i':v.index,'co':[round(float(x),6) for x in v.co],'nearest':n,'distance':round(d,6),'weights':{groups[g.group]:round(g.weight,5) for g in v.groups if g.weight>1e-6},'neighbors':[{'i':j,'w':{groups[g.group]:round(g.weight,4) for g in obj.data.vertices[j].groups if g.weight>1e-6}} for j in sorted(adj[v.index])]})
result.sort(key=lambda x:(x['distance'],x['i']))
with open(out,'w',encoding='utf8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
print('OUTPUT='+out,'NEARBY='+str(len(result)))
print(json.dumps(result[:30],ensure_ascii=False))
