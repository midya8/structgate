"""Export the unchanged full source model and every historical fixture draw."""
from pathlib import Path
import hashlib,json,random,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from structgate.eval import build_model,run_evaluation,generate_schema
from structgate.decode import generate
from structgate.schema import RECORD_SCHEMA
root=Path(__file__).resolve().parents[1];out=root/'structgate/data';out.mkdir(exist_ok=True)
def write(name,x):
 (out/name).write_text(json.dumps(x,ensure_ascii=True,allow_nan=False,separators=(',',':'))+'\n')
m=build_model()
write('model.json',{'order':m.order,'smoothing':m.smoothing,'vocab':list(m.vocab),'counts':{k:dict(v) for k,v in sorted(m._counts.items())},'totals':dict(m._totals),'corpus_size':200,'corpus_seed':42,'schema':RECORD_SCHEMA.fields,'initial_context':'Unpadded prefix, matching original generation. logprob() separately pads its initial context; it is not used here.'})
captures=[]
for mode in ['none','grammar','schema']:
 for seed in range(1000,1040):
  cap=220 if mode=='schema' else 200
  rng=random.Random(seed);us=[rng.random() for _ in range(cap)]
  if mode=='schema':text,complete,kls=generate_schema(m,random.Random(seed),RECORD_SCHEMA)
  else:
   r=generate(m,random.Random(seed),mode=='grammar');text=r['text'];complete=r['complete'];kls=[s.kl for s in r['steps']]
  captures.append({'id':mode+'-'+str(seed),'mode':mode,'seed':seed,'uniforms':us[:len(text)],'text':text,'stream_complete':complete,'historical_kls':kls,'budget':cap})
write('captures.json',captures);write('historical-evaluation.json',run_evaluation(m))
base={'alphabet':['0','1'],'words':['00','10','11'],'rows':{'*':['1/2','1/2'],'0':['9/10','1/10'],'1':['1/10','9/10']}}
import copy
cases=[{'id':'future-mass-changes-root','input':base}]
q=copy.deepcopy(base);q['words']=['00','01','10','11'];cases.append({'id':'unrestricted-control','input':q})
q=copy.deepcopy(base);q['words']=['00','11'];q['rows']['0']=['0','1'];cases.append({'id':'locally-stranded','input':q})
q=copy.deepcopy(base);q['words']=['00'];q['rows']['0']=['0','1'];cases.append({'id':'zero-event','input':q})
q={'alphabet':['a','b','c'],'words':['aaa','abc','bac','bbb','cab'],'rows':{'*':['1/2','1/3','1/6'],'a':['1/10','2/10','7/10'],'b':['1/3','1/3','1/3'],'c':['1/4','1/4','1/2']}};cases.append({'id':'three-symbol-language','input':q})
q=copy.deepcopy(base);q['words']=['0'];cases.append({'id':'one-token-control','input':q})
write('conditions.json',cases)
print(json.dumps({'captures':len(captures),'characters':sum(len(x['text']) for x in captures),'contexts':len(m._counts),'vocab':len(m.vocab),'condition_cases':len(cases)}))
