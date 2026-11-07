#!/usr/bin/env bash
set -euo pipefail

: "${PORT:?PORT is required}"

DIR="$(cd "$(dirname "$0")" && pwd)"
source "$DIR/../runtime_testlib.sh"
start_test
advance 90
setup_clear_room '{"stage":1,"player":{"sigils":[]}}'
wait_while_paused 1
snapshot
setup_clear_room '{"stage":5,"player":{"sigils":["piercing_ember","ash_crown","sacred_nail","light_ember","rekindle","wide_radiance"]}}'
wait_while_paused 1
snapshot
assert_trace assert_sigil_offers.py
