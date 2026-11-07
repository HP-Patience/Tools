#!/usr/bin/env bash
set -euo pipefail

: "${PORT:?PORT is required}"

DIR="$(cd "$(dirname "$0")" && pwd)"
source "$DIR/../runtime_testlib.sh"
start_test
advance 90
setup_combat '{"stage":1,"player":{"position":{"x":640,"y":360},"hp":100},"enemies":[{"type":"fang","position":{"x":640,"y":360},"hp":60,"behaviorState":"recover","stateTime":100}],"projectiles":[],"areas":[]}'
snapshot
advance 30
snapshot
setup_combat '{"stage":1,"player":{"position":{"x":640,"y":360},"hp":100},"enemies":[],"projectiles":[],"areas":[{"type":"fang","position":{"x":640,"y":360},"attackId":"same","phase":"active"},{"type":"fang","position":{"x":640,"y":360},"attackId":"same","phase":"active"}]}'
advance 1
snapshot
setup_combat '{"stage":1,"player":{"position":{"x":640,"y":360},"hp":100},"enemies":[],"projectiles":[],"areas":[{"type":"fang","position":{"x":640,"y":360},"attackId":"one","phase":"active"},{"type":"fang","position":{"x":640,"y":360},"attackId":"two","phase":"active"}]}'
advance 1
snapshot
setup_combat '{"stage":4,"route":"elite","player":{"position":{"x":640,"y":360},"hp":10},"enemies":[],"projectiles":[],"areas":[{"type":"deacon","position":{"x":640,"y":360},"attackId":"overkill","phase":"active"}]}'
advance 1
snapshot
reload_runtime
setup_combat '{"stage":1,"player":{"position":{"x":640,"y":360},"hp":20},"enemies":[{"type":"fang","position":{"x":700,"y":360},"hp":20,"behaviorState":"active","stateTime":0}],"projectiles":[{"type":"bolt","position":{"x":700,"y":360},"angle":0,"damage":20,"speed":0,"attackId":"ordinary-mutual-player"}],"areas":[{"type":"fang","position":{"x":640,"y":360},"attackId":"ordinary-mutual-enemy","phase":"active"}]}'
advance 1
snapshot
reload_runtime
setup_combat '{"stage":4,"route":"elite","player":{"position":{"x":640,"y":360},"hp":25},"enemies":[{"type":"deacon","position":{"x":700,"y":360},"hp":20,"behaviorState":"active","stateTime":0}],"projectiles":[{"type":"bolt","position":{"x":700,"y":360},"angle":0,"damage":20,"speed":0,"attackId":"elite-mutual-player"}],"areas":[{"type":"deacon","position":{"x":640,"y":360},"attackId":"elite-mutual-enemy","phase":"active"}]}'
advance 1
snapshot
assert_trace assert_damage_resolution.py
