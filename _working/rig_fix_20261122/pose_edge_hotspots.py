import bpy, json, math
from mathutils import Euler, Vector
TARGET=r"C:\Users\irisg\Documents\LoboUPVT\_working\rig_fix_20261122\Lobo_nuevo_candidate_v2.blend"
if bpy.path.abspath(bpy.data.filepath).replace('/','\\').lower()!=TARGET.lower(): raise RuntimeError('Safety stop: wrong blend path')
rig=bpy.data.objects['Mesh_0_Rig']; obj=bpy.data.objects['Mesh_0']; deps=bpy.context.evaluated_depsgraph_get()
def coords():
    bpy.context.view_layer.update(); deps=bpy.context.evaluated_depsgraph_get(); ev=obj.evaluated_get(deps); me=ev.to_mesh(); c=[ev.matrix_world@v.co for v in me.vertices]; ev.to_mesh_clear(); return c
saved={p.name:(p.rotation_mode,p.rotation_euler.copy(),p.rotation_quaternion.copy(),p.location.copy(),p.scale.copy()) for p in rig.pose.bones}
for p in rig.pose.bones: p.rotation_mode='QUATERNION'; p.rotation_quaternion=(1,0,0,0); p.location=(0,0,0); p.scale=(1,1,1)
base=coords(); group={g.index:g.name for g in obj.vertex_groups}; out=[]
for name in ('UpperArm_R','Forearm_R'):
    pb=rig.pose.bones.get(name)
    if not pb: continue
    for axis in 'XZ':
      for deg in (-90,90):
        pb.rotation_quaternion=Euler(tuple(math.radians(deg) if 'XYZ'[i]==axis else 0 for i in range(3)),'XYZ').to_quaternion()
        posed=coords(); edges=[]
        for ei,e in enumerate(obj.data.edges):
          a,b=e.vertices; bl=(base[a]-base[b]).length
          if bl<=0.005: continue
          pl=(posed[a]-posed[b]).length; ratio=pl/bl
          if ratio>=3:
            mid=(obj.data.vertices[a].co+obj.data.vertices[b].co)*0.5
            def w(v): return sorted([(group[g.group],round(g.weight,3)) for g in v.groups if g.weight>.05],key=lambda x:-x[1])[:5]
            edges.append((ratio,ei,a,b,round(bl,5),round(pl,5),tuple(round(x,4) for x in mid),w(obj.data.vertices[a]),w(obj.data.vertices[b])))
        edges.sort(reverse=True)
        out.append({'bone':name,'axis':axis,'degrees':deg,'count_ratio_ge_3':len(edges),'hotspots':edges[:8]})
        pb.rotation_quaternion=(1,0,0,0)
for p in rig.pose.bones:
  mode,e,q,l,s=saved[p.name]; p.location=l; p.rotation_mode=mode; p.rotation_euler=e; p.rotation_quaternion=q; p.scale=s
bpy.context.view_layer.update()
path=TARGET[:-6]+'_pose_edge_hotspots.json'
with open(path,'w',encoding='utf8') as f: json.dump(out,f,ensure_ascii=False,indent=2)
print('OUTPUT='+path)
print(json.dumps([{'bone':x['bone'],'axis':x['axis'],'deg':x['degrees'],'gt3':x['count_ratio_ge_3'],'top':x['hotspots'][:2]} for x in out if x['hotspots']],ensure_ascii=False))
