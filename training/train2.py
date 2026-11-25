"""Reproducible Russian training, strict TNY2 reader, evaluation and export."""
import argparse
import collections
import hashlib
import json
import math
import random
import struct
import time
from pathlib import Path
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from model import Cfg, Model, CTX, export
from tokenizer import encode, decode, normalize, VOCAB, FINGERPRINT

ROOT = Path(__file__).resolve().parents[1]


def read_rows(path):
    return [json.loads(s) for s in Path(path).read_text(encoding='utf-8').splitlines() if s.strip()]


def sequence(row):
    if any(c in row['question']+row['answer'] for c in '\r\n'):
        raise ValueError('Embedded line break in question or answer')
    q = encode(row['question'], strict=True)
    a = encode(row['answer'], strict=True)
    if 1 in q or 1 in a:raise ValueError('Embedded newline in question or answer')
    ids = q + [1] + a + [1]
    if len(ids) > CTX:
        raise ValueError('Question + answer exceeds context: %s' % row['question'])
    return ids, [0] * (len(q)+1) + [1] * (len(a)+1)


def make_batch(rows):
    seqs = [sequence(r) for r in rows]
    n = max(len(s) for s,_ in seqs)
    x = torch.zeros(len(rows), n, dtype=torch.long)
    mask = torch.zeros_like(x, dtype=torch.float32)
    for i,(s,k) in enumerate(seqs):
        x[i,:len(s)] = torch.tensor(s)
        mask[i,:len(k)] = torch.tensor(k)
    return x,mask


def loss_fn(model, x, mask, question_weight=0, per_example=False):
    logits=model(x[:,:-1])
    l=F.cross_entropy(logits.reshape(-1,VOCAB), x[:,1:].reshape(-1),reduction='none')
    w=(mask[:,1:]+question_weight*(1-mask[:,1:])*(x[:,1:]!=0)).reshape(-1)
    if per_example:
        weighted=(l*w).reshape(x.shape[0],-1)
        weights=w.reshape(x.shape[0],-1)
        return (weighted.sum(1)/weights.sum(1).clamp_min(1)).mean()
    return (l*w).sum()/w.sum()


def load_bin(path):
    data=Path(path).read_bytes()
    if data[:12] != b'TNY2'+struct.pack('<4h',96,4,4,256):
        raise ValueError('Not a Tiny-RU 96/4/4/256 TNY2 model')
    m=Model(Cfg())
    offset=12
    sd=m.state_dict()
    names=['emb.weight','pos.weight']
    for i in range(4):
        prefix='blocks.%d.' % i
        names += [prefix+'n1.g']+[prefix+n+'.weight' for n in 'qkvo']+[prefix+'n2.g',prefix+'f1.weight',prefix+'f2.weight']
    names += ['nf.g']
    for name in names:
        p=sd[name]
        if p.ndim==2:
            r,c=p.shape
            values=[]
            for _ in range(r):
                if offset+4+c>len(data):
                    raise ValueError('Truncated table')
                scale=struct.unpack_from('<f',data,offset)[0]
                if not math.isfinite(scale) or scale<=0:
                    raise ValueError('Invalid scale')
                values.append(np.frombuffer(data,np.int8,c,offset+4).astype(np.float32)*scale)
                offset+=4+c
            sd[name]=torch.tensor(np.array(values))
        else:
            count=p.numel()
            if offset+count*4>len(data):
                raise ValueError('Truncated gains')
            sd[name]=torch.tensor(np.frombuffer(data,'<f4',count,offset).copy())
            if not torch.isfinite(sd[name]).all():
                raise ValueError('Invalid gains')
            offset+=count*4
    if offset!=len(data):
        raise ValueError('Trailing bytes')
    m.load_state_dict(sd)
    return m


def load_checkpoint(path):
    # Only load trusted checkpoints; serialized tensors, optimizer, RNG state.
    ck=torch.load(path,map_location='cpu',weights_only=False)
    if ck.get('vocab_sha256')!=FINGERPRINT:
        raise ValueError('Tokenizer mismatch; English checkpoints are incompatible')
    if ck['cfg']!=vars(Cfg()):
        raise ValueError('MVP architecture must be 96/4/4/256')
    m=Model(Cfg(**ck['cfg']))
    m.load_state_dict(ck['sd'])
    return m,ck


def load_model(path):
    return load_bin(path) if str(path).lower().endswith('.bin') else load_checkpoint(path)[0]


