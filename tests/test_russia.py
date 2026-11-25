import json
import argparse
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'training'))
from tokenizer import encode
from gen_improved import key
import torch
from train2 import train,load_checkpoint


def rows(path):
    return [json.loads(s) for s in (ROOT/path).read_text(encoding='utf-8').splitlines()]


class RussiaDataTests(unittest.TestCase):
    def test_expanded_forms_exclude_all_previous_stages(self):
        prior=rows('data/train.jsonl')+rows('data/improved/train.jsonl')+rows('data/russia/train.jsonl')
        train=rows('data/russia-expanded/train.jsonl')+rows('data/russia-calibration/train.jsonl')
        held=rows('data/russia-expanded/test.jsonl')
        self.assertEqual(len(held),1000)
        self.assertFalse({key(r['question']) for r in prior+train}.intersection(key(r['question']) for r in held))
        for r in train:
            self.assertLessEqual(len(encode(r['question'],strict=True)),72)
            self.assertLessEqual(len(encode(r['question']+'\n'+r['answer']+'\n',strict=True)),128)

    def test_thousand_distinct_relations_and_provenance(self):
        facts=rows('data/russia-final/facts.jsonl')
        self.assertEqual(len(facts),1000)
        self.assertEqual(len({(f['subject'],f['property']) for f in facts}),1000)
        self.assertGreaterEqual(len({f['category'] for f in facts}),8)
        self.assertTrue(all(f['source'].startswith('https://') and f['verified_on']=='2026-11-24' for f in facts))
        self.assertFalse(any('expression' in f or f['category']=='арифметика' for f in facts))
        president=next(f for f in facts if f['property']=='president')
        self.assertEqual(president['answers'][0],'владимир путин')
        self.assertTrue(president['time_sensitive'])

    def test_corrected_sources_and_final_holdouts(self):
        facts={f['id']:f for f in rows('data/russia-final/facts.jsonl')}
        self.assertEqual(facts['russia-0043']['answers'],['каспийское море','каспийское море.'])
        self.assertEqual(facts['russia-0106']['answers'],['куршский залив','куршский залив.'])
        self.assertIn('1900',facts['russia-0298']['questions'][0])
        self.assertEqual(facts['russia-0298']['answers'][0],'москва')
        self.assertTrue(all('музей' in q for q in facts['russia-0046']['questions']))
        previous=[]
        for p in ('data/train.jsonl','data/improved/train.jsonl','data/russia/train.jsonl',
                  'data/russia-expanded/train.jsonl','data/russia-calibration/train.jsonl','data/russia-final/train.jsonl'):
            previous+=rows(p)
        self.assertFalse({key(r['question']) for r in previous}.intersection(key(r['question']) for r in rows('data/russia-final/test.jsonl')))
        self.assertFalse(any(r.get('fact_id')=='russia-0043' and key(r['answer'])=='кама' for r in rows('data/russia-final/train.jsonl')))

    def test_first_stage_holdouts_and_dos_limits(self):
        train=rows('data/train.jsonl')+rows('data/improved/train.jsonl')+rows('data/russia/train.jsonl')
        held=rows('data/russia/test.jsonl')
        self.assertEqual(len(held),1000)
        self.assertFalse({key(r['question']) for r in train}.intersection(key(r['question']) for r in held))
        for f in rows('data/russia/facts.jsonl'):
            for q in f['questions']+[f['held_question']]:
                self.assertLessEqual(len(encode(q,strict=True)),72)
                for a in f['answers']:
                    self.assertLessEqual(len(encode(q+'\n'+a+'\n',strict=True)),128)

    def test_focus_training_resume_is_exact(self):
        with tempfile.TemporaryDirectory() as directory:
            config=dict(data=ROOT/'data/russia/train.jsonl',validation=ROOT/'data/russia/validation.jsonl',
                        control=ROOT/'data/russia/control.jsonl',seed=42,steps=4,batch_size=2,lr=.001,
                        log_every=10,save_every=10,max_seconds=0,init=None,resume=None,
                        augment_prefixes=False,question_weight=0,threads=2,stop_after=0,
                        loss_per_example=True,focus_prefix='россия:',focus_probability=.8,
                        arithmetic_probability=None,no_curriculum=True,augment_format=True)
            full=argparse.Namespace(**dict(config,out=Path(directory)/'full.pt'))
            part=argparse.Namespace(**dict(config,out=Path(directory)/'part.pt'))
            with contextlib.redirect_stdout(io.StringIO()):
                train(full)
                part.stop_after=2
                train(part)
                part.resume=part.out
                part.stop_after=0
                train(part)
            for name,tensor in load_checkpoint(full.out)[0].state_dict().items():
                self.assertTrue(torch.equal(tensor,load_checkpoint(part.out)[0].state_dict()[name]),name)


if __name__=='__main__':unittest.main()
