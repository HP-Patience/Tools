#!/usr/bin/env bash
set -euo pipefail

: "${PORT:?PORT is required}"

DIR="$(cd "$(dirname "$0")" && pwd)"
source "$DIR/../runtime_testlib.sh"
start_test
advance 90
setup_combat '{"stage":4,"player":{"hp":40,"sigils":["piercing_ember","ash_crown","sacred_nail"]}}'
snapshot
take_screenshot route-junction.png
setup_combat '{"stage":4,"route":"recovery"}'
input_tap interact
advance 1
snapshot
input_tap interact
advance 1
snapshot
setup_clear_room '{"stage":5}'
wait_while_paused 1
click_first_sigil
advance 1
setup_clear_room '{"stage":6,"wave":2}'
wait_while_paused 1
click_first_sigil
advance 1
setup_combat '{"stage":7}'
snapshot
reload_runtime
advance 90
setup_combat '{"stage":4,"route":"elite","player":{"hp":40,"sigils":["piercing_ember","ash_crown","sacred_nail"]}}'
input_tap interact
advance 1
snapshot
eval_js 'const elites=[...sceneTree.nodes.values()].filter(n=>n.enabled!==false&&n.tags?.includes("enemy")&&n.runtimeState?.().kind==="dusk_deacon"); if(elites.length!==1) throw new Error("exactly one active Dusk Deacon required"); const elite=elites[0]; elite.receiveDamage(elite.hp,"runtime-test"); return elite.runtimeState();'
wait_while_paused 1.2
snapshot
click_first_sigil
advance 1
snapshot
input_tap interact
advance 1
snapshot
setup_clear_room '{"stage":5}'
wait_while_paused 1
click_first_sigil
advance 1
setup_clear_room '{"stage":6,"wave":2}'
wait_while_paused 1
click_first_sigil
advance 1
setup_combat '{"stage":7}'
snapshot
assert_trace assert_route_choice.py
