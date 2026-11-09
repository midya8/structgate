import copy
import itertools
import json
import math
import random
import subprocess
import sys
import unittest
from fractions import Fraction
from structgate.audit import loads,prefix_report,trace_report,conditioning_report
from structgate.eval import build_model,generate_schema
from structgate.decode import generate
from structgate.grammar import JSONValidator,valid_json
from structgate.schema import SchemaValidator,RECORD_SCHEMA

class AuditTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.model=build_model()
 def test_kl_direction_support(self):
  r=prefix_report(self.model,{'prefix':'','mode':'grammar'})
  self.assertAlmostEqual(r['forward_kl_masked_source'],r['minus_log_mass'])
  self.assertEqual(r['reverse_status'],'infinite_support');self.assertIsNone(r['reverse_kl_source_masked'])
  self.assertGreater(r['removed_mass'],0)
 def test_no_mask_zero_kl(self):
  r=prefix_report(self.model,{'prefix':'','mode':'none'})
  self.assertAlmostEqual(r['allowed_mass'],1);self.assertAlmostEqual(r['forward_kl_masked_source'],0)
  self.assertEqual(r['reverse_status'],'finite_zero')
 def test_failed_masks_empty(self):
  for v in [JSONValidator(),SchemaValidator(RECORD_SCHEMA)]:
   self.assertFalse(v.feed('@'));self.assertEqual(v.allowed(self.model.vocab),frozenset())
 def test_eof_number_differs_stream(self):
  r=prefix_report(self.model,{'prefix':'123','mode':'grammar'})
  self.assertTrue(r['eof_complete']);self.assertFalse(r['stream_complete'])
 def test_no_completion_guarantee(self):
  r=trace_report(self.model,{'mode':'grammar','uniforms':[0.]})
  self.assertEqual(r['stop'],'budget_exhausted');self.assertFalse(r['eof_complete'])
 def test_original_all_120_draws(self):
  for mode in ['none','grammar','schema']:
   for seed in range(1000,1040):
    cap=220 if mode=='schema' else 200
    rng=random.Random(seed);us=[rng.random() for _ in range(cap)]
    r=trace_report(self.model,{'mode':mode,'uniforms':us})
    if mode=='schema':text,complete,kls=generate_schema(self.model,random.Random(seed),RECORD_SCHEMA)
    else:
     old=generate(self.model,random.Random(seed),mode=='grammar');text=old['text'];complete=old['complete'];kls=[s.kl for s in old['steps']]
    self.assertEqual(r['text'],text);self.assertEqual(r['final']['stream_complete'],complete)
    self.assertEqual(len(r['steps']),len(kls))
    for step,kl in zip(r['steps'],kls):self.assertAlmostEqual(step['minus_log_mass'],kl,places=12)
 def test_all_prefixes_mask_rows(self):
  for pre in ['', '{','{"x":','[1,','"a\\u0','tru','0.1e','1 ','@']:
   r=prefix_report(self.model,{'prefix':pre,'mode':'grammar'})
   if r['allowed_mass']:
    self.assertAlmostEqual(sum(x['masked'] for x in r['rows']),1)
    self.assertAlmostEqual(sum(x['kl_term'] for x in r['rows']),r['minus_log_mass'])
 def test_trace_path_log_ratio(self):
  r=trace_report(self.model,{'mode':'grammar','uniforms':[.3,.5,.7,.1,.6]})
  lp=lq=0
  for s in r['steps']:
   row=next(x for x in s['rows'] if x['char']==s['chosen']);lp+=math.log(row['source']);lq+=math.log(row['masked'])
  self.assertAlmostEqual(lq-lp,r['sampled_log_ratio'])
 def test_schema_fractional_exponent_known_limit(self):
  text='{"active":true,"city":"x","name":"y","score":1.2e3}'
  self.assertIsInstance(json.loads(text),dict)
  r=prefix_report(self.model,{'prefix':text,'mode':'schema'})
  self.assertTrue(r['failed']) # retained historical validator limitation, not JSON law
 def test_strict_input(self):
  for text in ['{"x":1,"x":2}','NaN','1e999','['*10+']'*10,' '*100001]:
   with self.assertRaises(ValueError):loads(text)
  for req in [{'prefix':True,'mode':'grammar'},{'prefix':'','mode':'other'},{'prefix':'','mode':'grammar','x':0}]:
   with self.assertRaises(ValueError):prefix_report(self.model,req)
  for us in [[True],[float('inf')],[-1],[1],[],[0]*221]:
   with self.assertRaises(ValueError):trace_report(self.model,{'mode':'grammar','uniforms':us})
 def test_cli(self):
  r=subprocess.run([sys.executable,'-m','structgate.audit','prefix','--input','-'],input='{"prefix":"","mode":"grammar"}',text=True,capture_output=True)
  self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(json.loads(r.stdout)['reverse_status'],'infinite_support')
  r=subprocess.run([sys.executable,'-m','structgate.audit','prefix','--input','-'],input='{"bad":0}',text=True,capture_output=True)
  self.assertEqual(r.returncode,2);self.assertEqual(r.stdout,'')

