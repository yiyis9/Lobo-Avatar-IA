import bpy,json
src=r'C:\Users\irisg\Documents\LoboUPVT\_working\rig_fix_20261122\Lobo_nuevo_working.blend'
dst=r'C:\Users\irisg\Documents\LoboUPVT\_working\rig_fix_20261122\Lobo_nuevo_candidate_v5.blend'
if bpy.data.filepath.replace('/','\\').lower()!=src.lower():raise RuntimeError('Safety stop: clean source required')
obj=bpy.data.objects['Mesh_0'];names={g.index:g.name for g in obj.vertex_groups};groups={g.name:g for g in obj.vertex_groups};verts=obj.data.vertices
adj=[set() for _ in verts]
for e in obj.data.edges:a,b=e.vertices;adj[a].add(b);adj[b].add(a)
def weights(v):return {names[g.group]:g.weight for g in v.groups if g.weight>1e-8}
def torso(w):return w.get('Spine',0)+w.get('Root',0)
def arm(w):return sum(w.get(n,0) for n in ('UpperArm_R','Forearm_R','Hand_R'))
centers=set(); seam_edges=[]
for e in obj.data.edges:
 a,b=e.vertices;va,vb=verts[a],verts[b];length=(va.co-vb.co).length
 if length>.02:continue
 mid=(va.co+vb.co)*.5
 if not (-.56<=mid.x<=-.44 and -.18<=mid.y<=-.08 and .29<=mid.z<=.47):continue
 wa,wb=weights(va),weights(vb)
 if (torso(wa)>.7 and arm(wb)>.7) or (torso(wb)>.7 and arm(wa)>.7):
  centers.update((a,b));seam_edges.append({'edge':list(e.vertices),'length':round(length,6),'mid':[round(float(x),5) for x in mid]})
if len(seam_edges)<20:raise RuntimeError('Safety stop: expected seam cluster not detected')
affected=set(centers);frontier=set(centers)
for _ in range(2):
 frontier=set().union(*(adj[i] for i in frontier))-affected
 affected|=frontier
original=[weights(v) for v in verts];current=[w.copy() for w in original]
for _ in range(3):
 updated=[w.copy() for w in current]
 for i in affected:
  if not adj[i]:continue
  avg={}
  for j in adj[i]:
   for n,w in current[j].items():avg[n]=avg.get(n,0)+w/len(adj[i])
  merged={}
  for n,w in current[i].items():merged[n]=merged.get(n,0)+.5*w
  for n,w in avg.items():merged[n]=merged.get(n,0)+.5*w
  total=sum(merged.values());updated[i]={n:w/total for n,w in merged.items() if w/total>1e-5}
 current=updated
changes=[]
for i in sorted(affected):
 old,new=original[i],current[i]
 if all(abs(old.get(n,0)-new.get(n,0))<1e-6 for n in set(old)|set(new)):continue
 for g in list(verts[i].groups):groups[names[g.group]].remove([i])
 for n,w in new.items():groups[n].add([i],w,'REPLACE')
 changes.append({'vertex':i,'old':{n:round(w,4) for n,w in old.items()},'new':{n:round(w,4) for n,w in new.items()}})
bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=dst)
report={'source':src,'candidate':dst,'method':'three-pass 50% neighbor averaging over a two-ring neighborhood of detected torso/arm mismatched edges','seam_edge_count':len(seam_edges),'seam_endpoint_count':len(centers),'affected_neighborhood':len(affected),'changed_vertex_count':len(changes),'seam_edges':seam_edges,'changes':changes}
out=dst[:-6]+'_patch_report.json'
with open(out,'w',encoding='utf8') as f:json.dump(report,f,ensure_ascii=False,indent=2)
print('PATCH_REPORT='+out);print(json.dumps({k:report[k] for k in ('candidate','seam_edge_count','seam_endpoint_count','affected_neighborhood','changed_vertex_count')},ensure_ascii=False))
