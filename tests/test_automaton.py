import copy
from fractions import Fraction as F
import itertools
import json
from pathlib import Path
import random
import subprocess
import sys
import unittest
from structgate.automaton import automaton_report, normalize

ROOT = Path(__file__).resolve().parents[1]
BASE = json.loads((ROOT/'examples/automaton.json').read_text())


def enumerate_reference(req):
    # No native normalize, order, h, viability or transition rows used here.
    a, H, D = req['alphabet'], req['horizon'], req['transitions']
    P = {k: list(map(F, v))for k, v in req['rows'].items()}
    def suffixes(s, prev, k):
        out = []
        for word in itertools.product(a, repeat=k):
            st, pr, prob = s, prev, F(1)
            for c in word:
                prob *= P[pr][a.index(c)]
                st, pr = D[st][a.index(c)], c
            out.append((''.join(word), st in req['accept'], prob))
        return out
    sums = {}
    viable = {}
    for k in range(H+1):
        for s in req['states']:
            for p in ['*']+a:
                ls = suffixes(s, p, k)
                sums[k, s, p] = sum((m for _, ok, m in ls if ok), F(0))
                viable[k, s] = any(ok for _, ok, _ in ls)
    event = sums[H, req['start'], '*']
    words = []
    for w, ok, prob in suffixes(req['start'], '*', H):
        s, p, local = req['start'], '*', F(1)
        for elapsed, c in enumerate(w):
            permitted = [i for i, d in enumerate(D[s])if viable[H-elapsed-1, d]]
            denom = sum((P[p][i]for i in permitted), F(0))
            local *= P[p][a.index(c)]/denom if denom and a.index(c)in permitted else F(0)
            s, p = D[s][a.index(c)], c
        if not ok:
            local = F(0)
        words.append((w, ok, prob, local))
    return sums, viable, event, words


