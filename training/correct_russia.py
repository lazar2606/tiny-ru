"""Curate ambiguous imported claims before the final release fine-tune."""
import hashlib
import json
from pathlib import Path
from gen_improved import key
from tokenizer import encode
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/russia-final'
read=lambda p:[json.loads(s) for s in (ROOT/p).read_text(encoding='utf-8').splitlines()]
FIXES={
 'russia-0043':('каспийское море','https://tatarica.org/ru/razdely/priroda/gidrograficheskaya-set/reki/volga'),
 'russia-0106':('куршский залив','https://www.klgd.ru/city/history/almanac/a6_58.php?print=Y'),
 'russia-0316':('самур','https://textual.ru/gvr/index.php?card=174028'),
}
HISTORICAL='russia-0298'
MUSEUM='russia-0046'
HISTORY_Q=['в каком городе находился румянцевский музей в 1900 году?',
           'где был румянцевский музей в 1900 году?',
           'в каком городе был румянцевский музей после переезда 1861 года?']
HISTORY_HELD='назови город румянцевского музея в 1900 году.'


def museum_q(q):return q.replace('"гатчина"','гатчина').replace('гатчина','музей "гатчина"')


def build():
    facts=read('data/russia-expanded/facts.jsonl')
    train=read('data/russia-calibration/train.jsonl')
    previous=read('data/train.jsonl')+read('data/improved/train.jsonl')+read('data/russia/train.jsonl')+read('data/russia-expanded/train.jsonl')+train
    by_id={f['id']:f for f in facts}
    for ident,(answer,source) in FIXES.items():
        f=by_id[ident]
        f['original_source']=f['source'];f['source']=source
        f['answers']=[answer,answer+'.']
        f['verification']='curated-after-ambiguous-import'
    f=by_id[HISTORICAL]
    f['original_source']=f['source']
    f.update(property='P131@1900',questions=HISTORY_Q[:2],expanded_questions=HISTORY_Q,
             expanded_held_question=HISTORY_HELD,held_question=HISTORY_HELD,
             answers=['москва','москва.'],source='https://www.rsl.ru/fondy-i-katalogi/fondy-spetsializirovannyh-otdelov/fond-rukopisey/otdel-rukopisey/moskovskiy-period/',
             verification='historical-location-disambiguated')
    f=by_id[MUSEUM]
    f['questions']=[museum_q(q) for q in f['questions']]
    f['expanded_questions']=[museum_q(q) for q in f['expanded_questions']]
    f['held_question']=museum_q(f['held_question'])
    f['expanded_held_question']=museum_q(f['expanded_held_question'])
    f['verification']='museum-disambiguated-from-city'
    corrected=[]
    for row in train:
        r=dict(row);ident=r.get('fact_id')
        if ident==HISTORICAL:continue
        if ident in FIXES:
            r['answer']=FIXES[ident][0]+('.' if r['answer'].endswith('.') else '')
            r['sample_weight']=15
        if ident==MUSEUM:
            r['question']=museum_q(r['question']);r['sample_weight']=10
        corrected.append(r)
    for q in HISTORY_Q:
        for a in by_id[HISTORICAL]['answers']:
            corrected.append(dict(fact_id=HISTORICAL,category=by_id[HISTORICAL]['category'],question=q,answer=a,sample_weight=15))
    unique={}
    for r in corrected:unique.setdefault((key(r['question']),r['answer']),r)
    train=list(unique.values())
    def update(row,held=False):
        r=dict(row);ident=r.get('fact_id')
        if ident in by_id:r['answers']=by_id[ident]['answers']
        if ident==MUSEUM:r['question']=museum_q(r['question'])
        if ident==HISTORICAL:r['question']=HISTORY_HELD if held else HISTORY_Q[0]
        return r
    test=[update(r,True) for r in read('data/russia-expanded/test.jsonl')]
    familiar=[update(r) for r in read('data/russia/familiar.jsonl')]
    control=[update(r,r['split']=='russia_unseen') for r in read('data/russia-expanded/control.jsonl')]
    smoke=[update(r,r['split']=='russia_unseen') for r in read('data/russia-expanded/smoke.jsonl')]
    heldkeys={key(r['question']) for r in test}
    assert len(facts)==len(heldkeys)==1000
    assert not heldkeys.intersection(key(r['question']) for r in previous+train)
    for r in train:
        assert len(encode(r['question'],strict=True))<=72
        assert len(encode(r['question']+'\n'+r['answer']+'\n',strict=True))<=128
    OUT.mkdir(parents=True,exist_ok=True)
    hashes={}
    for name,rows in [('facts',facts),('train',train),('test',test),('validation',test+read('data/improved/test.jsonl')),('familiar',familiar),('control',control),('smoke',smoke)]:
        p=OUT/(name+'.jsonl');p.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
        hashes[name]=hashlib.sha256(p.read_bytes()).hexdigest()
    (OUT/'facts.txt').write_text('1000 фактов о России. Проверено по источникам на 24.11.2026.\n\n'+'\n\n'.join('%04d. %s\nОтвет: %s\nИсточник: %s'%(i,f['questions'][0],f['answers'][0],f['source']) for i,f in enumerate(facts,1))+'\n',encoding='utf-8')
    manifest=dict(facts=1000,train=len(train),sha256=hashes,corrected_ids=list(FIXES)+[HISTORICAL,MUSEUM],
                  note='Raw multi-valued imports are historical snapshots, not final reference answers. Current source of truth is russia-final.')
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(manifest,indent=2))


if __name__=='__main__':build()
