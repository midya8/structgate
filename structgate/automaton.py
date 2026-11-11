"""Exact finite-horizon DFA conditioning for a supplied first-order source.

Standard product-state dynamic programming and Doob reweighting. This separate
API does not change the historical JSON validator, source or generation policy.
"""
from __future__ import annotations
from copy import deepcopy
from fractions import Fraction as F
from functools import lru_cache
import re


def _fields(x, names):
    if not isinstance(x, dict) or set(x) != set(names):
        raise ValueError('wrong object fields: ' + ','.join(names))


def _prob(x):
    if type(x) is int:
        q = F(x)
    elif isinstance(x, str) and len(x) <= 32 and re.fullmatch(r'[0-9]+(?:/[1-9][0-9]*)?', x, flags=re.ASCII):
        q = F(x)
    else:
        raise ValueError('probabilities must be integers or unsigned rational strings')
    if not 0 <= q <= 1 or q.denominator > 10**6:
        raise ValueError('probability outside [0,1] or reduced denominator above 1000000')
    return q


def normalize(request):
    _fields(request, ['alphabet', 'states', 'start', 'accept', 'transitions', 'rows', 'horizon', 'word'])
    r = deepcopy(request)
    a, states = r['alphabet'], r['states']
    if not isinstance(a, list) or not 1 <= len(a) <= 4 or any(not isinstance(c, str) or re.fullmatch('[A-Za-z0-9]', c) is None for c in a) or len(set(a)) != len(a):
        raise ValueError('alphabet needs 1..4 distinct ASCII alphanumeric symbols')
    if not isinstance(states, list) or not 1 <= len(states) <= 8 or any(not isinstance(s, str) or re.fullmatch('[A-Za-z][A-Za-z0-9_]{0,15}', s) is None for s in states) or len(set(states)) != len(states):
        raise ValueError('states needs 1..8 distinct ASCII identifiers of at most 16 characters')
    if not isinstance(r['start'], str) or r['start'] not in states:
        raise ValueError('unknown start state')
    acc = r['accept']
    if not isinstance(acc, list) or any(not isinstance(s, str) or s not in states for s in acc) or len(set(acc)) != len(acc):
        raise ValueError('accept must be a distinct subset of states')
    if type(r['horizon']) is not int or not 0 <= r['horizon'] <= 32:
        raise ValueError('horizon must be an integer in 0..32')
    if not isinstance(r['word'], str) or len(r['word']) != r['horizon'] or any(c not in a for c in r['word']):
        raise ValueError('word must have exactly horizon symbols from alphabet')
    _fields(r['transitions'], states)
    for s in states:
        row = r['transitions'][s]
        if not isinstance(row, list) or len(row) != len(a) or any(not isinstance(d, str) or d not in states for d in row):
            raise ValueError('each total DFA transition row needs one known destination per symbol')
    _fields(r['rows'], ['*'] + a)
    for prev, row in r['rows'].items():
        if not isinstance(row, list) or len(row) != len(a):
            raise ValueError('source row length must equal alphabet length')
        ps = list(map(_prob, row))
        if sum(ps) != 1:
            raise ValueError('source rows must sum exactly to one')
        r['rows'][prev] = [str(q) for q in ps]
    return r


