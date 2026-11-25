#!/bin/sh
# WSL/Linux cross-build: apt install gcc-mingw-w64-x86-64-win32
set -eu
cd "$(dirname "$0")/.."
cc=${TINY_WINDOWS_CC:-x86_64-w64-mingw32-gcc}
if [ -n "${TINY_ZIG:-}" ]; then
  set -- "$TINY_ZIG" cc -target x86_64-windows-gnu
  platform_flags=''
else
  set -- "$cc"
  platform_flags='-static-libgcc -mconsole'
fi
python3 training/tokenizer.py
python3 scripts/generate_strings.py
mkdir -p windows
"$@" -x c -std=c99 -O2 -Wall -Wextra -Wno-unused-function -static $platform_flags \
  -Wl,--dynamicbase,--nxcompat dos/TINY.C windows/console.c -lm -o windows/TINYWIN.EXE
cp dos/TINY.BIN windows/TINY.BIN
"$@" --version | head -n 1
ls -l windows/TINYWIN.EXE windows/TINY.BIN
