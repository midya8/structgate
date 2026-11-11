#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
python3 -m venv "$TMP/venv"
if command -v uv >/dev/null 2>&1; then
 uv pip install --python "$TMP/venv/bin/python" --quiet --no-deps "$ROOT" --target "$TMP/site"
else
 "$TMP/venv/bin/python" -m pip install --quiet --no-deps "$ROOT" --target "$TMP/site"
fi
cp "$ROOT/examples/automaton-reports.json" "$TMP/reports.json"
cd "$TMP"
PYTHONPATH="$TMP/site" "$TMP/venv/bin/python" - <<'PY'
import importlib,json,pathlib,subprocess,sys
for m in ['structgate','structgate.automaton','structgate.automaton_cli','structgate.audit','structgate.model','structgate.grammar','structgate.schema','structgate.eval','structgate.decode','structgate.corpus','structgate.cli']:
 mod=importlib.import_module(m)
 assert '/site/' in mod.__file__,mod.__file__
from structgate.automaton import automaton_report
for c in json.loads(pathlib.Path('reports.json').read_text()):
 r=c['report']
 assert automaton_report(r['input'])==r
 pathlib.Path('input.json').write_text(json.dumps(r['input']))
 for command in [[sys.executable,'-m','structgate.automaton_cli'],[str(pathlib.Path('site/bin/structgate-automaton').resolve())]]:
  p=subprocess.run(command+['--input','input.json'],capture_output=True,text=True,check=True)
  assert json.loads(p.stdout)==r
print('Isolated eleven-module install: all24 reports exact through API, module and console entrypoints outside checkout.')
PY