class AutomatonTests(unittest.TestCase):
    def test_01_default_changes_future_not_support(self):
        r = automaton_report(BASE)
        self.assertEqual(r['acceptance_mass'], '1/2')
        self.assertEqual(r['word']['source'], '1/20')
        self.assertEqual(r['word']['local'], '1/2')
        self.assertEqual(r['word']['conditioned'], '1/10')
        self.assertEqual(r['local_failure_mass'], '0')

    def test_02_exhaustive_independent_seeded_reference(self):
        rng = random.Random(7821)
        for case in range(60):
            x = copy.deepcopy(BASE)
            states = ['s'+str(j)for j in range(rng.randint(1, 3))]
            x.update(states=states, start=states[0], accept=[s for s in states if rng.randrange(2)],
                     transitions={s: [rng.choice(states)for _ in range(2)]for s in states}, horizon=rng.randrange(6))
            x['word'] = ''.join(rng.choice('01')for _ in range(x['horizon']))
            for p in x['rows']:
                q = rng.randrange(5)
                x['rows'][p] = [str(q)+'/4', str(4-q)+'/4']
            h, viable, mass, words = enumerate_reference(x)
            r = automaton_report(x)
            self.assertEqual(F(r['acceptance_mass']), mass)
            for n in r['nodes']:
                k, s, p = n['remaining'], n['state'], n['previous']
                self.assertEqual(F(n['future_mass']), h[k, s, p])
                self.assertEqual(n['possible'], viable[k, s])
                for t in n['transitions']:
                    c, d = t['symbol'], t['destination']
                    prob = F(x['rows'][p][x['alphabet'].index(c)])
                    self.assertEqual(t['viable'], viable[k-1, d])
                    self.assertEqual(F(t['conditioned']), prob*h[k-1, d, c]/h[k, s, p]) if h[k, s, p] else self.assertIsNone(t['conditioned'])
            local_accepted = sum((q for _, _, _, q in words), F(0))
            self.assertEqual(F(r['local_acceptance_mass']), local_accepted)
            self.assertEqual(F(r['local_failure_mass']), 1-local_accepted)
            w = next(w for w in words if w[0] == x['word'])
            self.assertEqual(F(r['word']['source']), w[2])
            self.assertEqual(F(r['word']['local']), w[3])
            self.assertEqual(r['word']['conditioned'], str(w[2]/mass if w[1]else F(0)) if mass else None)
            # Independently aggregate every source/local/global prefix from words.
            for layer in r['layers']:
                k = layer['elapsed']
                for item in layer['states']:
                    for mode in ['source', 'conditioned']:
                        if mode == 'conditioned'and not mass:
                            self.assertIsNone(item[mode]);continue
                        total = F(0)
                        for word, ok, p, _ in words:
                            st = x['start']
                            for c in word[:k]:st = x['transitions'][st][x['alphabet'].index(c)]
                            prev = word[k-1]if k else '*'
                            if (st, prev)==(item['state'], item['previous']):
                                total += p if mode == 'source'else (p/mass if ok else F(0))
                        self.assertEqual(F(item[mode]), total)
                    local_prefix = F(0)
                    for chars in itertools.product(x['alphabet'], repeat=k):
                        state, previous, weight = x['start'], '*', F(1)
                        for elapsed, c in enumerate(chars):
                            allowed = [j for j, d in enumerate(x['transitions'][state]) if viable[x['horizon']-elapsed-1, d]]
                            ps = list(map(F, x['rows'][previous]))
                            den = sum((ps[j] for j in allowed), F(0))
                            j = x['alphabet'].index(c)
                            weight *= ps[j]/den if den and j in allowed else F(0)
                            state, previous = x['transitions'][state][j], c
                        if x['horizon'] == 0 and x['start'] not in x['accept']:
                            weight = F(0)
                        if (state, previous) == (item['state'], item['previous']):
                            local_prefix += weight
                    self.assertEqual(F(item['local']), local_prefix)


    def test_03_complete_saved_reports(self):
        for c in json.loads((ROOT/'examples/automaton-reports.json').read_text()):
            self.assertEqual(automaton_report(c['report']['input']), c['report'])

    def test_04_mass_conservation_and_telescoping(self):
        for c in json.loads((ROOT/'examples/automaton-reports.json').read_text()):
            r = c['report']
            for l in r['layers']:
                self.assertEqual(sum((F(s['source'])for s in l['states']), F(0)), 1)
                self.assertEqual(sum((F(s['local'])for s in l['states']), F(0))+F(l['local_failure']), 1)
                if r['conditioning_defined']:
                    self.assertEqual(sum((F(s['conditioned'])for s in l['states']), F(0)), 1)
            self.assertEqual(r['word']['conditioned'], r['word']['direct_conditioned'])

    def test_05_closed_long_horizon_and_empty_word(self):
        x = copy.deepcopy(BASE);x.update(horizon=32, word='0'*31+'1')
        r = automaton_report(x)
        self.assertEqual(r['acceptance_mass'], '1/2')
        self.assertEqual(r['structure']['source_words'], '4294967296')
        self.assertEqual(r['structure']['transition_rows'], 192)
        self.assertEqual(F(r['word']['conditioned']), F(9, 10)**30/F(10))
        x.update(horizon=0, word='')
        self.assertIsNone(automaton_report(x)['word']['conditioned'])
        x['accept'] = ['end0']
        self.assertEqual(automaton_report(x)['word']['conditioned'], '1')

    def test_06_zero_source_syntactic_deadends(self):
        x = copy.deepcopy(BASE);x['rows']['0'] = [1, 0];x['rows']['1'] = [0, 1]
        r = automaton_report(x)
        self.assertEqual(r['local_failure_mass'], '1/2')
        self.assertTrue(r['syntactic_completion'])
        self.assertEqual(r['conditioned_acceptance_mass'], '1')
        x['rows']['*'] = [1, 0]
        r = automaton_report(x)
        self.assertFalse(r['conditioning_defined'])
        self.assertEqual(r['local_failure_mass'], '1')

    def test_07_strict_shapes_types_and_boundaries(self):
        for change in [dict(horizon=True), dict(horizon=1.0), dict(horizon=33), dict(word='1'),
                       dict(states=['bad label']), dict(accept=['x']), dict(alphabet=['*']), dict(start=[]),
                       dict(rows={'*': [True, 0], '0': [1, 0], '1': [1, 0]}),
                       dict(rows={'*': ['1/1000001', '1000000/1000001'], '0': [1, 0], '1': [1, 0]})]:
            x = copy.deepcopy(BASE);x.update(change)
            with self.assertRaises(ValueError):automaton_report(x)
        x = copy.deepcopy(BASE);x['unknown'] = 1
        with self.assertRaises(ValueError):automaton_report(x)
        x = copy.deepcopy(BASE);x['transitions']['end0'] = ['end0']
        with self.assertRaises(ValueError):automaton_report(x)

    def test_08_inputs_not_mutated(self):
        x = copy.deepcopy(BASE);before = copy.deepcopy(x)
        automaton_report(x);self.assertEqual(before, x)
        self.assertEqual(normalize(normalize(x)), normalize(x))

    def test_09_strict_cli_and_roundtrip(self):
        for text in [json.dumps(BASE).replace('1/2', '-0', 1).replace('"-0"', '-0'), '{"horizon":1,"horizon":2}', '{"n":NaN}', '['*10+'0'+']'*10, ' '*100001,
                     json.dumps(dict(BASE, horizon=2.0)), json.dumps(dict(BASE, unknown=True))]:
            p = subprocess.run([sys.executable, '-m', 'structgate.automaton_cli', '--input', '-'], input=text, text=True, capture_output=True)
            self.assertEqual(p.returncode, 2);self.assertEqual(p.stdout, '');self.assertIn('automaton error', p.stderr)
        p = subprocess.run([sys.executable, '-m', 'structgate.automaton_cli', '--input', '-'], input=json.dumps(BASE), text=True, capture_output=True)
        self.assertEqual(p.returncode, 0);self.assertEqual(json.loads(p.stdout), automaton_report(BASE))

    def test_10_all_historical_artifacts_unchanged(self):
        import hashlib
        hashes = json.loads((ROOT/'structgate/data/original-hashes.json').read_text())
        for f, h in hashes["sha256"].items():
            self.assertEqual(hashlib.sha256((ROOT/f).read_bytes()).hexdigest(), h, f)
