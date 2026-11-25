"""First-stage source import; final curated labels are in correct_russia.py.

This snapshot is retained for training reproducibility. Use data/russia-final
for current facts and evaluation, not this initial uncurated import.
"""
import collections
import hashlib
import json
import random
import re
from pathlib import Path
from tokenizer import encode, normalize, FINGERPRINT
from gen_improved import key
from russia_curated import facts as curated_facts

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/russia'
EXCLUDE={'республика крым','севастополь','донецкая народная республика',
         'луганская народная республика','херсонская область','запорожская область'}


def read_rows(path):
    return [json.loads(s) for s in path.read_text(encoding='utf-8').splitlines() if s.strip()]


def label(value):
    value=normalize(value).strip()
    value=re.sub(r'\s*\([^)]*\)\s*$', '', value)
    value=' '.join(value.split())
    if not value or re.fullmatch(r'q\d+',value) or '/' in value:raise ValueError('Missing/unsuitable label')
    encode(value,strict=True)
    return value


def person_name(value):
    value=label(value)
    if ',' in value:
        last,first=value.split(',',1)
        return first.strip().split()[0]+' '+last.strip()
    words=value.split()
    if len(words)==3:
        if words[1].endswith(('ович','евич','ична','овна','евна')):
            return words[0]+' '+words[-1]
        if words[-1].endswith(('ович','евич','ична','овна','евна')):
            return words[1]+' '+words[0]
    return value


def source_rows(name):
    data=json.loads((OUT/'sources'/(name+'.json')).read_text(encoding='utf-8-sig'))
    grouped=collections.OrderedDict()
    for row in data['results']['bindings']:
        simple={k:v['value'] for k,v in row.items()}
        grouped.setdefault(simple['item'],[]).append(simple)
    if name in ('cities','rivers','books','museums'):
        grouped=collections.OrderedDict(sorted(grouped.items(),key=lambda pair:int(pair[0].rsplit('Q',1)[1])))
    return grouped


def candidates():
    result=curated_facts()
    def add(rows,property_name,category,questions,answers):
        values=list(dict.fromkeys(answers))
        if not values:return
        first=rows[0]
        result.append(dict(subject=first['item'], subject_label=label(first['itemLabel']),
                           property=property_name, category='россия: '+category,
                           questions=questions[:2], held_question=questions[2],
                           answers=values+[v+'.' for v in values],
                           source=first['item'].replace('http://www.wikidata.org/entity/', 'https://www.wikidata.org/wiki/'),
                           source_rows=rows, license='CC0-1.0', verified_on='2026-11-24',
                           verification='structured-source-import', time_sensitive=False))
    for name,groups in [(n,source_rows(n)) for n in ('regions','cities','rivers','people','books','museums')]:
        for item,rows in groups.items():
            try:
                s=label(rows[0]['itemLabel'])
                if s in EXCLUDE:continue
                if name=='regions':
                    if s in ('московская область',):
                        # Historical/current capital claims coexist; omit this ambiguity.
                        continue
                    values=[label(r['valueLabel']) for r in rows]
                    add(rows,'P36','регионы',[f'какой центр у региона "{s}"?',f'центр региона "{s}"?',f'назови административный центр: {s}.'],values)
                elif name=='cities':
                    if s.startswith(('городской округ','городское поселение')):continue
                    years={r['year'][:4] for r in rows if r.get('year','').startswith(tuple('12'))}
                    if len(years)==1 and all(500<=int(y)<=2026 for y in years):
                        add(rows,'P571','города',[f'в каком году основан город {s}?',f'год основания: {s}?',f'когда был основан город {s}?'],sorted(years))
                    waters=[label(r['riverLabel']) for r in rows if 'riverLabel' in r]
                    if waters:
                        add(rows,'P206','география',[f'на каком водоёме расположен город {s}?',f'водоём у города {s}?',f'у какого водоёма находится город {s}?'],waters)
                elif name=='rivers':
                    values=[label(r['valueLabel']) for r in rows]
                    add(rows,'P403','реки',[f'куда впадает река {s}?',f'устье реки "{s}"?',f'назови водоём, куда впадает река {s}.'],values)
                elif name=='people':
                    person=person_name(s)
                    # Gender-free wording avoids inflecting names incorrectly.
                    years={r['birth'][:4] for r in rows}
                    if len(years)==1 and all(500<=int(y)<=2026 for y in years):
                        add(rows,'P569','биографии',[f'{person}: год рождения?',f'назови год рождения: {person}.',f'в каком году появился на свет человек по имени {person}?'],sorted(years))
                    years={r['death'][:4] for r in rows if 'death' in r}
                    if len(years)==1 and all(500<=int(y)<=2026 for y in years):
                        add(rows,'P570','биографии',[f'{person}: год смерти?',f'назови год смерти: {person}.',f'каким годом датируется смерть: {person}?'],sorted(years))
                    places=[label(r['placeLabel']) for r in rows if 'placeLabel' in r]
                    if places:
                        add(rows,'P19','биографии',[f'место рождения: {person}?',f'назови место рождения: {person}.',f'{person}: где место рождения?'],places)
                elif name=='books':
                    authors=list(dict.fromkeys(person_name(r['valueLabel']) for r in rows))
                    if len(authors)==1:
                        add(rows,'P50','литература',[f'кто написал "{s}"?',f'кто автор "{s}"?',f'назови автора произведения "{s}".'],authors)
                    years={r['year'][:4] for r in rows if 'year' in r}
                    if len(years)==1 and all(500<=int(y)<=2026 for y in years):
                        add(rows,'P577','литература',[f'в каком году опубликовано "{s}"?',f'год публикации "{s}"?',f'назови год выхода произведения "{s}".'],sorted(years))
                elif name=='museums':
                    places=[label(r['placeLabel']) for r in rows if 'placeLabel' in r]
                    if places:
                        add(rows,'P131','музеи',[f'где находится "{s}"?',f'где расположен "{s}"?',f'назови местоположение: {s}.'],places)
            except (ValueError,KeyError):
                continue
    return result


