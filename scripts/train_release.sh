#!/bin/sh
# Reproduce the r3 stages from the included Russian r2 checkpoint.
set -eu
cd "$(dirname "$0")/.."
output_dir=${1:-build/reproduced}
mkdir -p "$output_dir"
python3 training/train2.py train --data data/russia/train.jsonl --validation data/russia/validation.jsonl --control data/russia/control.jsonl --init experiments/r2-release/baseline.pt --out "$output_dir/russia-stage1.pt" --steps 8000 --stop-after 3000 --batch-size 32 --lr 0.001 --loss-per-example --focus-prefix россия: --focus-probability 0.8 --no-curriculum --augment-format
python3 training/train2.py train --data data/russia-expanded/train.jsonl --validation data/russia-expanded/validation.jsonl --control data/russia-expanded/control.jsonl --init "$output_dir/russia-stage1.pt" --out "$output_dir/russia-expanded.pt" --steps 5000 --batch-size 32 --lr 0.0007 --loss-per-example --focus-prefix россия: --focus-probability 0.8 --no-curriculum --augment-format --augment-prefixes
python3 training/train2.py train --data data/russia-calibration/train.jsonl --validation data/russia-expanded/validation.jsonl --control data/russia-expanded/control.jsonl --init "$output_dir/russia-expanded.pt" --out "$output_dir/russia-calibrated.pt" --steps 1000 --batch-size 32 --lr 0.0003 --loss-per-example --focus-prefix россия: --focus-probability 0.8 --no-curriculum --augment-format
python3 training/train2.py train --data data/russia-final/train.jsonl --validation data/russia-final/validation.jsonl --control data/russia-final/control.jsonl --init "$output_dir/russia-calibrated.pt" --out "$output_dir/russia-final.pt" --steps 500 --batch-size 32 --lr 0.00015 --loss-per-example --focus-prefix россия: --focus-probability 0.8 --no-curriculum --augment-format
python3 training/train2.py export "$output_dir/russia-final.pt" "$output_dir/TINY.BIN"
