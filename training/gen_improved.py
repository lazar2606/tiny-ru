"""Richer wording and explicit user regressions; baseline data stays immutable."""
import collections
import hashlib
import json
import random
from pathlib import Path
from gen_ru import facts as baseline_facts
from tokenizer import encode, normalize, FINGERPRINT

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/improved'
TECH={
 'сколько бит в байте?':'один байт содержит сколько бит?',
 'что делает процессор?':'какова задача процессора?',
 'для чего нужна клавиатура?':'зачем нужна клавиатура?',
 'для чего нужен монитор?':'зачем используют монитор?',
 'для чего нужен принтер?':'какова функция принтера?',
 'для чего нужен микрофон?':'какую задачу выполняет микрофон?',
 'для чего нужны колонки?':'зачем нужны звуковые колонки?',
 'для чего нужен сканер?':'какова задача сканера?',
 'что хранится в файле?':'какую информацию содержит файл?',
 'какие цифры в двоичной системе?':'из каких цифр состоят двоичные числа?',
 'что означает dos?':'что означает аббревиатура dos?',
 'что делает команда dir в dos?':'для чего используют команду dir?',
 'что делает команда cls в dos?':'как действует команда cls?',
 'что делает команда cd в dos?':'какую операцию выполняет команда cd?',
}


def key(q):
    return ' '.join(normalize(q).split()).rstrip('.!? ')


