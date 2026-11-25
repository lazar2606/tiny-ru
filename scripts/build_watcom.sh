#!/bin/sh
# Alternative free 16-bit DOS compiler. Turbo C 2.0 uses dos/BUILD.BAT.
set -eu
cd "$(dirname "$0")/../dos"
: "${WATCOM:?Set WATCOM to the extracted Open Watcom installation}"
export PATH="$WATCOM/binl64:$WATCOM/binl:$PATH"
export INCLUDE="$WATCOM/h"
output_dir=${TINY_DOS_OUTPUT_DIR:-.}
mkdir -p "$output_dir"
wcl -q -bt=dos -ml -3 -fpi87 -os "-fe=$output_dir/TINY.EXE" "-fm=$output_dir/TINY.MAP" -k8192 -cc TINY.C
