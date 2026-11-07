#!/usr/bin/env bash
set -euo pipefail

: "${PORT:?PORT is required}"

DIR="$(cd "$(dirname "$0")" && pwd)"
source "$DIR/../runtime_testlib.sh"
start_test
snapshot
input_down move_right
sample_frames 80 1
input_up move_right
take_screenshot run-start.png
assert_trace assert_run_start.py
