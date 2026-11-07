#!/usr/bin/env bash
set -euo pipefail

: "${PORT:?PORT is required}"

DIR="$(cd "$(dirname "$0")" && pwd)"
source "$DIR/../runtime_testlib.sh"
start_test
advance 90
setup_combat '{"stage":7,"player":{"position":{"x":640,"y":360},"hp":100,"sigils":[],"skill":{"cooldownRemaining":0,"buffRemaining":0,"lastRejected":null}},"enemies":[{"type":"fang","position":{"x":730,"y":360},"hp":60,"behaviorState":"charge","stateTime":0.3,"attackId":"pulse-fang"},{"type":"deacon","position":{"x":640,"y":240},"hp":220,"behaviorState":"melee-charge","stateTime":0.3,"attackId":"pulse-deacon"},{"type":"bishop","position":{"x":520,"y":300},"hp":1500,"behaviorState":"slam-charge","stateTime":0.3,"attackId":"pulse-bishop","phase":1}],"projectiles":[{"type":"dart","position":{"x":700,"y":360},"angle":3.1415926536,"damage":15,"speed":0,"attackId":"pulse-inner"},{"type":"dart","position":{"x":820,"y":360},"angle":3.1415926536,"damage":15,"speed":900,"attackId":"pulse-outer"}],"areas":[{"type":"ritual","position":{"x":640,"y":500},"attackId":"pulse-hazard","phase":"warning"}]}'
snapshot
input_tap skill
advance 1
snapshot
advance 12
snapshot
assert_trace assert_pureflame_pulse.py
