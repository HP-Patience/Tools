#!/usr/bin/env bash

: "${PORT:?PORT is required}"

TEST_DIR="$(cd "$(dirname "$0")" && pwd)"
EVIDENCE="$TEST_DIR/evidence"
TRACE="$EVIDENCE/snapshot.jsonl"
CONTROLLER_LOG="$EVIDENCE/controller.log"
EVAL_LOG="$EVIDENCE/eval.jsonl"
PLAY=(vibegame play --port "$PORT")

start_test() {
  mkdir -p "$EVIDENCE"
  : > "$TRACE"
  : > "$CONTROLLER_LOG"
  : > "$EVAL_LOG"
  "${PLAY[@]}" activate >> "$CONTROLLER_LOG"
}

advance() {
  "${PLAY[@]}" continue -f "$1" >> "$CONTROLLER_LOG"
}

snapshot() {
  "${PLAY[@]}" snapshot >> "$TRACE"
}

sample_frames() {
  local count="$1"
  local frames="$2"
  local ops="$EVIDENCE/batch-${count}x${frames}.ops"
  local output="$EVIDENCE/batch-${count}x${frames}.log"
  : > "$ops"
  for _ in $(seq 1 "$count"); do
    printf 'continue -f %s\nsnapshot\n' "$frames" >> "$ops"
  done
  "${PLAY[@]}" batch "@$ops" > "$output"
  python3 - "$output" "$TRACE" <<'PY'
import json
import sys
from pathlib import Path

raw = Path(sys.argv[1]).read_text(encoding="utf-8")
decoder = json.JSONDecoder()
index = 0
snapshots = []
while index < len(raw):
    start = raw.find("{", index)
    if start < 0:
        break
    try:
        value, end = decoder.raw_decode(raw, start)
    except json.JSONDecodeError:
        index = start + 1
        continue
    index = end
    if isinstance(value, dict) and "nodes" in value:
        snapshots.append(value)
with Path(sys.argv[2]).open("a", encoding="utf-8") as trace:
    for snapshot in snapshots:
        json.dump(snapshot, trace, ensure_ascii=False)
        trace.write("\n")
if not snapshots:
    raise SystemExit("batch produced no snapshots")
PY
}

runtime_test_setup() {
  local mode="$1"
  local payload="$2"
  eval_js "const d=[...sceneTree.nodes.values()].find(n=>typeof n.runtimeTestSetup==='function'); if(!d) throw new Error('RunDirector.runtimeTestSetup(mode,params) is required by plan.md'); await d.runtimeTestSetup('$mode',$payload); return d.runtimeState();"
}

setup_combat() {
  runtime_test_setup combat "$1"
}

setup_clear_room() {
  runtime_test_setup clear-room "$1"
}

setup_simultaneous_terminal() {
  runtime_test_setup simultaneous-terminal "$1"
}

eval_js() {
  local response
  response="$("${PLAY[@]}" eval "$1")"
  printf '%s\n' "$response" >> "$EVAL_LOG"
  python3 -c 'import json, sys; payload=json.load(sys.stdin); raise SystemExit(1 if payload.get("error") else 0)' <<< "$response"
}

wait_while_paused() {
  "${PLAY[@]}" deactivate >> "$CONTROLLER_LOG"
  sleep "$1"
  "${PLAY[@]}" activate >> "$CONTROLLER_LOG"
}

reload_runtime() {
  "${PLAY[@]}" refresh >> "$CONTROLLER_LOG"
  "${PLAY[@]}" activate >> "$CONTROLLER_LOG"
}

wait_after_reload() {
  sleep "$1"
  "${PLAY[@]}" activate >> "$CONTROLLER_LOG"
}

input_down() {
  "${PLAY[@]}" input -a "$1" --held >> "$CONTROLLER_LOG"
}

input_up() {
  "${PLAY[@]}" input -a "$1" --release >> "$CONTROLLER_LOG"
}

input_tap() {
  "${PLAY[@]}" input -a "$1" >> "$CONTROLLER_LOG"
}

key_press() {
  "${PLAY[@]}" key -c "$1" -t press >> "$CONTROLLER_LOG"
}

move_pointer() {
  "${PLAY[@]}" mousemove -x "$1" -y "$2" >> "$CONTROLLER_LOG"
}

take_screenshot() {
  "${PLAY[@]}" screenshot -o "$EVIDENCE/$1" >> "$CONTROLLER_LOG"
}

assert_trace() {
  python3 "$TEST_DIR/$1" "$TRACE"
}

click_overlay_button() {
  eval_js "const wanted='$1'.toLowerCase(); const aliases={continue:'继续',cancel:'返回',restart:'重新开始'}; const label=aliases[wanted]||wanted; const buttons=[...document.querySelectorAll('button')].filter(b=>b.offsetParent!==null); const button=buttons.find(b=>(b.dataset.action||'').toLowerCase()===wanted||(b.textContent||'').trim().toLowerCase().includes(wanted)||(b.textContent||'').includes(label)); if(!button) throw new Error('visible overlay button $1 missing'); button.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,pointerId:91,pointerType:'mouse',buttons:1})); button.dispatchEvent(new PointerEvent('pointerup',{bubbles:true,pointerId:91,pointerType:'mouse',buttons:0})); button.click(); return true;"
}

