#!/usr/bin/env bash
set -euo pipefail

: "${PORT:?PORT is required}"

DIR="$(cd "$(dirname "$0")" && pwd)"
source "$DIR/../runtime_testlib.sh"
start_test
advance 90
setup_combat '{"stage":1,"player":{"position":{"x":640,"y":360}},"enemies":[{"type":"fang","position":{"x":800,"y":360},"hp":60,"behaviorState":"approach","stateTime":0}],"projectiles":[],"areas":[]}'
eval_js 'const p=[...sceneTree.nodes.values()].find(n=>n.tags?.includes("player")); p.hp=10000; return p.hp;'
snapshot
sample_frames 165 1
setup_combat '{"stage":2,"player":{"position":{"x":640,"y":360}},"enemies":[{"type":"acolyte","position":{"x":950,"y":360},"hp":40,"behaviorState":"move","stateTime":0}],"projectiles":[],"areas":[]}'
eval_js 'const p=[...sceneTree.nodes.values()].find(n=>n.tags?.includes("player")); p.hp=10000; return p.hp;'
snapshot
sample_frames 270 1
setup_combat '{"stage":4,"route":"elite","player":{"position":{"x":640,"y":360}},"enemies":[{"type":"deacon","position":{"x":820,"y":360},"hp":220,"behaviorState":"approach","stateTime":0}],"projectiles":[],"areas":[]}'
eval_js 'const p=[...sceneTree.nodes.values()].find(n=>n.tags?.includes("player")); p.hp=10000; return p.hp;'
snapshot
sample_frames 210 1
setup_combat '{"stage":4,"route":"elite","player":{"position":{"x":640,"y":360},"skill":{"cooldownRemaining":0,"buffRemaining":0,"lastRejected":null}},"enemies":[{"type":"deacon","position":{"x":740,"y":360},"hp":220,"behaviorState":"melee-charge","stateTime":0.3,"attackId":"elite-pulse"}],"projectiles":[],"areas":[]}'
snapshot
input_tap skill
advance 1
snapshot
assert_trace assert_enemy_behaviors.py