def prepare(seed=42):
    rng=random.Random(seed)
    facts=baseline_facts()
    baseline_rows=[json.loads(s) for s in (ROOT/'data/train.jsonl').read_text(encoding='utf-8').splitlines()]
    previously_trained={key(r['question']) for r in baseline_rows}
    additions=[
        ('chat-status',['как дела?','как у тебя дела?','как твои дела?'],'как у тебя идут дела?','всё хорошо'),
        ('chat-hello-status',['привет как дела?','привет, как дела?'],'здравствуй, как поживаешь?','привет, всё хорошо'),
        ('chat-capability',['что ты умеешь?','что ты можешь?'],'для каких задач ты подходишь?','отвечать на простые вопросы'),
    ]
    for ident,questions,held,answer in additions:
        facts.append(dict(id=ident,category='разговор',questions=questions,answers=[answer,answer+'.'],verification='original-dialogue',held_question=held))
    for f in facts:
        a=f['answers'][0]
        f['answers']=[r for r in f['answers'] if not r.startswith('ответ: ')]
        original=f['questions']
        first=original[0]
        if 'held_question' in f:
            train=original[:]
            held=f['held_question']
        elif f['category']=='география' and first.startswith('как называется столица '):
            country=first[len('как называется столица '):].rstrip('?')
            core=original+['какая столица '+country+'?','столица '+country+'?']
            extra=['назови столицу '+country+'.','какой город является столицей '+country+'?','какая у '+country+' столица?']
            held=rng.choice(extra)
            train=core+[q for q in extra if q!=held]
        elif 'expression' in f:
            x,op,y=f['expression']
            expression='%d%s%d'%(x,op,y)
            core=original+[expression,'сколько будет %d %s %d?'%(x,op,y)]
            if op in ('+','*') and x!=y:core+=['сколько будет %d%s%d?'%(y,op,x)]
            extra=['чему равно '+expression+'?','посчитай '+expression+'.','реши пример '+expression+'.']
            held=rng.choice(extra)
            train=core+[q for q in extra if q!=held]
            f['answers']=[a,a+'.','получится '+a+'.']
            f['sample_weight']=4 if max(x,y)<=9 else 1
        elif first in TECH:
            train=original[:]
            held=TECH[first]
        elif first=='привет!':
            train=original+['hi','hello','добрый день!','добрый вечер!']
            held='доброго дня!'
        elif f['verification']=='unavailable-personal-information':
            train=original[:]
            held='ты знаешь '+original[1][len('назови '):].rstrip('.')+'?'
        else:
            chosen=rng.randrange(2)
            train=[original[chosen],'скажи: '+original[chosen]]
            held=original[1-chosen]
        # A warm start has already seen some original forms. Do not label them
        # as unseen. Prefix-only holdouts are explicitly marked in the report.
        f['holdout_kind']='new_prefix' if f['verification']=='invalid-premise' else 'semantic_paraphrase'
        if key(held) in previously_trained:
            held='уточни: '+held
            f['holdout_kind']='new_prefix'
        f['train_questions']=list(dict.fromkeys(train))
        f['held_question']=held
    held_keys={key(f['held_question']) for f in facts}
    train=[]
    test=[]
    for f in facts:
        for q in f['train_questions']:
            if key(q) in held_keys:raise ValueError('Held wording leaked: '+q)
            for a in f['answers']:
                train.append(dict(fact_id=f['id'],category=f['category'],question=q,answer=a,sample_weight=f.get('sample_weight',1)))
        test.append(dict(fact_id=f['id'],category=f['category'],question=f['held_question'],answers=f['answers'],split='paraphrase',holdout_kind=f['holdout_kind']))
    # New control set: old controls are used only as regression checks.
    rng=random.Random(seed+1000)
    factual=[f for f in facts if f['category'] not in ('арифметика','неизвестное')]
    control=[]
    for split in ('familiar','paraphrase'):
        for f in rng.sample(factual,40):
            q=f['train_questions'][0] if split=='familiar' else f['held_question']
            control.append(dict(fact_id=f['id'],category=f['category'],question=q,answers=f['answers'],split=split,holdout_kind=f['holdout_kind'] if split=='paraphrase' else 'trained'))
    for category,count in [('арифметика',30),('неизвестное',15)]:
        for f in rng.sample([f for f in facts if f['category']==category],count):
            control.append(dict(fact_id=f['id'],category=category,question=f['held_question'],answers=f['answers'],split=category,holdout_kind=f['holdout_kind']))
    candidates=[f for f in factual if any(c in f['train_questions'][0]+f['answers'][0] for c in 'ёйъь')]
    special=[]
    for letter in 'ёйъь':
        f=next(f for f in candidates if letter in f['train_questions'][0]+f['answers'][0] and f not in special)
        special.append(f)
    special+= [f for f in candidates if f not in special][:15-len(special)]
    for f in special:control.append(dict(fact_id=f['id'],category=f['category'],question=f['train_questions'][0],answers=f['answers'],split='special_letters'))
    regressions=[
        ('Hi',['привет','привет.']),
        ('привет как дела?',['привет, всё хорошо','привет, всё хорошо.']),
        ('Привет, как дела',['привет, всё хорошо','привет, всё хорошо.']),
        ('Какая столица России?',['москва','москва.','столица россии - москва.']),
        ('какая столица россии',['москва','москва.','столица россии - москва.']),
        ('сколько будет 2+2',['4','4.','получится 4.']),
        ('сколько будет 2 + 2?',['4','4.','получится 4.']),
        ('2+2',['4','4.','получится 4.']),
    ]
    user=[dict(question=q,answers=refs,category='user_regression',split='user_regression') for q,refs in regressions]
    for row in train+test+control+user:
        answers=[row['answer']] if 'answer' in row else row['answers']
        if len(encode(row['question'],strict=True))>72:raise ValueError('DOS question overflow: '+row['question'])
        for a in answers:
            if len(encode(row['question']+'\n'+a+'\n',strict=True))>128:raise ValueError('Context overflow')
    pairs=[(normalize(r['question']),normalize(r['answer'])) for r in train]
    if len(pairs)!=len(set(pairs)):raise ValueError('Duplicate training pair')
    return facts,train,test,control,user


def build():
    OUT.mkdir(parents=True,exist_ok=True)
    facts,train,test,control,user=prepare()
    hashes={}
    for name,rows in [('facts',facts),('train',train),('test',test),('control',control),('user-regressions',user)]:
        p=OUT/(name+'.jsonl')
        p.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
        hashes[name]=hashlib.sha256(p.read_bytes()).hexdigest()
    manifest=dict(seed=42,vocab_sha256=FINGERPRINT,facts=len(facts),train=len(train),test=len(test),control=len(control),user_regressions=len(user),categories=dict(collections.Counter(f['category'] for f in facts)),sha256=hashes,license='MIT',note='Original control is now a regression set; use improved/control for held-out wording. User examples are deliberately trained regressions.')
    (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(manifest,ensure_ascii=False,indent=2))


if __name__=='__main__':build()
