import json,struct,pathlib
p=pathlib.Path(r'lobo_upvt_nuevo.glb')
b=p.read_bytes(); off=12; doc=None
while off<len(b):
 n,t=struct.unpack_from('<II',b,off); off+=8
 if t==0x4E4F534A: doc=json.loads(b[off:off+n]); break
 off+=n
print('anims:',[a.get('name') for a in doc.get('animations',[])])
print('nodes:',len(doc.get('nodes',[])),'skins:',len(doc.get('skins',[])),'size:',len(b))
