#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
: "${WATCOM:?Set WATCOM}"
export PATH="$WATCOM/binl64:$WATCOM/binl:$PATH"
export INCLUDE="$WATCOM/h"
mkdir -p build
wcl -q -bt=dos -ml -3 -fpi87 -os -k8192 -fe=build/CPINPUT.EXE tests/console_probe.c
