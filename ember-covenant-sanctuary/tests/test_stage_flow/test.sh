#!/usr/bin/env bash
set -euo pipefail

: "${PORT:?PORT is required}"

DIR="$(cd "$(dirname "$0")" && pwd)"
source "$DIR/../runtime_testlib.sh"
start_test
advance 90
setup_combat '{"stage":1}'
snapshot
setup_combat '{"stage":2}'
snapshot
setup_combat '{"stage":3}'
snapshot
setup_combat '{"stage":4}'
snapshot
setup_combat '{"stage":4,"route":"elite"}'
snapshot
setup_combat '{"stage":5}'
snapshot
setup_combat '{"stage":6,"wave":1}'
snapshot
setup_clear_room '{"stage":6,"wave":1,"projectiles":[{"type":"dart","position":{"x":900,"y":360},"angle":3.1415926536,"damage":15,"speed":300,"attackId":"wave1-lingering"}]}'
advance 1
snapshot
eval_js 'const dying=sceneTree.findByTag("enemy"); if(dying.length!==4) throw new Error("Stage 6 Wave 1 dying roster mismatch"); for(const enemy of dying) enemy._deathTime=0.001; return dying.map(enemy=>enemy.runtimeState());'
advance 1
snapshot
advance 10
snapshot
eval_js 'const director=sceneTree.root; if(!director.runtimeState().waveWarningActive) throw new Error("wave warning must be active before forced expiry"); director._waveWarningRemaining=0.001; return director.runtimeState();'
advance 1
snapshot
setup_combat '{"stage":7}'
snapshot
assert_trace assert_stage_flow.py
