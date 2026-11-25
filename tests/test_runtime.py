"""Integration tests run when a native C binary has been built."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'training'))
from model import Model,Cfg,export
import torch


@unittest.skipUnless((ROOT/'build/tiny-native').exists(),'Run scripts/build_native.sh first')
class RuntimeTests(unittest.TestCase):
    def run_with(self,weights,payload):
        with tempfile.TemporaryDirectory() as td:
            (Path(td)/'TINY.BIN').write_bytes(weights)
            return subprocess.run([str(ROOT/'build/tiny-native'),'/P','0'],cwd=td,input=payload,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)

    @classmethod
    def setUpClass(cls):
        torch.manual_seed(0)
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'model.bin'
            export(Model(Cfg()),path)
            cls.weights=path.read_bytes()

    def test_bad_model_files(self):
        for blob in [b'',self.weights[:12],b'BAD!'+self.weights[4:],self.weights+b'extra']:
            with self.subTest(length=len(blob)):
                self.assertNotEqual(self.run_with(blob,b'quit\n').returncode,0)

    def test_empty_long_and_all_cp866_bytes(self):
        payload=b'\n'+b'a'*73+b'\n'+b'a'*400+b'\n'+bytes(range(128,256))+b'\nquit\n'
        result=self.run_with(self.weights,payload)
        self.assertEqual(result.returncode,0)
        text=result.stdout.decode('cp866')
        self.assertEqual(text.count('Вопрос слишком длинный'),3)
        self.assertIn('До свидания!',text)

    def test_cr_only_and_mixed_line_endings(self):
        # No inference is necessary: all short lines are empty or the quit command.
        for payload in (b'\rquit\r', b'\r\n\rquit\r\n', b'\nquit'):
            result=self.run_with(self.weights,payload)
            self.assertEqual(result.returncode,0)
            self.assertNotIn('Вопрос слишком длинный',result.stdout.decode('cp866'))
            self.assertIn('До свидания!',result.stdout.decode('cp866'))


if __name__=='__main__':unittest.main()
