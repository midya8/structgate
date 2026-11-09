"""Full-model prefix masks and exact finite-language conditioning controls.

No completion guarantee for bounded JSON generation. Finite-language conditioning
is exact rational arithmetic on a supplied fixed-length Markov language, not a
solver for arbitrary JSON or a pretrained language model.
"""
from __future__ import annotations
import argparse
import json
import math
import re
import sys
from fractions import Fraction
from .grammar import JSONValidator, valid_json
from .schema import SchemaValidator, RECORD_SCHEMA, conforms

MAX_BYTES = 100000

def _pairs(pairs):
    d = {}
    for k,v in pairs:
        if k in d: raise ValueError('duplicate JSON key')
        d[k]=v
    return d

def loads(text):
    if len(text.encode('utf8')) > MAX_BYTES: raise ValueError('input exceeds 100000 bytes')
    def bad(_): raise ValueError('nonfinite JSON number')
    obj=json.loads(text,object_pairs_hook=_pairs,parse_constant=bad)
    def check(x,d=0):
        if d>8: raise ValueError('nesting exceeds 8')
        if isinstance(x,float) and not math.isfinite(x): raise ValueError('nonfinite JSON number')
        if isinstance(x,dict):
            for v in x.values():check(v,d+1)
        elif isinstance(x,list):
            for v in x:check(v,d+1)
    check(obj)
    return obj

def exact_fields(x, fields):
    if not isinstance(x,dict) or set(x)!=set(fields): raise ValueError('wrong object fields: '+','.join(fields))

def prefix_report(model, request):
    exact_fields(request,['prefix','mode'])
    prefix,mode=request['prefix'],request['mode']
    if not isinstance(prefix,str) or len(prefix)>512:raise ValueError('prefix must be a string of at most 512 characters')
    if mode not in ('none','grammar','schema'):raise ValueError('unknown mode')
    v=JSONValidator() if mode!='schema' else SchemaValidator(RECORD_SCHEMA)
    v.feed(prefix)
    source=model.distribution(prefix)
    allowed=set(model.vocab) if mode=='none' else v.allowed(model.vocab)
    # Sequential binary64 additions match the documented cross-language contract.
    mass=0.0
    for c in sorted(allowed):mass+=source[c]
    if mode=='none':mass=1.0
    rows=[]
    removed=0.0
    for c in model.vocab:
        p=source[c]; q=p/mass if c in allowed and mass>0 else 0.0
        if q==0:removed+=p
        rows.append({'char':c,'source':p,'allowed':c in allowed,'masked':q,
                     'kl_term':q*math.log(q/p) if q>0 else 0.0})
    kl=0.0
    for r in rows:kl+=r['kl_term']
    complete=valid_json(prefix) if mode!='schema' else v.complete and conforms(prefix,RECORD_SCHEMA)['conforms']
    return {'prefix':prefix,'mode':mode,'failed':v.failed,'stream_complete':v.complete,
            'eof_complete':bool(complete),'allowed_mass':mass,'removed_mass':removed,
            'forward_kl_masked_source':kl if mass>0 else None,
            'minus_log_mass':-math.log(mass) if mass>0 else None,
            'reverse_kl_source_masked':0.0 if removed==0 and mass>0 else None,
            'reverse_status':'finite_zero' if removed==0 and mass>0 else ('infinite_support' if mass>0 else 'undefined_empty_mask'),
            'rows':rows}

def trace_report(model, request):
    exact_fields(request,['mode','uniforms'])
    mode=request['mode'];us=request['uniforms']
    if mode not in ('none','grammar','schema'):raise ValueError('unknown mode')
    if not isinstance(us,list) or not 1<=len(us)<=220 or any(type(u) not in (int,float) or not math.isfinite(u) or not 0<=u<1 for u in us):raise ValueError('uniforms must contain 1..220 finite numbers in [0,1)')
    text='';steps=[];stop='budget_exhausted'
    for u in us:
        r=prefix_report(model,{'prefix':text,'mode':mode})
        if r['allowed_mass']<=0:stop='empty_mask';break
        acc=0.;chosen=None
        for row in r['rows']:
            if row['masked']<=0:continue
            chosen=row['char'];acc+=row['masked']
            if u<acc:break
        r['uniform']=u;r['chosen']=chosen;steps.append(r);text+=chosen
        after=prefix_report(model,{'prefix':text,'mode':mode})
        if after['failed']:stop='invalid_prefix';break
        if after['stream_complete']:stop='stream_complete';break
    final=prefix_report(model,{'prefix':text,'mode':mode})
    total=0.0
    for s in steps:total+=s['minus_log_mass']
    return {'text':text,'mode':mode,'stop':stop,'steps':steps,'final':final,
            'sampled_log_ratio':total,'eof_complete':final['eof_complete'],
            'note':'Path log-ratio is not a sequence KL expectation; budget can end incomplete.'}