def automaton_report(request):
    r = normalize(request)
    a, states, N = r['alphabet'], r['states'], r['horizon']
    contexts = ['*'] + a
    probs = {p: list(map(F, row)) for p, row in r['rows'].items()}
    delta = r['transitions']

    @lru_cache(None)
    def possible(k, s):
        return s in r['accept'] if k == 0 else any(possible(k-1, d) for d in delta[s])

    @lru_cache(None)
    def h(k, s, prev):
        if k == 0:
            return F(s in r['accept'])
        return sum((probs[prev][i] * h(k-1, delta[s][i], c) for i, c in enumerate(a)), F(0))

    def row(k, s, prev):
        hv = h(k, s, prev)
        z = sum((probs[prev][i] for i, d in enumerate(delta[s]) if possible(k-1, d)), F(0))
        return {'remaining': k, 'state': s, 'previous': prev,
                'possible': possible(k, s), 'future_mass': str(hv), 'viable_mass': str(z),
                'local_defined': bool(z), 'conditional_defined': bool(hv),
                'transitions': [{'symbol': c, 'destination': delta[s][i],
                                 'source': str(probs[prev][i]),
                                 'viable': possible(k-1, delta[s][i]),
                                 'next_future_mass': str(h(k-1, delta[s][i], c)),
                                 'local': str(probs[prev][i] / z) if z and possible(k-1, delta[s][i]) else '0',
                                 'conditioned': str(probs[prev][i] * h(k-1, delta[s][i], c) / hv) if hv else None}
                                for i, c in enumerate(a)]}

    nodes = [row(k, s, p) for k in range(1, N+1) for s in states for p in contexts]
    lookup = {(n['remaining'], n['state'], n['previous']): n for n in nodes}
    mass = h(N, r['start'], '*')
    keys = [(s, p) for s in states for p in contexts]
    vectors = [{key: F(key == (r['start'], '*')) for key in keys} for _ in range(3)]
    if not mass:
        vectors[2] = {key: F(0) for key in keys}
    sink = F(0)
    layers = []
    for elapsed in range(N+1):
        layers.append({'elapsed': elapsed, 'local_failure': str(sink),
                       'states': [{'state': s, 'previous': p,
                                   'source': str(vectors[0][s, p]), 'local': str(vectors[1][s, p]),
                                   'conditioned': str(vectors[2][s, p]) if mass else None}
                                  for s, p in keys]})
        if elapsed == N:
            break
        new = [{key: F(0) for key in keys} for _ in range(3)]
        for s, p in keys:
            n = lookup[N-elapsed, s, p]
            if not n['local_defined']:
                sink += vectors[1][s, p]
            for t in n['transitions']:
                key = t['destination'], t['symbol']
                for j, mode in enumerate(['source', 'local', 'conditioned']):
                    if t[mode] is not None:
                        new[j][key] += vectors[j][s, p] * F(t[mode])
        vectors = new
    # At horizon zero a syntactically impossible empty word fails immediately.
    if N == 0 and not possible(0, r['start']):
        sink = F(1)
        vectors[1] = {key: F(0) for key in keys}
        layers[0]['local_failure'] = '1'
        for item in layers[0]['states']:
            item['local'] = '0'
    accepted = [sum((v[s, p] for s, p in keys if s in r['accept']), F(0)) for v in vectors]
    state, prev = r['start'], '*'
    path, path_masses = [], [F(1), F(1), F(1) if mass else None]
    for elapsed, c in enumerate(r['word']):
        n = lookup[N-elapsed, state, prev]
        t = n['transitions'][a.index(c)]
        for j, mode in enumerate(['source', 'local', 'conditioned']):
            if path_masses[j] is not None:
                path_masses[j] *= F(t[mode]) if t[mode] is not None else F(0)
        path.append({'elapsed': elapsed, 'state': state, 'previous': prev,
                     'symbol': c, 'future_mass': n['future_mass'], 'transition': t.copy(),
                     'prefix_source': str(path_masses[0]), 'prefix_local': str(path_masses[1]),
                     'prefix_conditioned': str(path_masses[2]) if mass else None})
        state, prev = t['destination'], c
    word_accept = state in r['accept']
    if N == 0 and not word_accept:
        path_masses[1] = F(0)
    return {'schema': 1, 'input': r, 'acceptance_mass': str(mass), 'conditioning_defined': bool(mass),
            'syntactic_completion': possible(N, r['start']),
            'local_acceptance_mass': str(accepted[1]), 'local_failure_mass': str(sink),
            'conditioned_acceptance_mass': str(accepted[2]) if mass else None,
            'nodes': nodes, 'layers': layers,
            'word': {'text': r['word'], 'accepted': word_accept, 'final_state': state,
                     'source': str(path_masses[0]), 'local': str(path_masses[1]),
                     'conditioned': str(path_masses[2]) if mass else None,
                     'direct_conditioned': str(path_masses[0] / mass if word_accept else F(0)) if mass else None,
                     'steps': path},
            'structure': {'product_states_per_layer': len(keys), 'transition_rows': len(nodes),
                          'source_words': str(len(a)**N)},
            'limits': 'Fixed-length total DFA and supplied first-order source. Viability ignores source zeros. Exact rationals, not arbitrary JSON/CFG or an LLM; no random sampling or quality claim.'}
