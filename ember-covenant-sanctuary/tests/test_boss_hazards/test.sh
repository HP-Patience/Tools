#!/usr/bin/env bash
set -euo pipefail

: "${PORT:?PORT is required}"

DIR="$(cd "$(dirname "$0")" && pwd)"
source "$DIR/../runtime_testlib.sh"
start_test
advance 90
setup_combat '{"stage":7,"player":{"position":{"x":640,"y":360},"hp":100,"skill":{"cooldownRemaining":0,"buffRemaining":0,"lastRejected":null}},"enemies":[{"type":"bishop","position":{"x":1100,"y":360},"hp":20,"phase":2,"behaviorState":"phase-transition","stateTime":100}],"projectiles":[],"areas":[{"type":"ritual","position":{"x":640,"y":360},"attackId":"ritual-a","phase":"warning"},{"type":"ritual","position":{"x":650,"y":360},"attackId":"ritual-b","phase":"warning"},{"type":"ritual","position":{"x":900,"y":360},"attackId":"ritual-c","phase":"warning"}]}'
snapshot
setup_combat '{"stage":7,"player":{"position":{"x":640,"y":360},"hp":100,"skill":{"cooldownRemaining":0,"buffRemaining":0,"lastRejected":null}},"enemies":[{"type":"bishop","position":{"x":1100,"y":360},"hp":20,"phase":2,"behaviorState":"phase-transition","stateTime":100}],"projectiles":[],"areas":[{"type":"ritual","position":{"x":640,"y":360},"attackId":"ritual-a","phase":"active"},{"type":"ritual","position":{"x":650,"y":360},"attackId":"ritual-b","phase":"active"},{"type":"ritual","position":{"x":900,"y":360},"attackId":"ritual-c","phase":"active"}]}'
advance 1
snapshot
advance 5
snapshot
eval_js 'const p=[...sceneTree.nodes.values()].find(n=>n.enabled!==false&&n.tags?.includes("player")); p.getPhysicsObject().setPosition(900,360); return p.runtimeState();'
advance 1
snapshot
advance 5
snapshot
input_tap skill
advance 1
snapshot
eval_js 'const bosses=[...sceneTree.nodes.values()].filter(n=>n.enabled!==false&&n.tags?.includes("boss")); if(bosses.length!==1) throw new Error("exactly one active Boss required"); const boss=bosses[0]; boss.receiveDamage(boss.hp,"runtime-test"); return boss.runtimeState();'
advance 1
snapshot
advance 10
snapshot
assert_trace assert_boss_hazards.py