def _rational(x):
    if not isinstance(x,str) or len(x)>40 or re.fullmatch(r'-?\d+(?:/\d+)?',x,flags=re.ASCII) is None:raise ValueError('probabilities must be integer or numerator/positive-denominator strings')
    try:q=Fraction(x)
    except (ValueError,ZeroDivisionError):raise ValueError('invalid rational') from None
    if q<0 or q>1 or q.denominator>10**12 or abs(q.numerator)>10**12:raise ValueError('rational outside bounds')
    return q

def conditioning_report(req):
    exact_fields(req,['alphabet','words','rows'])
    alphabet,words,rows=req['alphabet'],req['words'],req['rows']
    if not isinstance(alphabet,list) or not 1<=len(alphabet)<=4 or any(not isinstance(c,str) or len(c)!=1 or not c.isascii() or not c.isalnum() for c in alphabet) or len(set(alphabet))!=len(alphabet):raise ValueError('alphabet must contain 1..4 distinct ASCII alphanumeric characters')
    if not isinstance(words,list) or not 1<=len(words)<=128 or any(not isinstance(w,str) or not 1<=len(w)<=8 or any(c not in alphabet for c in w) for w in words) or len(set(words))!=len(words) or len({len(w) for w in words})!=1:raise ValueError('words must be 1..128 distinct same-length words of length 1..8')
    exact_fields(rows,['*']+alphabet)
    probs={}
    for state,row in rows.items():
        if not isinstance(row,list) or len(row)!=len(alphabet):raise ValueError('wrong row length')
        probs[state]=list(map(_rational,row))
        if sum(probs[state])!=1:raise ValueError('each probability row must sum exactly to one')
    words=sorted(words);L=len(words[0]);prefixes=sorted({w[:i] for w in words for i in range(L+1)},key=lambda s:(len(s),s))
    def dist(pre):return dict(zip(alphabet,probs[pre[-1] if pre else '*']))
    h={}
    for pre in reversed(prefixes):
        h[pre]=Fraction(1) if len(pre)==L else sum((dist(pre)[c]*h[pre+c] for c in alphabet if pre+c in h),Fraction(0))
    local={'':Fraction(1)};conditioned={'':Fraction(1)};source={'':Fraction(1)};nodes=[];stranded=Fraction(0)
    for pre in prefixes:
        if len(pre)==L:continue
        p=dist(pre);allowed=[c for c in alphabet if pre+c in h];z=sum((p[c] for c in allowed),Fraction(0))
        q={c:(p[c]/z if c in allowed and z else Fraction(0)) for c in alphabet}
        g={c:(p[c]*h.get(pre+c,Fraction(0))/h[pre] if h[pre] else Fraction(0)) for c in alphabet}
        if not z:stranded+=local.get(pre,Fraction(0))
        for c in allowed:
            local[pre+c]=local.get(pre,Fraction(0))*q[c];conditioned[pre+c]=conditioned.get(pre,Fraction(0))*g[c];source[pre+c]=source.get(pre,Fraction(0))*p[c]
        nodes.append({'prefix':pre,'h':str(h[pre]),'legal_mass':str(z),'source':{c:str(p[c]) for c in alphabet},'local':{c:str(q[c]) for c in alphabet},'conditioned':{c:str(g[c]) for c in alphabet}})
    paths=[{'word':w,'source':str(source.get(w,Fraction(0))),'local':str(local.get(w,Fraction(0))),'conditioned':str(conditioned.get(w,Fraction(0))),'direct_conditioned':str(source.get(w,Fraction(0))/h['']) if h[''] else None} for w in words]
    tv=sum((abs(local.get(w,Fraction(0))-conditioned.get(w,Fraction(0))) for w in words),Fraction(0))/2
    return {'acceptance_mass':str(h['']),'conditioning_defined':bool(h['']),'stranded_local_mass':str(stranded),'terminal_l1_half':str(tv),'total_variation_with_failure':str(tv+stranded/2) if h[''] else None,'nodes':nodes,'paths':paths,'limits':'Fixed-length finite language, first-order source. Exact rationals, not arbitrary JSON conditioning. Undefined conditionals are zero rows with explicit false status.'}

def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('kind',choices=['prefix','trace','condition']);parser.add_argument('--input',required=True);args=parser.parse_args(argv)
    try:
        if args.input=='-':text=sys.stdin.read(MAX_BYTES+1)
        else:
            with open(args.input,encoding='utf8') as f:text=f.read(MAX_BYTES+1)
        request=loads(text)
        if args.kind=='condition':out=conditioning_report(request)
        else:
            from .eval import build_model
            out=(prefix_report if args.kind=='prefix' else trace_report)(build_model(),request)
        print(json.dumps(out,allow_nan=False,separators=(',',':')))
    except (ValueError,TypeError,KeyError,OverflowError,RecursionError,OSError) as e:
        print('audit error: '+str(e),file=sys.stderr);return 2
    return 0

if __name__=='__main__':sys.exit(main())
