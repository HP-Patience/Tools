#!/usr/bin/env bash
set -euo pipefail

: "${PORT:?PORT is required}"

DIR="$(cd "$(dirname "$0")" && pwd)"
source "$DIR/../runtime_testlib.sh"
start_test
advance 90
input_tap skill
advance 2
snapshot
input_tap skill
advance 2
snapshot
key_press Escape
snapshot
wait_while_paused 2
snapshot
click_overlay_button continue
advance 60
snapshot
setup_combat '{"stage":1,"player":{"position":{"x":640,"y":360},"hp":100,"sigils":["blood_prayer"],"skill":{"cooldownRemaining":0,"buffRemaining":0,"lastRejected":null}},"enemies":[],"projectiles":[],"areas":[]}'
input_tap skill
advance 1
key_press Escape
snapshot
wait_while_paused 2
snapshot
click_overlay_button continue
setup_combat '{"stage":1,"player":{"position":{"x":640,"y":360},"hp":8,"sigils":["blood_prayer"],"skill":{"cooldownRemaining":0,"buffRemaining":0,"lastRejected":null}},"enemies":[],"projectiles":[],"areas":[]}'
input_tap skill
advance 2
snapshot
assert_trace assert_skill_edges.py
