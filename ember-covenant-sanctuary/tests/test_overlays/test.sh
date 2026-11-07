#!/usr/bin/env bash
set -euo pipefail

: "${PORT:?PORT is required}"

DIR="$(cd "$(dirname "$0")" && pwd)"
source "$DIR/../runtime_testlib.sh"
start_test
advance 90
setup_combat '{"stage":2,"player":{"position":{"x":640,"y":360},"hp":100,"skill":{"cooldownRemaining":0,"buffRemaining":0,"lastRejected":null}},"enemies":[{"type":"acolyte","position":{"x":900,"y":360},"hp":40,"behaviorState":"move","stateTime":0}],"projectiles":[{"type":"dart","position":{"x":1000,"y":200},"angle":3.1415926536,"damage":15,"speed":100,"attackId":"pause-motion"}],"areas":[]}'
input_tap skill
advance 1
snapshot
key_press Escape
snapshot
wait_while_paused 3
snapshot
click_overlay_button continue
advance 30
snapshot
key_press Escape
click_overlay_button restart
snapshot
wait_while_paused 2
key_press Escape
snapshot
click_overlay_button cancel
snapshot
click_overlay_button continue
advance 2
snapshot
setup_clear_room '{"stage":1,"player":{"skill":{"cooldownRemaining":5}}}'
wait_while_paused 1
snapshot
wait_while_paused 2
key_press Escape
snapshot
setup_combat '{"stage":2,"player":{"position":{"x":640,"y":360},"hp":15},"enemies":[],"projectiles":[{"type":"dart","position":{"x":640,"y":360},"angle":0,"damage":15,"speed":0,"attackId":"overlay-death"}],"areas":[]}'
wait_while_paused 1.2
snapshot
wait_while_paused 2
key_press Escape
snapshot
take_screenshot restart-confirmation.png
click_overlay_button restart
wait_after_reload 1
advance 1
snapshot
assert_trace assert_overlays.py
