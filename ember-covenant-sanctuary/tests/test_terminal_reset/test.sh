#!/usr/bin/env bash
set -euo pipefail

: "${PORT:?PORT is required}"

DIR="$(cd "$(dirname "$0")" && pwd)"
source "$DIR/../runtime_testlib.sh"
start_test
advance 90
setup_combat '{"stage":2,"layout":"side-aisle-crypt","player":{"position":{"x":640,"y":360},"hp":15},"enemies":[],"projectiles":[{"type":"dart","position":{"x":640,"y":360},"angle":0,"damage":15,"speed":0,"attackId":"terminal-lose"}],"areas":[]}'
advance 1
snapshot
reload_runtime
setup_simultaneous_terminal '{"player":{"position":{"x":640,"y":360},"hp":1},"enemies":[{"type":"bishop","position":{"x":700,"y":360},"hp":1,"phase":2}]}'
advance 1
wait_while_paused 2.2
snapshot
click_overlay_button restart
wait_after_reload 1
advance 1
snapshot
assert_trace assert_terminal_reset.py
