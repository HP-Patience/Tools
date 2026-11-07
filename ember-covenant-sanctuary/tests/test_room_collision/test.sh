#!/usr/bin/env bash
set -euo pipefail

: "${PORT:?PORT is required}"

DIR="$(cd "$(dirname "$0")" && pwd)"
source "$DIR/../runtime_testlib.sh"
start_test
advance 90
setup_combat '{"stage":1,"player":{"position":{"x":1230,"y":360}},"enemies":[],"projectiles":[]}'
input_down move_right
advance 30
snapshot
advance 30
snapshot
input_up move_right
setup_combat '{"stage":1,"player":{"position":{"x":1160,"y":360},"skill":{"cooldownRemaining":0,"buffRemaining":0,"lastRejected":null}},"enemies":[{"type":"fang","position":{"x":1220,"y":360},"hp":60,"behaviorState":"charge","stateTime":0.3}],"projectiles":[]}'
snapshot
input_tap skill
advance 15
snapshot
setup_combat '{"stage":1,"player":{"position":{"x":1180,"y":300}},"enemies":[],"projectiles":[{"type":"bolt","position":{"x":1230,"y":300},"angle":0,"damage":20,"speed":760,"attackId":"wall-player-projectile"}]}'
snapshot
advance 10
snapshot
setup_combat '{"stage":1,"player":{"position":{"x":1180,"y":420}},"enemies":[],"projectiles":[{"type":"dart","position":{"x":1230,"y":420},"angle":0,"damage":15,"speed":500,"attackId":"wall-enemy-projectile"}]}'
snapshot
advance 10
snapshot
setup_combat '{"stage":1,"player":{"position":{"x":640,"y":160}},"enemies":[],"projectiles":[]}'
input_down move_up
advance 90
snapshot
advance 30
snapshot
input_up move_up
setup_combat '{"stage":1,"player":{"position":{"x":640,"y":150},"skill":{"cooldownRemaining":0,"buffRemaining":0,"lastRejected":null}},"enemies":[{"type":"fang","position":{"x":640,"y":90},"hp":60,"behaviorState":"charge","stateTime":0.3}],"projectiles":[]}'
snapshot
input_tap skill
advance 15
snapshot
setup_combat '{"stage":1,"player":{"position":{"x":640,"y":160}},"enemies":[],"projectiles":[{"type":"bolt","position":{"x":640,"y":120},"angle":-1.5707963268,"damage":20,"speed":760,"attackId":"door-player-projectile"}]}'
snapshot
advance 30
snapshot
setup_combat '{"stage":1,"player":{"position":{"x":640,"y":160}},"enemies":[],"projectiles":[{"type":"dart","position":{"x":640,"y":120},"angle":-1.5707963268,"damage":15,"speed":500,"attackId":"door-enemy-projectile"}]}'
snapshot
advance 30
snapshot
setup_clear_room '{"stage":1,"player":{"position":{"x":640,"y":160}}}'
wait_while_paused 1
click_first_sigil
advance 1
snapshot
input_down move_up
advance 30
input_up move_up
snapshot
take_screenshot door-open.png
assert_trace assert_room_collision.py
