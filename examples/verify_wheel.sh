#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
PYTHON=${PYTHON:-python3}
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
"$PYTHON" -m venv "$TMP/venv"
if command -v uv >/dev/null 2>&1; then
 uv pip install --python "$TMP/venv/bin/python" --quiet --no-deps "$ROOT" --target "$TMP/site"
else
 "$TMP/venv/bin/python" -m pip install --quiet --no-deps "$ROOT" --target "$TMP/site"
fi
cd "$TMP"
PYTHONPATH="$TMP/site" "$TMP/venv/bin/python" - <<'PY'
import importlib,json,pathlib,random
from importlib import resources
for m in ['structgate','structgate.audit','structgate.model','structgate.grammar','structgate.schema','structgate.eval','structgate.decode','structgate.corpus','structgate.cli']:
 x=importlib.import_module(m);assert '/site/' in x.__file__,x.__file__
from structgate.audit import trace_report,prefix_report,conditioning_report
from structgate.eval import build_model,run_evaluation
from structgate.schema import RECORD_SCHEMA
p=resources.files('structgate').joinpath('data');captures=json.loads(p.joinpath('captures.json').read_text());conditions=json.loads(p.joinpath('conditions.json').read_text());m=build_model()
for c in captures:
 r=trace_report(m,{'mode':c['mode'],'uniforms':c['uniforms']});assert r['text']==c['text'];assert r['final']['stream_complete']==c['stream_complete']
for c in conditions:
 r=conditioning_report(c['input']);assert all(x['conditioned']==x['direct_conditioned'] for x in r['paths']) if r['conditioning_defined'] else all(x['direct_conditioned'] is None for x in r['paths'])
r=run_evaluation(m);assert [r['modes'][s]['valid'] for s in ['none','grammar','schema']]==[3,40,40]
pathlib.Path('prefix.json').write_text(json.dumps({'prefix':'{','mode':'grammar'}));pathlib.Path('trace.json').write_text(json.dumps({'mode':captures[40]['mode'],'uniforms':captures[40]['uniforms']}));pathlib.Path('condition.json').write_text(json.dumps(conditions[0]['input']))
print('Installed artifact: nine module origins, all 120 complete historical paths, all six exact controls and original full 3/40,40/40,40/40 evaluation verified.')
PY
for kind in prefix trace condition; do
 PYTHONPATH="$TMP/site" "$TMP/venv/bin/python" -m structgate.audit "$kind" --input "$kind.json" > "$kind-report.json"
done
PYTHONPATH="$TMP/site" "$TMP/venv/bin/python" -m structgate gates --min-valid-rate 1 --min-conformance 1 --max-mean-kl 2 --max-unconstrained-rate .2 > gates.log
PYTHONPATH="$TMP/site" "$TMP/venv/bin/python" -m structgate evaluate --format json > evaluation.json
printf '%s\n' 'All three JSON audit commands, original evaluation CLI and original full gates passed outside checkout.'