click_first_sigil() {
  eval_js "const card=[...document.querySelectorAll('[data-sigil-id],[data-option-id],.up-card[data-idx]')].find(node=>node.offsetParent!==null); if(!card) throw new Error('visible sigil option DOM node missing'); card.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,pointerId:92,pointerType:'mouse',buttons:1})); card.dispatchEvent(new PointerEvent('pointerup',{bubbles:true,pointerId:92,pointerType:'mouse',buttons:0})); card.click(); return true;"
}

dispatch_touch_down() {
  eval_js "const action='$1'; const selector=['[data-touch-action=\"'+action+'\"]','[data-action=\"'+action+'\"]','[data-vg-action=\"'+action+'\"]'].join(','); const target=document.querySelector(selector); if(!target) throw new Error('touch control '+action+' missing'); const r=target.getBoundingClientRect(); target.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,pointerId:71,pointerType:'touch',isPrimary:true,buttons:1,clientX:r.left+r.width/2,clientY:r.top+r.height/2})); return true;"
}

dispatch_touch_up() {
  eval_js "const action='$1'; const selector=['[data-touch-action=\"'+action+'\"]','[data-action=\"'+action+'\"]','[data-vg-action=\"'+action+'\"]'].join(','); const target=document.querySelector(selector); if(!target) throw new Error('touch control '+action+' missing'); const r=target.getBoundingClientRect(); target.dispatchEvent(new PointerEvent('pointerup',{bubbles:true,pointerId:71,pointerType:'touch',isPrimary:true,buttons:0,clientX:r.left+r.width/2,clientY:r.top+r.height/2})); return true;"
}

dispatch_touch_down_and_advance() {
  local action="$1"
  local ops="$EVIDENCE/touch-${action}-down.ops"
  printf '%s\n' \
    'deactivate' \
    "eval const action='$action'; const target=document.querySelector('[data-action=\"'+action+'\"]'); if(!target) throw new Error('touch control '+action+' missing'); const r=target.getBoundingClientRect(); target.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,pointerId:71,pointerType:'touch',isPrimary:true,buttons:1,clientX:r.left+r.width/2,clientY:r.top+r.height/2})); return true;" \
    'eval await new Promise(resolve=>setTimeout(resolve,80)); return true;' \
    'activate' > "$ops"
  "${PLAY[@]}" batch "@$ops" >> "$CONTROLLER_LOG"
}

dispatch_touch_up_and_advance() {
  local action="$1"
  local ops="$EVIDENCE/touch-${action}-up.ops"
  printf '%s\n' \
    'deactivate' \
    "eval const action='$action'; const target=document.querySelector('[data-action=\"'+action+'\"]'); if(!target) throw new Error('touch control '+action+' missing'); const r=target.getBoundingClientRect(); target.dispatchEvent(new PointerEvent('pointerup',{bubbles:true,pointerId:71,pointerType:'touch',isPrimary:true,buttons:0,clientX:r.left+r.width/2,clientY:r.top+r.height/2})); return true;" \
    'eval await new Promise(resolve=>setTimeout(resolve,80)); return true;' \
    'activate' > "$ops"
  "${PLAY[@]}" batch "@$ops" >> "$CONTROLLER_LOG"
}

dispatch_touch_fire_down() {
  eval_js 'const target=document.querySelector("#touch-aim"); if(!target) throw new Error("touch aim control missing"); const r=target.getBoundingClientRect(); const x=r.left+r.width*0.72,y=r.top+r.height*0.5; target.dispatchEvent(new PointerEvent("pointerdown",{bubbles:true,pointerId:73,pointerType:"touch",isPrimary:true,buttons:1,clientX:x,clientY:y})); return {x,y};'
}

dispatch_touch_fire_up() {
  eval_js 'const target=document.querySelector("#touch-aim"); if(!target) throw new Error("touch aim control missing"); const r=target.getBoundingClientRect(); const x=r.left+r.width*0.72,y=r.top+r.height*0.5; target.dispatchEvent(new PointerEvent("pointerup",{bubbles:true,pointerId:73,pointerType:"touch",isPrimary:true,buttons:0,clientX:x,clientY:y})); return {x,y};'
}

dispatch_touch_fire_down_and_advance() {
  local ops="$EVIDENCE/touch-fire-down.ops"
  printf '%s\n' \
    'deactivate' \
    'eval const target=document.querySelector("#touch-aim"); if(!target) throw new Error("touch aim control missing"); const r=target.getBoundingClientRect(); const x=r.left+r.width*0.72,y=r.top+r.height*0.5; target.dispatchEvent(new PointerEvent("pointerdown",{bubbles:true,pointerId:73,pointerType:"touch",isPrimary:true,buttons:1,clientX:x,clientY:y})); return {x,y};' \
    'eval await new Promise(resolve=>setTimeout(resolve,80)); return true;' \
    'activate' > "$ops"
  "${PLAY[@]}" batch "@$ops" >> "$CONTROLLER_LOG"
}

dispatch_touch_fire_up_and_advance() {
  local ops="$EVIDENCE/touch-fire-up.ops"
  printf '%s\n' \
    'deactivate' \
    'eval const target=document.querySelector("#touch-aim"); if(!target) throw new Error("touch aim control missing"); const r=target.getBoundingClientRect(); const x=r.left+r.width*0.72,y=r.top+r.height*0.5; target.dispatchEvent(new PointerEvent("pointerup",{bubbles:true,pointerId:73,pointerType:"touch",isPrimary:true,buttons:0,clientX:x,clientY:y})); return {x,y};' \
    'eval await new Promise(resolve=>setTimeout(resolve,80)); return true;' \
    'activate' > "$ops"
  "${PLAY[@]}" batch "@$ops" >> "$CONTROLLER_LOG"
}
