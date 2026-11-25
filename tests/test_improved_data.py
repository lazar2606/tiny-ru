import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'training'))
from gen_improved import prepare,key
from train2 import read_rows


class ImprovedDataTests(unittest.TestCase):
    def test_unseen_questions_exclude_both_training_stages(self):
        facts,train,test,control,user=prepare()
        seen={key(r['question']) for r in read_rows(ROOT/'data/train.jsonl')+train}
        self.assertFalse(seen.intersection(key(r['question']) for r in test))
        self.assertGreaterEqual(len(control),100)
        self.assertTrue(all(key(r['question']) in {key(t['question']) for t in train} for r in user))
        self.assertTrue(all(r['holdout_kind'] in ('semantic_paraphrase','new_prefix') for r in test))


if __name__=='__main__':unittest.main()