@torch.no_grad()
def answer_many(model, questions, max_new=64):
    was_training=model.training
    model.eval()
    groups=collections.defaultdict(list)
    for q in dict.fromkeys(questions):
        if '\r' in q or '\n' in q:raise ValueError('Question must be one line')
        ids=encode(q)+[1]
        if len(ids)>=CTX:
            raise ValueError('Question leaves no answer context')
        groups[len(ids)].append((q,ids))
    result={}
    for n,group in groups.items():
        for start in range(0,len(group),64):
            block=group[start:start+64]
            x=torch.tensor([ids for _,ids in block])
            outputs=[[] for _ in block]
            finished=[False]*len(block)
            for _ in range(min(max_new,CTX-n)):
                logits=model(x)[:,-1]
                logits[:,0]=-float('inf')
                nxt=logits.argmax(-1)
                for i,t in enumerate(nxt.tolist()):
                    if not finished[i]:
                        if t==1:
                            finished[i]=True
                        else:
                            outputs[i].append(t)
                if all(finished):
                    break
                x=torch.cat([x,nxt[:,None]],1)
            for (q,_),ids,done in zip(block,outputs,finished):
                result[q]=dict(answer=decode(ids),terminated=done,invalid_tokens=0)
    model.train(was_training)
    return result


def canonical(s):
    return normalize(s).strip().rstrip('.!?').strip()


def evaluate(model, rows):
    generated=answer_many(model,[r['question'] for r in rows])
    counts=collections.defaultdict(lambda:[0,0])
    details=[]
    for r in rows:
        got=generated[r['question']]
        ok=canonical(got['answer']) in {canonical(a) for a in r['answers']}
        group=r.get('split',r['category'])
        counts[group][0]+=int(ok)
        counts[group][1]+=1
        details.append(dict(r,**got,correct=ok))
    return dict(metrics={k:dict(correct=a,total=b,accuracy=a/b) for k,(a,b) in counts.items()}, total=len(rows), invalid_tokens=sum(r['invalid_tokens'] for r in details), unterminated=sum(not r['terminated'] for r in details), examples=details)


