import json,struct,pathlib
p=pathlib.Path(r'lobo_referencia_rig.glb'); b=p.read_bytes(); off=12; doc=None
while off<len(b):
 n,t=struct.unpack_from('<II',b,off);off+=8
 if t==0x4E4F534A: doc=json.loads(b[off:off+n]);break
 off+=n
print('animations',[a.get('name') for a in doc.get('animations',[])])
print('mesh primitives',sum(len(m.get('primitives',[])) for m in doc.get('meshes',[])),'skins',len(doc.get('skins',[])),'size',len(b))
