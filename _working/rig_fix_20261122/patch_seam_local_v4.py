import bpy, json
src=r'C:\Users\irisg\Documents\LoboUPVT\_working\rig_fix_20261122\Lobo_nuevo_working.blend'
dst=r'C:\Users\irisg\Documents\LoboUPVT\_working\rig_fix_20261122\Lobo_nuevo_candidate_v4.blend'
if bpy.data.filepath.replace('/','\\').lower()!=src.lower(): raise RuntimeError('Safety stop: clean source copy required')
obj=bpy.data.objects['Mesh_0']; names={g.index:g.name for g in obj.vertex_groups}; groups={g.name:g for g in obj.vertex_groups}
adj=[set() for _ in obj.data.vertices]
for e in obj.data.edges:a,b=e.vertices;adj[a].add(b);adj[b].add(a)
centers={9929,9990}; affected=set(centers); frontier=set(centers)
for _ in range(2):
    frontier=set().union(*(adj[i] for i in frontier))-affected
    affected |= frontier
original=[{names[g.group]:g.weight for g in v.groups if g.weight>1e-8} for v in obj.data.vertices]
current=[w.copy() for w in original]
for _ in range(3):
    updated=[w.copy() for w in current]
    for i in affected:
        if not adj[i]: continue
        avg={}
        for j in adj[i]:
            for n,w in current[j].items():avg[n]=avg.get(n,0)+w/len(adj[i])
        merged={}
        for n,w in current[i].items():merged[n]=merged.get(n,0)+0.5*w
        for n,w in avg.items():merged[n]=merged.get(n,0)+0.5*w
        total=sum(merged.values());updated[i]={n:w/total for n,w in merged.items() if w/total>1e-5}
    current=updated
changes=[]
for i in sorted(affected):
    old=original[i];new=current[i]
    if all(abs(old.get(n,0)-new.get(n,0))<1e-6 for n in set(old)|set(new)):continue
    for g in list(obj.data.vertices[i].groups):groups[names[g.group]].remove([i])
    for n,w in new.items():groups[n].add([i],w,'REPLACE')
    changes.append({'vertex':i,'old':{n:round(w,5) for n,w in old.items()},'new':{n:round(w,5) for n,w in new.items()}})
bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=dst)
report={'source':src,'candidate':dst,'method':'three simultaneous Laplacian smoothing passes with 50% neighbor average over a two-ring neighborhood around seam vertices 9929 and 9990','affected_count':len(changes),'changes':changes}
out=dst[:-6]+'_patch_report.json'
with open(out,'w',encoding='utf8') as f:json.dump(report,f,ensure_ascii=False,indent=2)
print('PATCH_REPORT='+out);print(json.dumps({'candidate':dst,'changed_count':len(changes),'center_weights':{str(i):current[i] for i in sorted(centers)}},ensure_ascii=False))
