#!/usr/bin/env bash
set -euo pipefail

: "${PORT:?PORT is required}"

DIR="$(cd "$(dirname "$0")" && pwd)"
source "$DIR/../runtime_testlib.sh"
start_test
advance 90
setup_combat '{"stage":1,"player":{"hp":100,"sigils":[]}}'
snapshot
advance 70
snapshot
input_tap skill
advance 1
snapshot
setup_combat '{"stage":1,"player":{"hp":8,"sigils":["blood_prayer"],"skill":{"cooldownRemaining":0,"buffRemaining":0,"lastRejected":null}},"enemies":[],"projectiles":[],"areas":[]}'
input_tap skill
advance 1
snapshot
setup_combat '{"stage":1,"player":{"hp":100,"sigils":["blood_prayer"],"skill":{"cooldownRemaining":0,"buffRemaining":0,"lastRejected":null}},"enemies":[],"projectiles":[],"areas":[]}'
input_tap skill
advance 1
snapshot
setup_combat '{"stage":1,"player":{"position":{"x":640,"y":360},"sigils":["close_flame"]},"enemies":[{"type":"fang","position":{"x":800,"y":360},"hp":60}]}'
move_pointer 800 360
advance 1
snapshot
move_pointer 1100 360
advance 1
snapshot
setup_combat '{"stage":1,"player":{"position":{"x":640,"y":360},"hp":100,"sigils":[]},"enemies":[{"type":"fang","position":{"x":800,"y":360},"hp":60,"behaviorState":"recover","stateTime":100}],"projectiles":[],"areas":[]}'
advance 1
snapshot
move_pointer 800 360
input_tap fire
sample_frames 8 1
take_screenshot damage-digit-visible.png
advance 90
snapshot
eval_js "const count=document.querySelectorAll('.damage-number').length; if(count!==0) throw new Error('damage digit DOM did not clear after TTL: '+count); return {damageNumberDomCount:count};"
setup_clear_room '{"stage":1}'
wait_while_paused 1
click_first_sigil
advance 1
snapshot
setup_combat '{"stage":7,"player":{"hp":100},"enemies":[{"type":"bishop","position":{"x":1100,"y":360},"hp":1500,"phase":1}]}'
advance 1
eval_js 'const p=sceneTree.findByTag("player")[0]; if(!p?.receiveDamage?.(20,"hud-bar-test","hud-bar-test-1")) throw new Error("public player damage setup failed"); return p.runtimeState();'
advance 1
snapshot
take_screenshot boss-hud.png
assert_trace assert_hud_state.py
