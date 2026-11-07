#!/usr/bin/env bash
set -euo pipefail

: "${PORT:?PORT is required}"

DIR="$(cd "$(dirname "$0")" && pwd)"
source "$DIR/../runtime_testlib.sh"
start_test
advance 90
setup_combat '{"stage":7,"player":{"position":{"x":300,"y":360},"hp":100},"enemies":[{"type":"bishop","position":{"x":900,"y":360},"hp":1500,"phase":1,"behaviorState":"adjust","stateTime":0}],"projectiles":[],"areas":[]}'
snapshot
setup_combat '{"stage":7,"player":{"position":{"x":300,"y":360}},"enemies":[{"type":"bishop","position":{"x":900,"y":360},"hp":760,"phase":1,"behaviorState":"active","stateTime":0}],"projectiles":[{"type":"bolt","position":{"x":900,"y":360},"angle":0,"damage":20,"speed":0,"attackId":"threshold-hit"}],"areas":[]}'
advance 1
snapshot
setup_combat '{"stage":7,"player":{"position":{"x":300,"y":360}},"enemies":[{"type":"bishop","position":{"x":900,"y":360},"hp":740,"phase":1,"behaviorState":"phase-transition","stateTime":0.5}],"projectiles":[{"type":"bolt","position":{"x":900,"y":360},"angle":0,"damage":20,"speed":0,"attackId":"transition-hit"}],"areas":[]}'
advance 1
snapshot
setup_combat '{"stage":7,"player":{"position":{"x":300,"y":360}},"enemies":[{"type":"bishop","position":{"x":900,"y":360},"hp":760,"phase":1,"behaviorState":"active","stateTime":0}],"projectiles":[{"type":"bolt","position":{"x":900,"y":360},"angle":0,"damage":9999,"speed":0,"attackId":"direct-death"}],"areas":[]}'
advance 1
snapshot
reload_runtime
setup_combat '{"stage":7,"player":{"position":{"x":300,"y":360},"hp":100},"enemies":[{"type":"bishop","position":{"x":500,"y":360},"hp":700,"phase":2,"phaseSlot":0,"consecutiveRanged":0,"behaviorState":"adjust","stateTime":0}],"projectiles":[],"areas":[]}'
eval_js 'const p=[...sceneTree.nodes.values()].find(n=>n.tags?.includes("player")); p.hp=10000; return p.hp;'
sample_frames 55 6
assert_trace assert_boss_encounter.py
