"""Prepare short independent DOS batches for current Russia weights."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
rows=[json.loads(s) for s in (ROOT/'data/russia-final/smoke.jsonl').read_text(encoding='utf-8').splitlines()]
parts=[]
for start in range(0,len(rows),2):
    name='russia-smoke-%d'%(start//2)
    path=ROOT/'build'/name
    path.mkdir(parents=True,exist_ok=True)
    batch=rows[start:start+2]
    (path/'INPUT.TXT').write_bytes(('\r\n'.join(r['question'] for r in batch)+'\r\nquit\r\n').encode('cp866'))
    parts.append(dict(name=name,count=len(batch)))
(ROOT/'build/russia/smoke-parts.json').write_text(json.dumps(parts,indent=2)+'\n',encoding='utf-8')
print('Prepared',len(parts),'DOS batches,',len(rows),'questions')
