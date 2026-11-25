"""Merge completed DOS batches only when EXE and weights match the candidate."""
import hashlib
import json
from pathlib import Path
from evaluate_c import parse_output
ROOT=Path(__file__).resolve().parents[1]
parts=json.loads((ROOT/'build/russia/smoke-parts.json').read_text(encoding='utf-8'))
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
result=bytearray()
for part in parts:
    folder=ROOT/'build'/part['name']
    assert (folder/'DONE.TXT').exists(),part
    assert not (folder/'FAILED.TXT').read_bytes(),part
    assert len(parse_output(folder/'OUTPUT.TXT'))==part['count'],part
    for name in ('TINY.EXE','TINY.BIN'):
        assert digest(folder/name)==digest(ROOT/'build/russia'/name),(part,name)
    raw=(folder/'OUTPUT.TXT').read_bytes()
    result.extend(raw)
    (ROOT/'reports/russia'/(part['name']+'.cp866.txt')).write_bytes(raw)
(ROOT/'reports/russia/dos-output.cp866.txt').write_bytes(result)
print('Verified and merged',len(parts),'DOS batches')
