"""Regenerate all complete fixture data and compare structures, then restore bytes."""
import json,math,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
paths=[root/'structgate/data'/f for f in ['model.json','captures.json','conditions.json','historical-evaluation.json']]+[root/'docs/data.js']
old={p:p.read_bytes() for p in paths}
def compare(a,b):
 if isinstance(a,bool) or a is None or isinstance(a,str):assert a==b
 elif isinstance(a,(int,float)):
  assert type(b) in (int,float) and math.isfinite(b) and abs(a-b)<=1e-12*max(1,abs(a),abs(b)),(a,b)
 elif isinstance(a,list):
  assert isinstance(b,list) and len(a)==len(b)
  for x,y in zip(a,b):compare(x,y)
 else:
  assert isinstance(b,dict) and a.keys()==b.keys()
  for k in a:compare(a[k],b[k])
try:
 subprocess.run([sys.executable,'scripts/regenerate.py'],cwd=root,check=True)
 for p in paths[:-1]:compare(json.loads(old[p]),json.loads(p.read_text()))
 subprocess.run([sys.executable,'scripts/browser_data.py'],cwd=root,check=True)
 before=old[paths[-1]].decode().split('window.StructData=',1)[1].rstrip(';\n')
 after=paths[-1].read_text().split('window.StructData=',1)[1].rstrip(';\n')
 compare(json.loads(before),json.loads(after))
 print('All full regenerated data structures match within 1e-12; checked-in bytes restored.')
finally:
 for p,b in old.items():p.write_bytes(b)
