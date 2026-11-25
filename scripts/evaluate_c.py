"""Evaluate the actual C runtime, including its quantized KV caches."""
import argparse
import collections
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'training'))
from tokenizer import normalize,encode


def parse_output(path):
    raw=Path(path).read_bytes()
    text=raw.decode('cp866')
    return re.findall(r'\n>   ([^\r\n]*)\r?\n   \[',text)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--questions',type=Path,default=ROOT/'data/control.jsonl')
    p.add_argument('--prepare',type=Path)
    p.add_argument('--executable',type=Path)
    p.add_argument('--model-dir',type=Path,default=ROOT/'dos')
    p.add_argument('--transcript',type=Path)
    p.add_argument('--out',type=Path,default=ROOT/'reports/c-evaluation.json')
    args=p.parse_args()
    rows=[json.loads(s) for s in args.questions.read_text(encoding='utf-8').splitlines()]
    payload=('\r\n'.join(normalize(r['question']) for r in rows)+'\r\nquit\r\n').encode('cp866')
    if any(len(encode(r['question']))>72 for r in rows):raise ValueError('C question limit exceeded')
    if args.prepare:
        args.prepare.parent.mkdir(parents=True,exist_ok=True)
        args.prepare.write_bytes(payload)
        print('Prepared',len(rows),'questions')
        return
    transcript=args.transcript or ROOT/'reports/native-output.cp866.txt'
    if args.executable:
        r=subprocess.run([str(args.executable.resolve()),'/P','0'],cwd=args.model_dir,input=payload,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=240)
        transcript.write_bytes(r.stdout)
        if r.returncode:raise RuntimeError(r.stderr.decode(errors='replace'))
    answers=parse_output(transcript)
    if len(answers)!=len(rows):raise ValueError('Expected %d answers, got %d'%(len(rows),len(answers)))
    counts=collections.defaultdict(lambda:[0,0])
    details=[]
    canonical=lambda s:normalize(s).strip().rstrip('.!?').strip()
    for row,answer in zip(rows,answers):
        ok=canonical(answer) in {canonical(a) for a in row['answers']}
        counts[row['split']][0]+=int(ok)
        counts[row['split']][1]+=1
        encode(answer,strict=True)
        terminated=len(answer)<128-len(encode(row['question']))-1
        details.append(dict(row,answer=answer,correct=ok,terminated=terminated))
    result=dict(total=len(rows),metrics={k:dict(correct=a,total=b,accuracy=a/b) for k,(a,b) in counts.items()},invalid_tokens=0,unterminated=sum(not r['terminated'] for r in details),examples=details,weights_sha256=hashlib.sha256((args.model_dir/'TINY.BIN').read_bytes()).hexdigest())
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result['metrics'],ensure_ascii=False,indent=2))


if __name__=='__main__':main()
