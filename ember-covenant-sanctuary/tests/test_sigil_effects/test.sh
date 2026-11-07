#!/usr/bin/env bash
set -euo pipefail

: "${PORT:?PORT is required}"

DIR="$(cd "$(dirname "$0")" && pwd)"
source "$DIR/../runtime_testlib.sh"
start_test
advance 90
setup_combat '{"stage":1,"player":{"position":{"x":240,"y":360},"sigils":[]},"enemies":[],"projectiles":[]}'
snapshot
setup_combat '{"stage":1,"player":{"position":{"x":240,"y":360},"sigils":["piercing_ember"]},"enemies":[],"projectiles":[]}'
move_pointer 1100 360
input_tap fire
advance 1
snapshot
setup_combat '{"stage":1,"player":{"position":{"x":240,"y":360},"sigils":["ash_crown"]},"enemies":[],"projectiles":[]}'
move_pointer 1100 360
input_tap fire
advance 1
snapshot
setup_combat '{"stage":1,"player":{"position":{"x":240,"y":360},"sigils":["sacred_nail"]},"enemies":[],"projectiles":[]}'
move_pointer 1100 360
input_tap fire
advance 1
snapshot
setup_combat '{"stage":1,"player":{"position":{"x":240,"y":360},"hp":100,"sigils":["light_ember"]},"enemies":[],"projectiles":[]}'
snapshot
setup_combat '{"stage":1,"player":{"position":{"x":240,"y":360},"hp":50,"sigils":["rekindle"]},"enemies":[{"type":"fang","position":{"x":900,"y":360},"hp":60}],"projectiles":[]}'
snapshot
setup_clear_room '{"stage":1,"player":{"position":{"x":240,"y":360},"hp":50,"sigils":["rekindle"]},"enemies":[{"type":"fang","position":{"x":900,"y":360},"hp":60}],"projectiles":[]}'
wait_while_paused 1
snapshot
setup_combat '{"stage":1,"player":{"position":{"x":240,"y":360},"hp":100,"sigils":["wide_radiance"],"skill":{"cooldownRemaining":0,"buffRemaining":0,"lastRejected":null}},"enemies":[],"projectiles":[]}'
input_tap skill
advance 1
snapshot
setup_combat '{"stage":1,"player":{"position":{"x":640,"y":360},"sigils":["close_flame"]},"enemies":[{"type":"fang","position":{"x":800,"y":360},"hp":60,"behaviorState":"recover","stateTime":100}],"projectiles":[]}'
move_pointer 800 360
input_tap fire
advance 20
snapshot
setup_combat '{"stage":1,"player":{"position":{"x":640,"y":360},"sigils":["close_flame"]},"enemies":[{"type":"fang","position":{"x":1000,"y":360},"hp":60,"behaviorState":"recover","stateTime":100}],"projectiles":[]}'
move_pointer 1000 360
input_tap fire
advance 35
snapshot
setup_combat '{"stage":1,"player":{"position":{"x":640,"y":360},"hp":35,"sigils":["last_candle"]},"enemies":[{"type":"fang","position":{"x":800,"y":360},"hp":60}],"projectiles":[]}'
move_pointer 800 360
input_tap fire
advance 20
snapshot
setup_combat '{"stage":1,"player":{"position":{"x":640,"y":360},"hp":36,"sigils":["last_candle"]},"enemies":[{"type":"fang","position":{"x":800,"y":360},"hp":60}],"projectiles":[]}'
move_pointer 800 360
input_tap fire
advance 20
snapshot
setup_combat '{"stage":1,"player":{"position":{"x":640,"y":360},"hp":100,"sigils":["blood_prayer"],"skill":{"cooldownRemaining":0,"buffRemaining":0,"lastRejected":null}},"enemies":[],"projectiles":[]}'
snapshot
input_tap skill
advance 1
snapshot
setup_combat '{"stage":1,"player":{"position":{"x":640,"y":360},"hp":8,"sigils":["blood_prayer"],"skill":{"cooldownRemaining":0,"buffRemaining":0,"lastRejected":null}},"enemies":[],"projectiles":[]}'
input_tap skill
advance 1
snapshot
setup_combat '{"stage":1,"player":{"position":{"x":240,"y":360},"sigils":["ash_crown","sacred_nail"]},"enemies":[],"projectiles":[]}'
move_pointer 1100 360
input_tap fire
advance 1
snapshot
assert_trace assert_sigil_effects.py
