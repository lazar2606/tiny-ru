"""Pair the same 30 arithmetic facts in trained and held-out wording."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
read=lambda path:[json.loads(s) for s in path.read_text(encoding='utf-8').splitlines()]
facts={r['id']:r for r in read(ROOT/'data/facts.jsonl')}
controls=[r for r in read(ROOT/'data/control.jsonl') if r['split']=='арифметика']
rows=[]
for r in controls:
    f=facts[r['fact_id']]
    for name,form in [('arithmetic_familiar',f['train_form']),('arithmetic_paraphrase',1-f['train_form'])]:
        rows.append(dict(fact_id=f['id'],question=f['questions'][form],answers=f['answers'],category='арифметика',split=name))
path=ROOT/'reports/arithmetic-diagnostic.jsonl'
path.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
print(path)
