#!/usr/bin/env bash
set -euo pipefail

: "${PORT:?PORT is required}"

DIR="$(cd "$(dirname "$0")" && pwd)"
source "$DIR/../runtime_testlib.sh"
start_test
advance 90
eval_js 'const c=document.querySelector("canvas"),r=c.getBoundingClientRect(),x=r.left+r.width*0.8,y=r.top+r.height*0.5; c.dispatchEvent(new PointerEvent("pointermove",{bubbles:true,pointerId:31,pointerType:"mouse",buttons:0,clientX:x,clientY:y})); c.dispatchEvent(new PointerEvent("pointerdown",{bubbles:true,pointerId:31,pointerType:"mouse",button:0,buttons:1,clientX:x,clientY:y})); return true;'
advance 2
snapshot
eval_js 'const c=document.querySelector("canvas"); c.dispatchEvent(new PointerEvent("pointerleave",{bubbles:true,pointerId:31,pointerType:"mouse",buttons:0})); return true;'
advance 2
snapshot
eval_js 'const c=document.querySelector("canvas"),r=c.getBoundingClientRect(),x=r.left+r.width*0.7,y=r.top+r.height*0.5; c.dispatchEvent(new PointerEvent("pointermove",{bubbles:true,pointerId:31,pointerType:"mouse",buttons:0,clientX:x,clientY:y})); return true;'
advance 10
snapshot
input_down move_right
input_down fire
advance 2
snapshot
eval_js 'window.dispatchEvent(new Event("blur")); return true;'
advance 2
snapshot
eval_js 'window.dispatchEvent(new Event("focus")); return true;'
advance 2
snapshot
key_press Escape
eval_js 'const c=document.querySelector("canvas"),r=c.getBoundingClientRect(),x=r.left+r.width*0.7,y=r.top+r.height*0.5; c.dispatchEvent(new PointerEvent("pointerdown",{bubbles:true,pointerId:32,pointerType:"mouse",button:0,buttons:1,clientX:x,clientY:y})); return true;'
click_overlay_button continue
snapshot
eval_js 'const c=document.querySelector("canvas"),r=c.getBoundingClientRect(),x=r.left+r.width*0.7,y=r.top+r.height*0.5; c.dispatchEvent(new PointerEvent("pointermove",{bubbles:true,pointerId:32,pointerType:"mouse",buttons:1,clientX:x,clientY:y})); return true;'
advance 2
snapshot
eval_js 'const c=document.querySelector("canvas"),r=c.getBoundingClientRect(),x=r.left+r.width*0.7,y=r.top+r.height*0.5; c.dispatchEvent(new PointerEvent("pointerup",{bubbles:true,pointerId:32,pointerType:"mouse",button:0,buttons:0,clientX:x,clientY:y})); return true;'
advance 2
snapshot
assert_trace assert_input_edges.py
