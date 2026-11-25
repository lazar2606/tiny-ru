import json
import random
import re
import struct
import subprocess
import sys
import tempfile
import unittest
import argparse
import contextlib
import io
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'training'))
import tokenizer as tok
import gen_ru
import torch
from model import Model,Cfg,export,quantized_copy
from train2 import sequence,load_bin,load_checkpoint,make_batch,loss_fn,train

torch.set_num_threads(2)


class TokenTests(unittest.TestCase):
    def test_alphabet_roundtrip(self):
        s='Съешь ещё этих мягких французских булок, да выпей чаю!'
        self.assertEqual(tok.decode(tok.encode(s)),s.lower())
        self.assertEqual(tok.decode(tok.encode(tok.CHARS)),tok.CHARS)
        self.assertEqual(tok.VOCAB,97)

    def test_unknown_and_range(self):
        self.assertEqual(tok.encode('🙂'),[tok.UNK])
        with self.assertRaises(ValueError):tok.encode('🙂',strict=True)
        with self.assertRaises(ValueError):tok.decode([97])
        with self.assertRaises(ValueError):tok.decode([-1])

    def test_header_matches_and_all_bytes_safe(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'VOCAB.H'
            tok.generate_header(path)
            self.assertEqual(path.read_bytes(),(ROOT/'dos/VOCAB.H').read_bytes())
        text=(ROOT/'dos/VOCAB.H').read_text()
        match=re.search(r'ru_cp_to_id\[256\] = \{(.*?)\};',text,re.S)
        values=list(map(int,re.findall(r'\d+',match.group(1))))
        self.assertEqual(len(values),256)
        self.assertTrue(all(0<=v<97 for v in values))
        for c in tok.CHARS:
            self.assertEqual(values[c.encode('cp866')[0]],tok.TO_ID[c])
            self.assertEqual(values[c.upper().encode('cp866')[0]],tok.TO_ID[c])
        for b in range(32,256):
            self.assertEqual(values[b],tok.encode(bytes([b]).decode('cp866'))[0])


class DatasetTests(unittest.TestCase):
    def test_dataset_and_split(self):
        facts=gen_ru.facts()
        self.assertGreaterEqual(len(facts),1000)
        expressions=set()
        for f in facts:
            if 'expression' in f:
                x,op,y=f['expression']
                expected=x+y if op=='+' else x-y if op=='-' else x*y
                self.assertEqual(f['answers'][0],str(expected))
                key=(op,tuple(sorted([x,y])) if op in ('+','*') else (x,y))
                self.assertNotIn(key,expressions)
                expressions.add(key)
            for q in f['questions']:
                for a in f['answers']:sequence(dict(question=q,answer=a))
        with tempfile.TemporaryDirectory() as td:
            gen_ru.build(Path(td))
            for name in ('train.jsonl','test.jsonl','control.jsonl','manifest.json'):
                self.assertEqual((Path(td)/name).read_bytes(),(ROOT/'data'/name).read_bytes())
        control=[json.loads(s) for s in (ROOT/'data/control.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertGreaterEqual(len(control),100)
        questions=''.join(r['question'] for r in control)
        for c in 'ёйъь':self.assertIn(c,questions)
        manifest=json.loads((ROOT/'data/manifest.json').read_text(encoding='utf-8'))
        for counts in manifest['arithmetic_form_by_y_parity'].values():
            rate=counts['0']/sum(counts.values())
            self.assertTrue(.4<rate<.6)

    def test_no_silent_truncation(self):
        with self.assertRaises(ValueError):sequence(dict(question='я'*120,answer='я'*10))
        with self.assertRaises(ValueError):sequence(dict(question='я\nты',answer='да'))
        with self.assertRaises(ValueError):sequence(dict(question='я\rты',answer='да'))
        ids,mask=sequence(dict(question='ёж?',answer='да'))
        self.assertEqual(mask,[0]*4+[1]*3)
        self.assertEqual(tok.decode(ids),'ёж?\nда\n')


class ModelTests(unittest.TestCase):
    def test_per_example_loss_does_not_downweight_short_answers(self):
        class Fixed(torch.nn.Module):
            def forward(self,x):
                logits=torch.zeros(x.shape[0],x.shape[1],97)
                logits[1,:,2]=2
                return logits
        x=torch.full((2,4),2,dtype=torch.long)
        mask=torch.tensor([[0.,1.,0.,0.],[0.,1.,1.,1.]])
        expected=(torch.log(torch.tensor(97.))+torch.log(torch.exp(torch.tensor(2.))+96)-2)/2
        self.assertAlmostEqual(float(loss_fn(Fixed(),x,mask,per_example=True)),float(expected),places=5)
        self.assertGreater(float(loss_fn(Fixed(),x,mask,per_example=True)),float(loss_fn(Fixed(),x,mask)))
    def test_resume_matches_uninterrupted(self):
        with tempfile.TemporaryDirectory() as td:
            kwargs=dict(data=ROOT/'data/train.jsonl',validation=ROOT/'data/test.jsonl',seed=42,steps=4,batch_size=2,lr=.002,log_every=10,save_every=10,max_seconds=0,init=None,resume=None,augment_prefixes=False,threads=2,stop_after=0,question_weight=0)
            a=argparse.Namespace(**dict(kwargs,out=Path(td)/'full.pt'))
            b=argparse.Namespace(**dict(kwargs,out=Path(td)/'part.pt'))
            with contextlib.redirect_stdout(io.StringIO()):
                train(a)
                b.stop_after=2
                train(b)
                self.assertEqual(load_checkpoint(b.out)[1]['step'],2)
                b.resume=b.out
                b.stop_after=0
                train(b)
            first=load_checkpoint(a.out)[0].state_dict()
            second=load_checkpoint(b.out)[0].state_dict()
            for key in first:self.assertTrue(torch.equal(first[key],second[key]),key)

    def test_export_reload(self):
        torch.manual_seed(42)
        m=Model(Cfg())
        self.assertEqual(sum(p.numel() for p in m.parameters()),366528)
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'TINY.BIN'
            export(m,path)
            loaded=load_bin(path)
            quant=quantized_copy(m)
            for key,value in loaded.state_dict().items():
                self.assertTrue(torch.allclose(value,quant.state_dict()[key],atol=2e-7),key)
            for corrupted in [b'',path.read_bytes()[:-1],path.read_bytes()+b'x']:
                path.write_bytes(corrupted)
                with self.assertRaises(ValueError):load_bin(path)

    def test_forward_loss(self):
        m=Model(Cfg())
        x,mask=make_batch([dict(question='ёж?',answer='да'),dict(question='кто ты?',answer='тини')])
        loss=loss_fn(m,x,mask)
        self.assertTrue(torch.isfinite(loss))
        loss.backward()
        self.assertIsNotNone(m.emb.weight.grad)


if __name__=='__main__':unittest.main()
