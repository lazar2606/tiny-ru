"""Add ordinary short forms while preserving the final wording holdouts."""
import hashlib
import json
from pathlib import Path
from gen_improved import key
from gen_russia import person_name
from tokenizer import encode
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/russia-calibration'
read=lambda p:[json.loads(s) for s in (ROOT/p).read_text(encoding='utf-8').splitlines()]


def genitive_region(s):
    if s.startswith('республика '):s=s[11:]
    special={'коми':'коми','саха':'саха','марий эл':'марий эл','тыва':'тывы','алтай':'алтая','чечня':'чечни'}
    if s in special:return special[s]
    if s.endswith(' область'):
        return s[:-8].replace('ая','ой')+' области'
    if s.endswith(' край'):return s[:-5].replace('ский','ского').replace('цкий','цкого')+' края'
    if s.endswith('ия'):return s[:-1]+'и'
    if s.endswith('стан'):return s+'а'
    if s in ('дагестан',):return s+'а'
    return None


def build():
    facts=read('data/russia/facts.jsonl')
    held=read('data/russia-expanded/test.jsonl')
    heldkeys={key(r['question'].replace('"','')) for r in held}
    train=read('data/russia-expanded/train.jsonl')
    sexes=json.loads((ROOT/'data/russia/sources/genders.json').read_text(encoding='utf-8'))['results']['bindings']
    female={r['item']['value'] for r in sexes if r['sex']['value'].endswith('/Q6581072')}
    people={f['subject']:person_name(f['subject_label']) for f in facts if f['category']=='россия: биографии'}
    title_cases={'война и мир':'войну и мир','евгений онегин':'евгения онегина',
                 'обломов':'обломова','отцы и дети':'отцов и детей',
                 'герой нашего времени':'героя нашего времени'}
    for f in facts:
        s=f.get('subject_label',f['subject']);prop=f['property'];extra=[]
        if prop=='P36':
            region=genitive_region(s)
            if region:extra=[f'какая столица {region}?',f'какой административный центр {region}?']
        elif prop=='P571' and ' ' not in s:
            accusative=s[:-1]+'у' if s.endswith('а') else s[:-1]+'ю' if s.endswith('я') else s
            extra=[f'когда основали {accusative}?']
        elif prop=='P403':extra=[f'куда впадает {s}?']
        elif prop in ('P569','P570','P19'):
            n=people[f['subject']]
            born='родилась' if f['subject'] in female else 'родился'
            died='умерла' if f['subject'] in female else 'умер'
            if prop=='P569':extra=[f'когда {born} {n}?']
            if prop=='P570':extra=[f'когда {died} {n}?']
        elif prop=='P50' and s in title_cases:extra=[f'кто написал {title_cases[s]}?']
        for q in extra:
            if key(q) in heldkeys:continue
            if len(encode(q,strict=True))>72:continue
            for a in f['answers'][:2]:
                if len(encode(q+'\n'+a+'\n',strict=True))<=128:
                    train.append(dict(fact_id=f['id'],category=f['category'],question=q,answer=a,sample_weight=4))
    unique={}
    for r in train:unique.setdefault((key(r['question']),r['answer']),r)
    train=list(unique.values())
    assert not heldkeys.intersection(key(r['question'].replace('"','')) for r in train)
    OUT.mkdir(parents=True,exist_ok=True)
    p=OUT/'train.jsonl'
    p.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in train),encoding='utf-8')
    manifest=dict(facts=1000,train=len(train),source='data/russia-expanded/train.jsonl',
                  sha256=dict(train=hashlib.sha256(p.read_bytes()).hexdigest()),
                  validation='data/russia-expanded/validation.jsonl',control='data/russia-expanded/control.jsonl')
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(manifest,indent=2))


if __name__=='__main__':build()
