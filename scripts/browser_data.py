import json
from pathlib import Path
root=Path(__file__).resolve().parents[1];d=root/'structgate/data'
obj={n:json.loads((d/f).read_text()) for n,f in [('model','model.json'),('captures','captures.json'),('conditions','conditions.json')]}
(root/'docs/data.js').write_text('/* Complete original model and all fixture inputs, not selected outputs. */\nwindow.StructData='+json.dumps(obj,separators=(',',':'),ensure_ascii=True)+';\n')
