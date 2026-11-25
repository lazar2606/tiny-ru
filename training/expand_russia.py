"""Vary natural question forms; hold one unseen form per known fact."""
import collections
import hashlib
import json
import random
from pathlib import Path
from gen_improved import key
from gen_russia import person_name
from tokenizer import encode

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/russia-expanded'
read=lambda p:[json.loads(s) for s in (ROOT/p).read_text(encoding='utf-8').splitlines()]


def build():
    facts=read('data/russia/facts.jsonl')
    prior=read('data/train.jsonl')+read('data/improved/train.jsonl')+read('data/russia/train.jsonl')
    seen={key(r['question']) for r in prior}
    sexes=json.loads((ROOT/'data/russia/sources/genders.json').read_text(encoding='utf-8'))['results']['bindings']
    female={r['item']['value'] for r in sexes if r['sex']['value'].endswith('/Q6581072')}
    people={f['subject']:person_name(f['subject_label']) for f in facts if f['category']=='россия: биографии'}
    surnames=collections.Counter(n.split()[-1] for n in people.values())
    rng=random.Random(42)
    train=[]; test=[]; familiar=[]
    for f in facts:
        s=f.get('subject_label',f['subject'])
        prop=f['property']
        choices=[f['held_question']]
        if prop=='P36':
            choices += [f'назови центр региона "{s}".',f'административный центр региона "{s}"?',f'какая столица у региона "{s}"?']
        elif prop=='P571':
            choices += [f'когда основали город {s}?',f'назови год основания города {s}.',f'год основания города {s}?']
        elif prop=='P206':
            choices += [f'назови водоём у города {s}.',f'город {s} находится на каком водоёме?',f'какой водоём рядом с городом {s}?']
        elif prop=='P403':
            choices += [f'в какой водоём впадает река {s}?',f'река {s} куда впадает?',f'куда несёт воды река {s}?']
        elif prop in ('P569','P570','P19'):
            p=people[f['subject']]
            born='родилась' if f['subject'] in female else 'родился'
            died='умерла' if f['subject'] in female else 'умер'
            names=[p]
            if surnames[p.split()[-1]]==1:names.append(p.split()[-1])
            for n in names:
                if prop=='P569':choices += [f'в каком году {born} {n}?',f'когда {born} {n}, в каком году?',f'каков год рождения: {n}?']
                elif prop=='P570':choices += [f'в каком году {died} {n}?',f'когда {died} {n}, в каком году?',f'каков год смерти: {n}?']
                else:choices += [f'где {born} {n}?',f'откуда родом {n}?',f'какое место рождения у человека по имени {n}?']
        elif prop=='P50':
            choices += [f'кто написал произведение "{s}"?',f'автор произведения "{s}"?',f'назови автора "{s}".']
        elif prop=='P577':
            choices += [f'когда вышло произведение "{s}", в каком году?',f'в каком году вышло "{s}"?',f'назови год публикации "{s}".']
        elif prop=='P131':
            choices += [f'в каком месте расположен "{s}"?',f'где можно найти "{s}"?',f'назови место, где находится "{s}".']
        valid=[]
        for q in choices:
            if len(encode(q,strict=True))<=72 and all(len(encode(q+'\n'+a+'\n'))<=128 for a in f['answers']):
                if q not in valid:valid.append(q)
        never_seen=[q for q in valid if key(q) not in seen]
        if not never_seen:raise ValueError('No unseen form for '+f['id'])
        held=rng.choice(never_seen)
        # Select a whole wording before generating quote/punctuation variants.
        qkey=lambda q:key(q.replace('"',''))
        questions=[q for q in f['questions']+valid if qkey(q)!=qkey(held)]
        questions+= [q.replace('"','') for q in questions if '"' in q]
        questions=list(dict.fromkeys(questions))
        for q in questions:
            for a in f['answers'][:2]:train.append(dict(fact_id=f['id'],category=f['category'],question=q,answer=a,sample_weight=f.get('sample_weight',1)))
        f['expanded_questions']=questions
        f['expanded_held_question']=held
        test.append(dict(fact_id=f['id'],category=f['category'],question=held,answers=f['answers'],split='russia_unseen'))
        familiar.append(dict(fact_id=f['id'],category=f['category'],question=f['questions'][0],answers=f['answers'],split='russia_familiar'))
    replay=read('data/improved/train.jsonl')
    train+=replay
    unique={}
    for row in train:unique.setdefault((key(row['question']),row['answer']),row)
    train=list(unique.values())
    heldkeys={key(r['question']) for r in test}
    assert len(heldkeys)==1000 and not heldkeys.intersection(seen | {key(r['question']) for r in train})
    validation=test+read('data/improved/test.jsonl')
    control=familiar+random.Random(1042).sample(test,200)
    # Keep the president's genuinely untrained new wording in DOS smoke.
    smoke=read('data/russia/smoke.jsonl')
    smoke[1]=test[0]
    OUT.mkdir(parents=True,exist_ok=True)
    hashes={}
    for name,rows in [('facts',facts),('train',train),('test',test),('validation',validation),('control',control),('smoke',smoke)]:
        path=OUT/(name+'.jsonl')
        path.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
        hashes[name]=hashlib.sha256(path.read_bytes()).hexdigest()
    manifest=dict(facts=1000,train=len(train),new_train=sum(r['category'].startswith('россия:') for r in train),
                  sha256=hashes,seed=42,source_facts='data/russia/facts.jsonl',
                  split='One randomly held wording per fact; excludes v2, r2 and first Russia stage.')
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(manifest,indent=2))


if __name__=='__main__':build()
