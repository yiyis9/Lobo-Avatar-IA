import bpy,json
obj=bpy.data.objects['Mesh_0'];names={g.index:g.name for g in obj.vertex_groups};verts=obj.data.vertices
def w(v):return {names[g.group]:g.weight for g in v.groups if g.weight>.05}
rows=[]
for ei,e in enumerate(obj.data.edges):
 a,b=e.vertices;va,vb=verts[a],verts[b];length=(va.co-vb.co).length
 if length>.02:continue
 mid=(va.co+vb.co)*.5
 if not (-.56<=mid.x<=-.44 and -.18<=mid.y<=-.08 and .29<=mid.z<=.47):continue
 wa,wb=w(va),w(vb)
 def torso(x):return x.get('Spine',0)+x.get('Root',0)
 def arm(x):return sum(x.get(n,0) for n in ('UpperArm_R','Forearm_R','Hand_R'))
 if (torso(wa)>.7 and arm(wb)>.7) or (torso(wb)>.7 and arm(wa)>.7):
  rows.append({'edge':ei,'verts':[a,b],'length':round(length,6),'mid':[round(float(x),5) for x in mid],'weights':[w(va),w(vb)]})
out=bpy.data.filepath.rsplit('.',1)[0]+'_weight_seams.json'
with open(out,'w',encoding='utf8') as f:json.dump(rows,f,ensure_ascii=False,indent=2)
print(json.dumps({'file':bpy.data.filepath,'count':len(rows),'unique_vertices':len(set(i for r in rows for i in r['verts'])),'region_bounds':{'xmin':min((r['mid'][0] for r in rows),default=None),'xmax':max((r['mid'][0] for r in rows),default=None),'ymin':min((r['mid'][1] for r in rows),default=None),'ymax':max((r['mid'][1] for r in rows),default=None),'zmin':min((r['mid'][2] for r in rows),default=None),'zmax':max((r['mid'][2] for r in rows),default=None)},'top':rows[:20]},ensure_ascii=False))
