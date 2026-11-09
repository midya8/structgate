"""Fresh complete native reports, not selected browser table values."""
import json
from pathlib import Path
from structgate.audit import prefix_report,trace_report,conditioning_report
from structgate.eval import build_model
root=Path(__file__).resolve().parents[1];data=root/'structgate/data';m=build_model();captures=json.loads((data/'captures.json').read_text());conditions=json.loads((data/'conditions.json').read_text())
prefixes=['','{','{"x":','[1,','"a\\u0','tru','0.1e','1 ','@','{"active":true,"city":"x","name":"y","score":1.2e3}']
prefixes+=['\"😀x','\"😀\"','[1e+','[0.2e3]','{\"k\":\"\\u0000\"}','{\"k\":1,}','[true,false,null,{}]']
from structgate.corpus import generate_corpus
import random
rng=random.Random(83)
docs=generate_corpus(200)
for _ in range(200):
 doc=rng.choice(docs);pre=doc[:rng.randrange(len(doc)+1)];prefixes.append(pre);prefixes.append(pre+rng.choice('}]:,x\\\"'))
print(json.dumps({'distributions':[{'prefix':ctx,'probabilities':m.distribution(ctx)} for ctx in list(m._counts)+['','😀x']], 'prefixes':[prefix_report(m,{'prefix':p,'mode':mode}) for mode in ['none','grammar','schema'] for p in prefixes], 'traces':[trace_report(m,{'mode':c['mode'],'uniforms':c['uniforms']}) for c in captures], 'conditions':[conditioning_report(c['input']) for c in conditions]},allow_nan=False,separators=(',',':')))
