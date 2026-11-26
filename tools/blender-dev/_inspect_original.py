import bpy
p=r'C:\Users\irisg\Documents\LoboUPVT\ahora_si_lobo_articulado.blend'
bpy.ops.wm.open_mainfile(filepath=p)
for o in bpy.data.objects:
 if o.type in {'MESH','ARMATURE'}:
  print('OBJ',o.name,o.type,'verts',len(o.data.vertices) if o.type=='MESH' else '', 'groups',[g.name for g in o.vertex_groups] if o.type=='MESH' else '', 'mods',[(m.name,m.type,m.object.name if m.object else '') for m in o.modifiers])
  if o.type=='ARMATURE': print('BONES',[(b.name,tuple(round(x,3) for x in b.head_local),tuple(round(x,3) for x in b.tail_local),b.parent.name if b.parent else None) for b in o.data.bones])
print('ACTIONS',[(a.name,len(a.fcurves) if hasattr(a,'fcurves') else len(a.layers)) for a in bpy.data.actions])
