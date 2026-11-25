#!/bin/sh
# Evaluate a completed candidate without overwriting the working release.
set -eu
cd "$(dirname "$0")/.."
checkpoint=${1:-training/russia-final.pt}
python3 training/train2.py export "$checkpoint" build/russia/TINY.BIN
python3 training/train2.py eval "$checkpoint" --questions data/russia-final/control.jsonl --out reports/russia/float.json > reports/russia/float.log
python3 training/train2.py eval build/russia/TINY.BIN --questions data/russia-final/control.jsonl --out reports/russia/int8.json > reports/russia/int8.log
python3 training/train2.py eval build/russia/TINY.BIN --questions data/russia-final/test.jsonl --out reports/russia/unseen-all.json > reports/russia/unseen-all.log
python3 scripts/evaluate_c.py --model-dir build/russia --executable build/tiny-native --questions data/russia-final/control.jsonl --transcript reports/russia/native-output.cp866.txt --out reports/russia/native.json > reports/russia/native.log
python3 training/train2.py eval build/russia/TINY.BIN --questions data/improved/user-regressions.jsonl --out reports/russia/user-regressions.json > reports/russia/user-regressions.log
python3 training/train2.py eval build/russia/TINY.BIN --questions data/improved/control.jsonl --out reports/russia/previous-skills.json > reports/russia/previous-skills.log
echo 'Completed FP32/int8/native evaluation, all new wordings and old regressions'
