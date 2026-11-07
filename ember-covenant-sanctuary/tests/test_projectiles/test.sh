#!/usr/bin/env bash
set -euo pipefail

: "${PORT:?PORT is required}"

DIR="$(cd "$(dirname "$0")" && pwd)"
source "$DIR/../runtime_testlib.sh"
start_test
advance 90
setup_combat '{"stage":1,"player":{"position":{"x":240,"y":360},"sigils":[]},"enemies":[],"projectiles":[]}'
move_pointer 1100 360
input_tap fire
advance 1
snapshot
advance 6
snapshot
setup_combat '{"stage":1,"player":{"position":{"x":640,"y":360},"sigils":[]},"enemies":[{"type":"fang","position":{"x":1300,"y":360},"hp":60,"behaviorState":"recover","stateTime":100}],"projectiles":[]}'
move_pointer 1100 360
input_tap fire
advance 1
snapshot
advance 60
snapshot
setup_combat '{"stage":1,"player":{"position":{"x":240,"y":360},"sigils":[]},"enemies":[{"type":"fang","position":{"x":500,"y":360},"hp":60,"behaviorState":"recover","stateTime":100},{"type":"fang","position":{"x":750,"y":360},"hp":60,"behaviorState":"recover","stateTime":100}],"projectiles":[]}'
move_pointer 1100 360
snapshot
input_tap fire
advance 30
snapshot
setup_combat '{"stage":1,"player":{"position":{"x":240,"y":360},"sigils":["piercing_ember"]},"enemies":[{"type":"fang","position":{"x":500,"y":360},"hp":60,"behaviorState":"recover","stateTime":100},{"type":"fang","position":{"x":750,"y":360},"hp":60,"behaviorState":"recover","stateTime":100},{"type":"fang","position":{"x":1000,"y":360},"hp":60,"behaviorState":"recover","stateTime":100}],"projectiles":[]}'
move_pointer 1100 360
snapshot
input_tap fire
advance 7
snapshot
advance 7
snapshot
advance 20
snapshot
assert_trace assert_projectiles.py
