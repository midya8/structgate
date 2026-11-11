from pathlib import Path
import subprocess,sys
root=Path(__file__).resolve().parents[1]
paths=[root/p for p in ['examples/automaton.json','examples/automaton-reports.json','docs/automaton-data.js']]
old={p:p.read_bytes()for p in paths}
try:
 subprocess.run([sys.executable,str(root/'scripts/build_automaton.py')],check=True)
 assert all(p.read_bytes()==old[p]for p in paths)
 print('All24 complete exact reports and browser input data regenerate byte-for-byte.')
finally:
 for p,b in old.items():p.write_bytes(b)
