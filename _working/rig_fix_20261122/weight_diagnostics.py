import bpy, json, math
from mathutils import Vector

TARGET = r"C:\Users\irisg\Documents\LoboUPVT\_working\rig_fix_20261122\Lobo_nuevo_working.blend"
def norm(p): return bpy.path.abspath(p).replace("/", "\\").lower()
if norm(bpy.data.filepath) != norm(TARGET):
    raise RuntimeError(f"Safety stop: {bpy.data.filepath}")
rig = bpy.data.objects.get("Mesh_0_Rig")
mesh = bpy.data.objects.get("Mesh_0")
if not rig or not mesh: raise RuntimeError("Expected rig/mesh not found")
groups = {g.index:g.name for g in mesh.vertex_groups}
arm_names = {n for n in groups.values() if n.startswith(("UpperArm_", "Forearm_", "Hand_"))}
arm_ids = {i for i,n in groups.items() if n in arm_names}
leg_torso_tokens=("Pelvis", "Thigh", "Shin", "Foot", "Toe", "Spine", "Tail", "Ear", "Head")
other_ids={i for i,n in groups.items() if any(t.lower() in n.lower() for t in leg_torso_tokens)}
bone_lines={b.name:(Vector(b.head_local),Vector(b.tail_local)) for b in rig.data.bones}
def seg_dist(p,a,b):
    ab=b-a
    t=max(0.0,min(1.0,(p-a).dot(ab)/(ab.length_squared or 1)))
    return (p-(a+t*ab)).length

stats={n:{"count":0,"z_bins":{},"max_weight":0.0} for n in sorted(arm_names)}
lower_leaks=[]; far_arm=[]; sums=[]; nonnorm=[]
for v in mesh.data.vertices:
    weights={g.group:g.weight for g in v.groups if g.weight>1e-6}
    total=sum(weights.values())
    sums.append(total)
    if total<0.98 or total>1.02: nonnorm.append((v.index,round(total,4),tuple(round(x,4) for x in v.co)))
    arm=[(i,w) for i,w in weights.items() if i in arm_ids]
    other=[(i,w) for i,w in weights.items() if i in other_ids]
    for i,w in arm:
        n=groups[i]; s=stats[n]; s["count"]+=1; s["max_weight"]=max(s["max_weight"],w)
        zbin=round(v.co.z,1); s["z_bins"][zbin]=s["z_bins"].get(zbin,0)+1
    if arm:
        arm_names_here=[groups[i] for i,w in arm]
        best=max(w for i,w in arm)
        if v.co.z < 0.12 and best > 0.005:
            lower_leaks.append((best,v.index,tuple(round(x,4) for x in v.co),[(groups[i],round(w,4)) for i,w in weights.items() if w>0.005]))
        # Arm influence on points more than 0.25m from every involved arm bone segment
        d=min(seg_dist(v.co,*bone_lines[groups[i]]) for i,w in arm if groups[i] in bone_lines)
        if d>0.25 and best>0.01:
            far_arm.append((d,best,v.index,tuple(round(x,4) for x in v.co),[(groups[i],round(w,4)) for i,w in weights.items() if w>0.01]))
report={
 "blend":bpy.data.filepath,"mesh":mesh.name,"vertices":len(mesh.data.vertices),"groups":len(groups),
 "arm_groups":stats,
 "vertices_sum_outside_0.98_1.02":{"count":len(nonnorm),"examples":nonnorm[:30]},
 "arm_weight_below_z_0.12":{"count":len(lower_leaks),"top":sorted(lower_leaks,reverse=True)[:35]},
 "arm_weight_far_from_arm_bones_gt_0.25m":{"count":len(far_arm),"top":sorted(far_arm,reverse=True)[:35]},
}
out=TARGET[:-6]+"_weight_diagnostics.json"
with open(out,"w",encoding="utf-8") as f: json.dump(report,f,ensure_ascii=False,indent=2)
print(json.dumps({k:v for k,v in report.items() if k not in ("arm_groups",)},ensure_ascii=False))
print("OUTPUT="+out)
