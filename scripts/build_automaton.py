"""Deterministic inputs and native reports, never browser answer data."""
from pathlib import Path
import copy
import json
import random
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from structgate.automaton import automaton_report
root = Path(__file__).resolve().parents[1]
base = {'alphabet': ['0', '1'], 'states': ['end0', 'end1'], 'start': 'end0',
        'accept': ['end1'], 'transitions': {'end0': ['end0', 'end1'], 'end1': ['end0', 'end1']},
        'rows': {'*': ['1/2', '1/2'], '0': ['9/10', '1/10'], '1': ['1/10', '9/10']},
        'horizon': 2, 'word': '01'}
cases = [{'id': 'legal-does-not-mean-likely', 'input': base}]

def add(name, **kw):
    x = copy.deepcopy(base)
    x.update(kw)
    cases.append({'id': name, 'input': x})

add('four-billion-source-words', horizon=32, word='0'*31+'1')
add('all-words-control', accept=['end0', 'end1'], horizon=5, word='01010')
add('empty-language', accept=[])
add('source-zero-event', rows={'*': [1, 0], '0': [1, 0], '1': [0, 1]})
add('source-zero-stranding', rows={'*': ['1/2', '1/2'], '0': [1, 0], '1': [0, 1]})
add('rejected-word', word='00')
add('empty-accepted', horizon=0, word='', accept=['end0'])
add('empty-rejected', horizon=0, word='')
add('single-character', horizon=1, word='1')
add('no-consecutive-ones', states=['zero', 'one', 'dead'], start='zero', accept=['one'],
    transitions={'zero': ['zero', 'one'], 'one': ['zero', 'dead'], 'dead': ['dead', 'dead']}, horizon=6, word='010101')
add('three-symbols', alphabet=['a', 'b', 'c'], states=['even', 'odd'], start='even', accept=['even'],
    transitions={'even': ['odd', 'even', 'even'], 'odd': ['even', 'odd', 'odd']},
    rows={'*': ['1/2', '1/3', '1/6'], 'a': ['1/3']*3, 'b': ['1/4', '1/4', '1/2'], 'c': [0, '1/2', '1/2']}, horizon=4, word='abac')
add('one-symbol', alphabet=['x'], rows={'*': [1], 'x': [1]},
    transitions={'end0': ['end1'], 'end1': ['end0']}, horizon=32, word='x'*32)
add('maximum-product', alphabet=['a', 'b', 'c', 'd'], states=['s'+str(i)for i in range(8)],
    start='s0', accept=['s0', 's3'], transitions={'s'+str(i): ['s'+str((i+j+1)%8)for j in range(4)]for i in range(8)},
    rows={c: ['1/4']*4 for c in ['*', 'a', 'b', 'c', 'd']}, horizon=32, word='abcd'*8)
rng = random.Random(371)
for i in range(10):
    x = copy.deepcopy(base)
    n = rng.randint(1, 4)
    x['states'] = ['s'+str(j)for j in range(n)]
    x['start'] = x['states'][0]
    x['accept'] = [s for s in x['states']if rng.randrange(2)]
    x['transitions'] = {s: [rng.choice(x['states'])for _ in range(2)]for s in x['states']}
    x['rows'] = {}
    for c in ['*', '0', '1']:
        p = rng.randrange(5)
        x['rows'][c] = [str(p)+'/4', str(4-p)+'/4']
    x['horizon'] = rng.randint(1, 6)
    x['word'] = ''.join(rng.choice('01')for _ in range(x['horizon']))
    cases.append({'id': 'seeded-'+str(i), 'input': x})
reports = [{'id': c['id'], 'report': automaton_report(c['input'])}for c in cases]
(root/'examples/automaton.json').write_text(json.dumps(base, indent=2)+'\n')
(root/'examples/automaton-reports.json').write_text(json.dumps(reports, separators=(',', ':'))+'\n')
(root/'docs/automaton-data.js').write_text('window.AutomatonInputs='+json.dumps(cases, separators=(',', ':'))+';\n')
print(json.dumps({'reports': len(reports), 'nodes': sum(len(x['report']['nodes'])for x in reports),
                  'transitions': sum(sum(len(n['transitions'])for n in x['report']['nodes'])for x in reports),
                  'layer_rows': sum(sum(len(l['states'])for l in x['report']['layers'])for x in reports)}))
