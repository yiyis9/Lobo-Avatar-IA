import bpy, json, math, sys
from mathutils import Euler, Vector

args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
if len(args) != 2:
    raise RuntimeError('Usage: -- <allowed-blend> <output-json>')
target, output = args
allowed = {
    r'C:\Users\irisg\Documents\LoboUPVT\_working\rig_fix_20261122\Lobo_nuevo_working.blend'.lower(),
    r'C:\Users\irisg\Documents\LoboUPVT\_working\rig_fix_20261122\Lobo_nuevo_candidate_v2.blend'.lower(),
    r'C:\Users\irisg\Documents\LoboUPVT\_working\rig_fix_20261122\Lobo_nuevo_candidate_v3.blend'.lower(),
    r'C:\Users\irisg\Documents\LoboUPVT\_working\rig_fix_20261122\Lobo_nuevo_candidate_v4.blend'.lower(),
    r'C:\Users\irisg\Documents\LoboUPVT\_working\rig_fix_20261122\Lobo_nuevo_candidate_v5.blend'.lower(),
}
if target.lower() not in allowed or bpy.path.abspath(bpy.data.filepath).replace('/', '\\').lower() != target.lower():
    raise RuntimeError('Safety stop: file is not an explicitly allowed working copy')
rig = bpy.data.objects['Mesh_0_Rig']
obj = bpy.data.objects['Mesh_0']
names = {g.index:g.name for g in obj.vertex_groups}
verts = obj.data.vertices
adj = [set() for _ in verts]
for e in obj.data.edges:
    a,b=e.vertices; adj[a].add(b); adj[b].add(a)
def weights(v):
    return {names[g.group]:round(g.weight,5) for g in v.groups if g.weight>1e-6}
def ring(start, levels=2):
    found={start}; frontier={start}
    for _ in range(levels):
        nxt=set().union(*(adj[i] for i in frontier))-found if frontier else set()
        found |= nxt; frontier=nxt
    return sorted(found)
def xyz(v): return [round(float(x),6) for x in v.co]
def pose_coords():
    bpy.context.view_layer.update(); dg=bpy.context.evaluated_depsgraph_get(); ev=obj.evaluated_get(dg); me=ev.to_mesh()
    coords=[ev.matrix_world@v.co for v in me.vertices]; ev.to_mesh_clear(); return coords
saved={p.name:(p.rotation_mode,p.rotation_euler.copy(),p.rotation_quaternion.copy(),p.location.copy(),p.scale.copy()) for p in rig.pose.bones}
for p in rig.pose.bones:
    p.rotation_mode='QUATERNION'; p.rotation_quaternion=(1,0,0,0); p.location=(0,0,0); p.scale=(1,1,1)
base=pose_coords()
report={'file':target,'mesh_vertex_count':len(verts),'vertices':{},'poses':[]}
focus={8222,8305,3524,3518,9929,9990}
for idx in focus:
    if idx>=len(verts): continue
    region=ring(idx,2)
    report['vertices'][str(idx)]={'co':xyz(verts[idx]),'weights':weights(verts[idx]),'neighbors':sorted(adj[idx]),'ring2':[{'i':j,'co':xyz(verts[j]),'weights':weights(verts[j])} for j in region if j!=idx]}
for bone_name in ('UpperArm_R','Forearm_R','Hand_R','Index_01_R'):
    pb=rig.pose.bones.get(bone_name)
    if not pb: continue
    for axis in 'XZ':
      for deg in (-60,-45,45,60):
        pb.rotation_quaternion=Euler(tuple(math.radians(deg) if 'XYZ'[i]==axis else 0 for i in range(3)),'XYZ').to_quaternion()
        posed=pose_coords()
        pair_dist=(posed[8222]-posed[8305]).length
        seam_dist=(posed[9929]-posed[9990]).length
        local=[]
        for idx in (8222,8305,9929,9990):
            for j in adj[idx]:
                before=(base[idx]-base[j]).length; after=(posed[idx]-posed[j]).length
                if before>.005:
                    local.append({'edge':[idx,j],'rest':round(before,6),'posed':round(after,6),'ratio':round(after/before,3)})
        report['poses'].append({'bone':bone_name,'axis':axis,'degrees':deg,'pair_8222_8305':round(pair_dist,6),'pair_9929_9990':round(seam_dist,6),'local_edges':local})
        pb.rotation_quaternion=(1,0,0,0)
for p in rig.pose.bones:
    mode,e,q,l,s=saved[p.name]; p.location=l; p.rotation_mode=mode; p.rotation_euler=e; p.rotation_quaternion=q; p.scale=s
bpy.context.view_layer.update()
with open(output,'w',encoding='utf8') as f: json.dump(report,f,ensure_ascii=False,indent=2)
print('DIAGNOSTIC='+output)
print(json.dumps({'file':target,'vertices':{k:{'co':v['co'],'weights':v['weights'],'neighbors':v['neighbors']} for k,v in report['vertices'].items()},'poses':report['poses']},ensure_ascii=False))
