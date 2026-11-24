import bpy,json
from mathutils import Vector
TARGET=r"C:\Users\irisg\Documents\LoboUPVT\_working\rig_fix_20261122\Lobo_nuevo_candidate.blend"
if bpy.data.filepath.replace('/','\\').lower()!=TARGET.lower(): raise RuntimeError('Safety stop')
obj=bpy.data.objects['Mesh_0']; ids=[9534,9650,3813,3892,9929,9990,9459,9569,9788,9789,7810,7893]
g={x.index:x.name for x in obj.vertex_groups}; adj={i:[] for i in ids}; faces={i:[] for i in ids}
for e in obj.data.edges:
 a,b=e.vertices
 if a in adj: adj[a].append(b)
 if b in adj: adj[b].append(a)
for f in obj.data.polygons:
 for i in f.vertices:
  if i in faces: faces[i].append(list(f.vertices))
out=[]
for i in ids:
 v=obj.data.vertices[i]
 out.append({'index':i,'co':list(v.co),'weights':sorted([(g[x.group],round(x.weight,4)) for x in v.groups],key=lambda x:-x[1]),'degree':len(adj[i]),'faces':len(faces[i]),'neighbors':[{'index':j,'co':list(obj.data.vertices[j].co),'dist':round((v.co-obj.data.vertices[j].co).length,6),'weights':sorted([(g[x.group],round(x.weight,3)) for x in obj.data.vertices[j].groups],key=lambda x:-x[1])[:4]} for j in adj[i][:30]],'incident_faces':faces[i][:8]})
path=TARGET[:-6]+'_hotspot_vertices.json'
with open(path,'w',encoding='utf8') as f:json.dump(out,f,ensure_ascii=False,indent=2)
print(json.dumps(out,ensure_ascii=False))
print('OUTPUT='+path)
