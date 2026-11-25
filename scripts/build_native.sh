#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
python3 training/tokenizer.py
python3 scripts/generate_strings.py
mkdir -p build
gcc -x c -std=c89 -pedantic -Wall -Wextra -O2 dos/TINY.C -lm -o build/tiny-native
