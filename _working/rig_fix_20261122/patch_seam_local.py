import bpy, json, os
src=r'C:\Users\irisg\Documents\LoboUPVT\_working\rig_fix_20261122\Lobo_nuevo_working.blend'
dst=r'C:\Users\irisg\Documents\LoboUPVT\_working\rig_fix_20261122\Lobo_nuevo_candidate_v3.blend'
if bpy.data.filepath.replace('/','\\').lower()!=src.lower(): raise RuntimeError('Safety stop: clean source copy required')
obj=bpy.data.objects['Mesh_0']
names={g.index:g.name for g in obj.vertex_groups}
groups={g.name:g for g in obj.vertex_groups}
adj=[set() for _ in obj.data.vertices]
for e in obj.data.edges:
    a,b=e.vertices; adj[a].add(b); adj[b].add(a)
centers={9929,9990}
affected=centers|set().union(*(adj[i] for i in centers))
snapshot=[{names[g.group]:g.weight for g in v.groups if g.weight>1e-8} for v in obj.data.vertices]
changes=[]
for i in sorted(affected):
    neighbors=adj[i]
    if not neighbors: continue
    avg={}
    for j in neighbors:
        for name,w in snapshot[j].items(): avg[name]=avg.get(name,0.0)+w/len(neighbors)
    old=snapshot[i]
    merged={}
    for n,w in old.items(): merged[n]=merged.get(n,0)+0.5*w
    for n,w in avg.items(): merged[n]=merged.get(n,0)+0.5*w
    total=sum(merged.values())
    merged={n:w/total for n,w in merged.items() if w/total>1e-5}
    v=obj.data.vertices[i]
    for g in list(v.groups):
        groups[names[g.group]].remove([i])
    for n,w in merged.items(): groups[n].add([i],w,'REPLACE')
    changes.append({'vertex':i,'old':{n:round(w,5) for n,w in old.items()},'new':{n:round(w,5) for n,w in merged.items()},'degree':len(neighbors)})
bpy.context.view_layer.update()
bpy.ops.wm.save_as_mainfile(filepath=dst)
report={'source':src,'candidate':dst,'method':'one-ring local weight smoothing, 50% original + 50% fixed-snapshot neighbor average','centers':sorted(centers),'affected_count':len(changes),'changes':changes}
out=dst[:-6]+'_patch_report.json'
with open(out,'w',encoding='utf8') as f: json.dump(report,f,ensure_ascii=False,indent=2)
print('PATCH_REPORT='+out)
print(json.dumps({'candidate':dst,'affected_count':len(changes),'changes':changes},ensure_ascii=False))
