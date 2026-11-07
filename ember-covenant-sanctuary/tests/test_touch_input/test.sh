#!/usr/bin/env bash
set -euo pipefail

: "${PORT:?PORT is required}"

DIR="$(cd "$(dirname "$0")" && pwd)"
source "$DIR/../runtime_testlib.sh"
start_test
advance 90
for action in move_up move_down move_left move_right fire skill interact pause; do
  case "$action" in
    interact)
      setup_combat '{"stage":4,"player":{"position":{"x":400,"y":208},"hp":100}}'
      advance 1
      ;;
    *)
      setup_combat '{"stage":1,"player":{"position":{"x":640,"y":360},"hp":100,"skill":{"cooldownRemaining":0,"buffRemaining":0,"lastRejected":null}},"enemies":[],"projectiles":[],"areas":[]}'
      ;;
  esac
  if [ "$action" = fire ]; then dispatch_touch_fire_down_and_advance; else dispatch_touch_down_and_advance "$action"; fi
  snapshot
  if [ "$action" = fire ]; then
    dispatch_touch_fire_up_and_advance
  elif [ "$action" = pause ]; then
    dispatch_touch_up "$action"
  else
    dispatch_touch_up_and_advance "$action"
  fi
  snapshot
done
click_overlay_button continue
advance 1
snapshot

reload_runtime
advance 90
setup_combat '{"stage":1,"player":{"position":{"x":640,"y":360},"hp":100},"enemies":[],"projectiles":[],"areas":[]}'
dispatch_touch_fire_down_and_advance
snapshot
eval_js 'const overlay=[...sceneTree.nodes.values()].find(n=>n.name==="Overlay"); if(!overlay?.showMenu("pause")) throw new Error("pause overlay did not open"); return true;'
click_overlay_button continue
advance 1
snapshot
dispatch_touch_fire_down_and_advance
snapshot
dispatch_touch_fire_up_and_advance
snapshot
advance 20
dispatch_touch_fire_down_and_advance
snapshot
dispatch_touch_fire_up_and_advance
snapshot
take_screenshot touch-controls.png
assert_trace assert_touch_input.py