class ConditioningTests(unittest.TestCase):
 def req(self):return {'alphabet':['0','1'],'words':['00','10','11'],'rows':{'*':['1/2','1/2'],'0':['9/10','1/10'],'1':['1/10','9/10']}}
 def test_direct_enumeration_all_rows(self):
  q=self.req();r=conditioning_report(q);p={k:list(map(Fraction,v)) for k,v in q['rows'].items()}
  masses={}
  for chars in itertools.product(q['alphabet'],repeat=2):
   word=''.join(chars);mass=p['*'][int(word[0])]*p[word[0]][int(word[1])]
   if word in q['words']:masses[word]=mass
  z=sum(masses.values());self.assertEqual(Fraction(r['acceptance_mass']),z)
  for path in r['paths']:
   self.assertEqual(Fraction(path['source']),masses[path['word']]);self.assertEqual(Fraction(path['conditioned']),masses[path['word']]/z);self.assertEqual(path['conditioned'],path['direct_conditioned'])
  for node in r['nodes']:
   pre=node['prefix'];h=Fraction(node['h'])
   expected=sum((mass for word,mass in masses.items() if word.startswith(pre)),Fraction(0))
   prior=Fraction(1)
   for i,c in enumerate(pre):prior*=p[pre[i-1] if i else '*'][int(c)]
   self.assertEqual(h,expected/prior)
 def test_local_not_global(self):
  r=conditioning_report(self.req());self.assertGreater(Fraction(r['terminal_l1_half']),0);self.assertEqual(r['stranded_local_mass'],'0')
 def test_unrestricted_equal(self):
  q=self.req();q['words']=['00','01','10','11'];r=conditioning_report(q)
  self.assertEqual(r['acceptance_mass'],'1');self.assertEqual(r['terminal_l1_half'],'0')
 def test_stranded_local_mass(self):
  q=self.req();q['words']=['00','11'];q['rows']['0']=['0','1'];r=conditioning_report(q)
  self.assertEqual(r['stranded_local_mass'],'1/2');self.assertEqual(sum(Fraction(x['local']) for x in r['paths']),Fraction(1,2))
  self.assertEqual(sum(Fraction(x['conditioned']) for x in r['paths']),1)
 def test_zero_acceptance(self):
  q=self.req();q['words']=['00'];q['rows']['0']=['0','1'];r=conditioning_report(q)
  self.assertFalse(r['conditioning_defined']);self.assertEqual(r['acceptance_mass'],'0');self.assertTrue(all(x['direct_conditioned'] is None for x in r['paths']))
 def test_one_token(self):
  q=self.req();q['words']=['0'];r=conditioning_report(q);self.assertEqual(r['paths'][0]['conditioned'],'1')
 def test_reject(self):
  for change in [dict(words=['0','11']),dict(words=['00','00']),dict(alphabet=['*']),dict(rows={'*':['.1','.1']})]:
   q=self.req();q.update(change)
   with self.assertRaises(ValueError):conditioning_report(q)
  for x in [True,'NaN','1/0','-1','9/2','1/999999999999999999']:
   q=self.req();q['rows']['*'][0]=x
   with self.assertRaises(ValueError):conditioning_report(q)
 def test_random_small_oracles(self):
  rng=random.Random(71)
  for _ in range(24):
   words=[''.join(x) for x in itertools.product('01',repeat=4) if rng.random()<.7]
   if not words:continue
   q={'alphabet':['0','1'],'words':words,'rows':{}}
   for c in ['*','0','1']:
    k=rng.randrange(1,10);q['rows'][c]=[f'{k}/10',f'{10-k}/10']
   r=conditioning_report(q);z=Fraction(0);masses={}
   for w in words:
    m=Fraction(1)
    for i,c in enumerate(w):m*=Fraction(q['rows'][w[i-1] if i else '*'][int(c)])
    masses[w]=m;z+=m
   self.assertEqual(Fraction(r['acceptance_mass']),z)
   for path in r['paths']:self.assertEqual(Fraction(path['conditioned']),masses[path['word']]/z)

class PreservationTests(unittest.TestCase):
 def test_original_files_unchanged(self):
  import hashlib
  from pathlib import Path
  root=Path(__file__).resolve().parents[1];manifest=json.loads((root/'structgate/data/original-hashes.json').read_text())
  for name,digest in manifest['sha256'].items():self.assertEqual(hashlib.sha256((root/name).read_bytes()).hexdigest(),digest,name)
 def test_source_counts_all_exported(self):
  from pathlib import Path
  root=Path(__file__).resolve().parents[1];m=build_model();d=json.loads((root/'structgate/data/model.json').read_text())
  self.assertEqual(d['counts'],m._counts);self.assertEqual(d['totals'],m._totals);self.assertEqual(d['vocab'],list(m.vocab));self.assertEqual(len(d['counts']),287)
 def test_tv_failure_sink(self):
  q={'alphabet':['0','1'],'words':['00','11'],'rows':{'*':['1/2','1/2'],'0':['0','1'],'1':['1/10','9/10']}}
  r=conditioning_report(q);self.assertEqual(r['total_variation_with_failure'],'1/2')