def build():
    previous=read_rows(ROOT/'data/train.jsonl')+read_rows(ROOT/'data/improved/train.jsonl')
    seen={key(r['question']) for r in previous}
    pools=collections.OrderedDict()
    rejected=collections.Counter()
    identities=set()
    question_answers={}
    accepted=[]
    # Detect ambiguous labels rather than arbitrarily assigning one answer.
    raw=candidates()
    meanings=collections.defaultdict(set)
    for f in raw:
        meanings[key(f['questions'][0])].add(tuple(sorted(key(a) for a in f['answers'])))
    for f in raw:
        identity=(f['subject'],f['property'])
        if identity in identities:continue
        if len(meanings[key(f['questions'][0])])>1:
            rejected['ambiguous_question']+=1;continue
        try:
            answers=list(dict.fromkeys(normalize(a) for a in f['answers']))
            questions=list(dict.fromkeys(normalize(q) for q in f['questions']))
            held=normalize(f['held_question'])
            if key(held) in seen:
                if f['property']=='capital':held='какой город служит столицей россии?'
                else:raise ValueError('Warm-start overlap')
            if key(held) in seen or key(held) in {key(q) for q in questions}:raise ValueError('Holdout overlap')
            for q in questions+[held]:
                if len(encode(q,strict=True))>72:raise ValueError('Question too long')
                for a in answers:
                    if len(encode(q+'\n'+a+'\n',strict=True))>128 or len(encode(a))>56:raise ValueError('Answer/context too long')
            f.update(questions=questions,held_question=held,answers=answers)
            identities.add(identity)
            pools.setdefault(f['category'],[]).append(f)
        except ValueError as exc:
            rejected[str(exc)]+=1
    # Keep the entire hand-checked core, then balance source topics. Each
    # record is one relation, not a paraphrase counted as a new fact.
    for category,rows in pools.items():
        if rows[0].get('verification')!='structured-source-import':accepted+=rows
    queues={category:rows[:] for category,rows in pools.items() if rows[0].get('verification')=='structured-source-import'}
    while len(accepted)<1000 and any(queues.values()):
        for category,rows in queues.items():
            if rows and len(accepted)<1000:accepted.append(rows.pop(0))
    if len(accepted)!=1000:raise ValueError('Only %d suitable distinct facts; source pool=%s'%(len(accepted),{k:len(v) for k,v in pools.items()}))
    train=[]; test=[]; familiar=[]
    for i,f in enumerate(accepted,1):
        f['id']='russia-%04d'%i
        for q in f['questions']:
            for a in f['answers'][:2]:
                train.append(dict(fact_id=f['id'],category=f['category'],question=q,answer=a,sample_weight=f.get('sample_weight',1)))
        test.append(dict(fact_id=f['id'],category=f['category'],question=f['held_question'],answers=f['answers'],split='russia_unseen'))
        familiar.append(dict(fact_id=f['id'],category=f['category'],question=f['questions'][0],answers=f['answers'],split='russia_familiar'))
    held_keys={key(r['question']) for r in test}
    assert len(held_keys)==1000
    assert not held_keys.intersection(seen | {key(r['question']) for r in train})
    # Retain earlier skills while new Russian facts receive their own sampling
    # mass in train2. The preceding stage's holdouts stay untrained.
    replay=read_rows(ROOT/'data/improved/train.jsonl')
    train+=replay
    validation=test+read_rows(ROOT/'data/improved/test.jsonl')
    rng=random.Random(42)
    control=familiar+rng.sample(test,200)
    smoke=[familiar[0],dict(test[0],split='russia_unseen')]
    for category in ('россия: регионы','россия: города','россия: реки','россия: биографии','россия: литература','россия: музеи'):
        row=next((r for r in familiar if r['category']==category),None)
        if row:smoke.append(row)
    smoke+=read_rows(ROOT/'data/improved/user-regressions.jsonl')[:4]
    smoke+=read_rows(ROOT/'data/improved/user-regressions.jsonl')[-2:]
    hashes={}
    for name,rows in [('facts',accepted),('train',train),('test',test),('validation',validation),('familiar',familiar),('control',control),('smoke',smoke)]:
        path=OUT/(name+'.jsonl')
        path.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
        hashes[name]=hashlib.sha256(path.read_bytes()).hexdigest()
    readable='1000 фактов о России. Срез источников: 24 ноября 2026 года.\n\n'
    readable+='\n\n'.join('%04d. %s\nОтвет: %s\nИсточник: %s'%(i,f['questions'][0],f['answers'][0],f['source']) for i,f in enumerate(accepted,1))+'\n'
    (OUT/'facts.txt').write_text(readable,encoding='utf-8')
    manifest=dict(seed=42,facts=len(accepted),train=len(train),new_train=len(train)-len(replay),
                  categories=dict(collections.Counter(f['category'] for f in accepted)),source_pool={k:len(v) for k,v in pools.items()},
                  rejected=dict(rejected),sha256=hashes,vocab_sha256=FINGERPRINT,checked_on='2026-11-24',
                  source_license='Wikidata structured data CC0-1.0; original factual questions MIT',
                  scope='1000 subject/property facts; variants and arithmetic replay are not counted as new facts',
                  evaluation='Known facts, held-out wording; not unseen factual knowledge. Structured imports are not a full independent audit.')
    (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(manifest,ensure_ascii=False,indent=2))


if __name__=='__main__':build()