def save_json(path,data):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def train(args):
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    random.seed(args.seed)
    torch.use_deterministic_algorithms(True)
    rows=read_rows(args.data)
    for r in rows:
        sequence(r)
    data_hash=hashlib.sha256(Path(args.data).read_bytes()).hexdigest()
    # Equal sampling mass for categories prevents arithmetic from dominating.
    categories=collections.defaultdict(list)
    for r in rows:
        categories[r['category']].append(r)
    groups=list(categories.values())
    focus_prefix=getattr(args,'focus_prefix',None)
    focus_probability=getattr(args,'focus_probability',None)
    focused=[r for r in rows if focus_prefix and r['category'].startswith(focus_prefix)]
    unfocused=[g for g in groups if not focus_prefix or not g[0]['category'].startswith(focus_prefix)]
    focus_weights=[]
    total_weight=0
    for row in focused:
        total_weight+=float(row.get('sample_weight',1))
        focus_weights.append(total_weight)
    if focus_probability is not None:
        if not 0<=focus_probability<=1 or not focused or not unfocused:
            raise ValueError('Focus sampling needs a valid probability and both domains')
        if getattr(args,'arithmetic_probability',None) is not None:
            raise ValueError('Choose either focus or arithmetic sampling')
    cumulative={}
    for name,items in categories.items():
        if any('sample_weight' in r for r in items):
            total=0
            cumulative[name]=[]
            for r in items:
                weight=float(r.get('sample_weight',1))
                if not math.isfinite(weight) or weight<=0:raise ValueError('Invalid sample weight')
                total+=weight
                cumulative[name].append(total)
    arithmetic=categories.get('арифметика')
    non_arithmetic=[g for g in groups if g[0]['category']!='арифметика']
    rng=random.Random(args.seed)
    model=Model(Cfg())
    if args.init:
        model=load_model(args.init)
    opt=torch.optim.AdamW(model.parameters(),lr=args.lr,betas=(0.9,0.98),weight_decay=0.01)
    start=0
    if args.resume:
        model,ck=load_checkpoint(args.resume)
        if ck['data_sha256']!=data_hash:
            raise ValueError('Training data changed; use a new run')
        if ck['run']['steps']!=args.steps:
            raise ValueError('Resume requires the same target --steps for LR continuity')
        defaults=dict(loss_per_example=False,arithmetic_probability=None,no_curriculum=False,augment_format=False,focus_prefix=None,focus_probability=None)
        for key in ('seed','lr','batch_size','augment_prefixes','question_weight','loss_per_example','arithmetic_probability','no_curriculum','augment_format','focus_prefix','focus_probability'):
            if ck['run'].get(key,defaults.get(key,False))!=getattr(args,key,defaults.get(key,False)):
                raise ValueError('Resume requires unchanged %s; use --init for a new run' % key)
        opt=torch.optim.AdamW(model.parameters(),lr=args.lr,betas=(0.9,0.98),weight_decay=0.01)
        opt.load_state_dict(ck['optimizer'])
        start=ck['step']
        rng.setstate(ck['rng'])
        torch.set_rng_state(ck['torch_rng'])
    validation=read_rows(args.validation)
    held_questions={canonical(r['question']) for r in validation}
    # This validation subset is distinct from the final 140 control questions.
    final_q={r['question'] for r in read_rows(getattr(args,'control',ROOT/'data/control.jsonl'))}
    validation=[r for r in validation if r['question'] not in final_q and r['category']!='арифметика'][:24]
    # Fixed teacher-forced validation data; does not consume training RNG.
    vx,vm=make_batch([dict(question=r['question'],answer=r['answers'][0]) for r in validation])
    t0=time.monotonic()
    running=None
    output=Path(args.out)
    output.parent.mkdir(parents=True,exist_ok=True)
    logpath=output.with_suffix('.jsonl')
    print('parameters',sum(p.numel() for p in model.parameters()),'threads',args.threads,flush=True)
    def save(step):
        state=dict(cfg=vars(model.c),sd=model.state_dict(),vocab_sha256=FINGERPRINT,data_sha256=data_hash,optimizer=opt.state_dict(),step=step,rng=rng.getstate(),torch_rng=torch.get_rng_state(),run=vars(args).copy())
        for k,v in state['run'].items():
            if isinstance(v,Path):state['run'][k]=str(v)
        tmp=output.with_suffix('.tmp')
        torch.save(state,tmp)
        tmp.replace(output)
    for step in range(start,args.steps):
        if args.stop_after and step>=args.stop_after:
            save(step)
            return
        if args.max_seconds and time.monotonic()-t0>args.max_seconds:
            save(step)
            print('time limit reached; checkpoint saved',flush=True)
            return
        # Two-stage curriculum first learns language/encyclopedic QA, then arithmetic.
        chosen=[]
        for _ in range(args.batch_size):
            if focus_probability is not None and rng.random()<focus_probability:
                selected=rng.choices(focused,cum_weights=focus_weights,k=1)[0]
                group=None
            elif focus_probability is not None:
                group=rng.choice(unfocused)
            else:
                group=None
            probability=getattr(args,'arithmetic_probability',None)
            if focus_probability is not None:
                pass
            elif probability is None:
                group=rng.choice(groups)
            else:
                if not arithmetic or not non_arithmetic:raise ValueError('Arithmetic mixing needs both kinds of data')
                group=arithmetic if rng.random()<probability else rng.choice(non_arithmetic)
            if group is not None and not getattr(args,'no_curriculum',False) and step<args.steps//3 and group[0]['category']=='арифметика':
                group=rng.choice([g for g in groups if g[0]['category']!='арифметика'])
            if group is not None:
                name=group[0]['category']
                selected=rng.choices(group,cum_weights=cumulative[name],k=1)[0] if name in cumulative else rng.choice(group)
            row=dict(selected)
            if getattr(args,'augment_format',False):
                q=row['question'].rstrip('.!? ')
                q=q+rng.choice(['','?','.'])
                if canonical(q) not in held_questions:row['question']=q
            if args.augment_prefixes:
                q=row['question']
                if q.startswith('скажи: '):q=q[7:]
                q=rng.choice(['','а ','ну, ','скажи: ','подскажи: ','пожалуйста, ','дай ответ: ','ответь мне: ','мой вопрос: '])+q
                if canonical(q) not in held_questions and len(encode(q))<=72 and len(encode(q+'\n'+row['answer']+'\n'))<=CTX:
                    row['question']=q
            chosen.append(row)
        x,mask=make_batch(chosen)
        lr=args.lr*min(1,(step+1)/100)*(0.1+0.9*0.5*(1+math.cos(math.pi*step/args.steps)))
        for g in opt.param_groups:g['lr']=lr
        model.train()
        loss=loss_fn(model,x,mask,args.question_weight,getattr(args,'loss_per_example',False))
        if not torch.isfinite(loss):raise ValueError('Nonfinite loss')
        opt.zero_grad(set_to_none=True)
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(),1)
        opt.step()
        running=loss.item() if running is None else .98*running+.02*loss.item()
        if (step+1)%args.log_every==0 or step==start:
            model.eval()
            with torch.no_grad():vl=float(loss_fn(model,vx,vm))
            row=dict(step=step+1,seconds=time.monotonic()-t0,loss=running,validation_loss=vl,lr=lr)
            with logpath.open('a',encoding='utf-8') as f:f.write(json.dumps(row)+'\n')
            print(json.dumps(row),flush=True)
        if (step+1)%args.save_every==0:save(step+1)
    save(args.steps)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--threads',type=int,default=2)
    sub=p.add_subparsers(dest='command',required=True)
    t=sub.add_parser('train')
    t.add_argument('--data',type=Path,default=ROOT/'data/train.jsonl')
    t.add_argument('--validation',type=Path,default=ROOT/'data/test.jsonl')
    t.add_argument('--control',type=Path,default=ROOT/'data/control.jsonl')
    t.add_argument('--out',type=Path,default=ROOT/'training/release.pt')
    initial=t.add_mutually_exclusive_group()
    initial.add_argument('--resume',type=Path)
    initial.add_argument('--init',type=Path,help='New optimizer/run initialized from a Russian checkpoint')
    t.add_argument('--augment-prefixes',action='store_true')
    t.add_argument('--question-weight',type=float,default=0,help='Optional auxiliary next-character loss on questions')
    t.add_argument('--loss-per-example',action='store_true',help='Equal loss weight for short and long answers')
    t.add_argument('--arithmetic-probability',type=float,default=None)
    t.add_argument('--focus-prefix',default=None,help='Category prefix for a new training domain')
    t.add_argument('--focus-probability',type=float,default=None,help='Sampling mass for that domain; remaining mass rehearses old categories')
    t.add_argument('--no-curriculum',action='store_true')
    t.add_argument('--augment-format',action='store_true',help='Vary terminal question punctuation')
    t.add_argument('--steps',type=int,default=5000)
    t.add_argument('--seed',type=int,default=42)
    t.add_argument('--lr',type=float,default=0.002)
    t.add_argument('--batch-size',type=int,default=32)
    t.add_argument('--log-every',type=int,default=100)
    t.add_argument('--save-every',type=int,default=500)
    t.add_argument('--max-seconds',type=float,default=0)
    t.add_argument('--stop-after',type=int,default=0,help='Pause after an absolute step, keeping the original LR schedule')
    e=sub.add_parser('eval')
    e.add_argument('model',type=Path)
    e.add_argument('--questions',type=Path,default=ROOT/'data/control.jsonl')
    e.add_argument('--out',type=Path,default=ROOT/'reports/evaluation.json')
    x=sub.add_parser('export')
    x.add_argument('model',type=Path)
    x.add_argument('out',type=Path)
    a=sub.add_parser('ask')
    a.add_argument('model',type=Path)
    a.add_argument('question')
    args=p.parse_args()
    if args.threads<1:p.error('--threads must be positive')
    if args.command=='train' and (args.steps<1 or args.batch_size<1 or args.log_every<1 or args.save_every<1 or args.lr<=0):
        p.error('steps, batch size, log/save intervals and LR must be positive')
    if args.command=='train' and args.arithmetic_probability is not None and not 0<=args.arithmetic_probability<=1:
        p.error('--arithmetic-probability must be between 0 and 1')
    torch.set_num_threads(args.threads)
    if args.command=='train':train(args)
    elif args.command=='export':
        m=load_model(args.model)
        print('bytes',export(m,args.out))
        load_bin(args.out)
        save_json(str(args.out)+'.json',dict(vocab_sha256=FINGERPRINT,sha256=hashlib.sha256(args.out.read_bytes()).hexdigest(),architecture=vars(m.c)))
    elif args.command=='eval':
        r=evaluate(load_model(args.model),read_rows(args.questions))
        save_json(args.out,r)
        print(json.dumps({k:v for k,v in r.items() if k!='examples'},ensure_ascii=False,indent=2))
    else:print(answer_many(load_model(args.model),[args.question])[args.question]['answer'])


if __name__=='__main__':main()
