#!/usr/bin/env bash
set -euo pipefail

: "${PORT:?PORT is required}"

DIR="$(cd "$(dirname "$0")" && pwd)"
source "$DIR/../runtime_testlib.sh"

reset_trace() {
  TRACE="$EVIDENCE/$1"
  : > "$TRACE"
}

capture_eval() {
  local name="$1"
  local code response
  code="$(cat)"
  response="$("${PLAY[@]}" eval "$code")"
  printf '%s\n' "$response" > "$EVIDENCE/$name"
  printf '%s\n' "$response" >> "$EVAL_LOG"
  python3 -c 'import json,sys; p=json.load(sys.stdin); raise SystemExit(1 if p.get("error") else 0)' <<< "$response"
}

snapshot_file() {
  "${PLAY[@]}" snapshot >> "$EVIDENCE/$1"
}

start_test
advance 90

capture_eval forbidden-semantics.json <<'JS'
const english = ['dodge','roll','dash','teleport','immunity','invulnerability','shield']
const chinese = ['闪避','翻滚','冲刺','传送','免疫','无敌帧','无敌','护盾']
const matches = []
const scan = (source, value) => {
  const text = typeof value === 'string' ? value : JSON.stringify(value ?? null)
  for (const word of english) {
    if (new RegExp(`(^|[^a-z])${word}([^a-z]|$)`, 'i').test(text)) matches.push({ source, word, text })
  }
  for (const word of chinese) if (text.includes(word)) matches.push({ source, word, text })
}
const visible = element => {
  const style = getComputedStyle(element)
  return style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity || 1) > 0 && element.getClientRects().length > 0
}
for (const element of document.querySelectorAll('body *')) {
  if (!visible(element)) continue
  scan(`dom:${element.id || element.className || element.tagName}`, [element.textContent, element.getAttribute('aria-label'), element.title, element.getAttribute('alt')])
}
const inputMap = await fetch('/config/input-map.json').then(response => response.json())
scan('input-map', inputMap)
for (const node of sceneTree.nodes.values()) {
  if (node.enabled === false) continue
  scan(`node:${node.name}:config`, node.config)
  scan(`node:${node.name}:runtime`, node.runtimeState?.())
  const visual = node.getVisualObject?.()
  scan(`node:${node.name}:visual`, {
    texture: visual?.texture?.key,
    frame: visual?.frame?.name,
    declaredTexture: node._visualDef?.texture,
    clip: node.animationPlayer?.currentClipName,
  })
}
return { keywords: [...english, ...chinese], count: matches.length, matches }
JS

capture_eval formal-source-scan.json <<'JS'
await document.fonts.load('16px FusionPixel')
const manifest = sceneTree.assetManifest || {}
const invalidVisuals = []
for (const node of sceneTree.nodes.values()) {
  if (node.enabled === false || !node._visualDef) continue
  const declared = node._visualDef.texture
  const active = node.getVisualObject?.()?.texture?.key
  for (const [role, key] of [['declared', declared], ['active', active]]) {
    if (!key) continue
    const entry = manifest[key]
    if (!entry || String(entry.type).startsWith('placeholder') || /placeholder|prototype|frame_/i.test(key)) {
      invalidVisuals.push({ node: node.name, role, key, type: entry?.type || null })
    }
  }
}
const invalidDomAssets = []
for (const element of document.querySelectorAll('[data-manifest-key]')) {
  const key = element.dataset.manifestKey
  const entry = manifest[key]
  if (!entry || entry.type !== 'image' || String(entry.type).startsWith('placeholder')) invalidDomAssets.push({ key, type: entry?.type || null })
}
const resources = performance.getEntriesByType('resource').map(entry => entry.name)
const fonts = resources.filter(url => /\.(woff2?|ttf|otf)(\?|$)/i.test(url))
return {
  invalidVisuals,
  invalidDomAssets,
  fontLoaded: document.fonts.check('16px FusionPixel'),
  fontResources: fonts,
  remoteFontResources: fonts.filter(url => new URL(url, location.href).origin !== location.origin),
  artifactResources: resources.filter(url => url.includes('/assets/artifacts/')),
  enginePlaceholderResources: resources.filter(url => /\/engine\/(?:assets\/__placeholder_(?:image|atlas)__\.png|placeholder\.js)(?:\?|$)/i.test(url)),
  placeholderResources: resources.filter(url => /placeholder/i.test(url) && !/\/engine\/(?:assets\/__placeholder_(?:image|atlas)__\.png|placeholder\.js)(?:\?|$)/i.test(url)),
}
JS

reset_trace player-actions.jsonl
setup_combat '{"stage":1,"player":{"position":{"x":640,"y":360},"hp":100,"skill":{"cooldownRemaining":0,"buffRemaining":0,"lastRejected":null}},"enemies":[],"projectiles":[],"areas":[]}'
advance 1
snapshot
input_down move_right
advance 2
snapshot
input_down fire
advance 1
snapshot
input_up fire
input_tap skill
advance 1
snapshot
input_up move_right

reset_trace fang-actions.jsonl
setup_combat '{"stage":1,"player":{"position":{"x":640,"y":360}},"enemies":[{"type":"fang","position":{"x":1000,"y":360},"hp":60}],"projectiles":[],"areas":[]}'
advance 1
snapshot
setup_combat '{"stage":1,"player":{"position":{"x":640,"y":360}},"enemies":[{"type":"fang","position":{"x":700,"y":360},"hp":60}],"projectiles":[],"areas":[]}'
advance 1
snapshot
eval_js 'const enemy=sceneTree.findByTag("enemy")[0]; enemy.receiveDamage(enemy.hp,"visual-test"); return enemy.runtimeState();'
snapshot

reset_trace acolyte-actions.jsonl
setup_combat '{"stage":2,"player":{"position":{"x":640,"y":360}},"enemies":[{"type":"acolyte","position":{"x":1100,"y":360},"hp":40}],"projectiles":[],"areas":[]}'
advance 1
snapshot
setup_combat '{"stage":2,"player":{"position":{"x":640,"y":360}},"enemies":[{"type":"acolyte","position":{"x":900,"y":360},"hp":40}],"projectiles":[],"areas":[]}'
advance 1
snapshot
eval_js 'const enemy=sceneTree.findByTag("enemy")[0]; enemy.receiveDamage(enemy.hp,"visual-test"); return enemy.runtimeState();'
snapshot

reset_trace deacon-actions.jsonl
setup_combat '{"stage":1,"player":{"position":{"x":640,"y":360}},"enemies":[{"type":"deacon","position":{"x":1000,"y":360},"hp":220}],"projectiles":[],"areas":[]}'
advance 1
snapshot
setup_combat '{"stage":1,"player":{"position":{"x":640,"y":360}},"enemies":[{"type":"deacon","position":{"x":750,"y":360},"hp":220}],"projectiles":[],"areas":[]}'
advance 1
snapshot
setup_combat '{"stage":1,"player":{"position":{"x":640,"y":360}},"enemies":[{"type":"deacon","position":{"x":840,"y":360},"hp":220}],"projectiles":[],"areas":[]}'
advance 1
snapshot
eval_js 'const enemy=sceneTree.findByTag("enemy")[0]; enemy.receiveDamage(enemy.hp,"visual-test"); return enemy.runtimeState();'
snapshot

reset_trace bishop-actions.jsonl
setup_combat '{"stage":7,"player":{"position":{"x":640,"y":360}},"enemies":[{"type":"bishop","position":{"x":1000,"y":360},"hp":1500,"phase":1}],"projectiles":[],"areas":[]}'
advance 1
snapshot
setup_combat '{"stage":7,"player":{"position":{"x":640,"y":360}},"enemies":[{"type":"bishop","position":{"x":840,"y":360},"hp":1500,"phase":1}],"projectiles":[],"areas":[]}'
advance 1
snapshot
setup_combat '{"stage":7,"player":{"position":{"x":640,"y":360}},"enemies":[{"type":"bishop","position":{"x":865,"y":360},"hp":1500,"phase":1}],"projectiles":[],"areas":[]}'
advance 1
snapshot
setup_combat '{"stage":7,"player":{"position":{"x":640,"y":360}},"enemies":[{"type":"bishop","position":{"x":840,"y":360},"hp":1500,"phase":2,"phaseSlot":2}],"projectiles":[],"areas":[]}'
advance 1
snapshot
setup_combat '{"stage":7,"player":{"position":{"x":640,"y":360}},"enemies":[{"type":"bishop","position":{"x":840,"y":360},"hp":1500,"phase":1}],"projectiles":[],"areas":[]}'
eval_js 'const boss=sceneTree.findByTag("boss")[0]; boss.receiveDamage(750,"visual-phase"); return boss.runtimeState();'
snapshot
eval_js 'const boss=sceneTree.findByTag("boss")[0]; boss.receiveDamage(boss.hp,"visual-death"); return boss.runtimeState();'
snapshot

reset_trace fang-melee.jsonl
setup_combat '{"stage":1,"player":{"position":{"x":640,"y":360}},"enemies":[{"type":"fang","position":{"x":700,"y":360},"hp":60}],"projectiles":[],"areas":[]}'
advance 1
snapshot
take_screenshot fang-warning.png
eval_js 'const attack=sceneTree.findByTag("damaging").find(node=>node.runtimeState?.().warningDuration===0.65); if(!attack) throw new Error("Fang warning area missing"); attack._elapsed=attack.warningDuration; return attack.runtimeState();'
advance 1
snapshot
take_screenshot fang-impact.png

reset_trace deacon-melee.jsonl
setup_combat '{"stage":1,"player":{"position":{"x":640,"y":360}},"enemies":[{"type":"deacon","position":{"x":750,"y":360},"hp":220}],"projectiles":[],"areas":[]}'
advance 1
snapshot
take_screenshot deacon-warning.png
eval_js 'const attack=sceneTree.findByTag("damaging").find(node=>node.runtimeState?.().warningDuration===0.85); if(!attack) throw new Error("Deacon warning area missing"); attack._elapsed=attack.warningDuration; return attack.runtimeState();'
advance 1
snapshot
take_screenshot deacon-impact.png

reset_trace bishop-melee.jsonl
setup_combat '{"stage":7,"player":{"position":{"x":640,"y":360}},"enemies":[{"type":"bishop","position":{"x":840,"y":360},"hp":1500,"phase":1}],"projectiles":[],"areas":[]}'
advance 1
snapshot
take_screenshot bishop-warning.png
eval_js 'const attack=sceneTree.findByTag("boss_hazard").find(node=>node.runtimeState?.().warningDuration===1); if(!attack) throw new Error("Bishop warning area missing"); attack._elapsed=attack.warningDuration; return attack.runtimeState();'
advance 1
snapshot
take_screenshot bishop-impact.png

reset_trace stale-danger.jsonl
setup_combat '{"stage":1,"player":{"position":{"x":640,"y":360}},"enemies":[{"type":"fang","position":{"x":700,"y":360},"hp":60}],"projectiles":[],"areas":[]}'
advance 3
snapshot
eval_js 'const enemy=sceneTree.findByTag("enemy")[0]; enemy.receiveDamage(enemy.hp,"cleanup-fang"); return true;'
snapshot
setup_combat '{"stage":1,"player":{"position":{"x":640,"y":360}},"enemies":[{"type":"fang","position":{"x":700,"y":360},"hp":1,"behaviorState":"charge","stateTime":1,"attackId":"cleanup-room"}],"projectiles":[{"type":"dart","position":{"x":1000,"y":300},"angle":0,"damage":15,"speed":0,"attackId":"cleanup-room-dart"}],"areas":[{"type":"fang","position":{"x":720,"y":360},"attackId":"cleanup-room","phase":"warning"}]}'
snapshot
eval_js 'const director=sceneTree.root; const enemy=sceneTree.findByTag("enemy")[0]; enemy.receiveDamage(enemy.hp,"cleanup-room"); director.enemyCount=0; await director._handleClear(); return director.runtimeState();'
snapshot
setup_combat '{"stage":7,"player":{"position":{"x":640,"y":360}},"enemies":[{"type":"bishop","position":{"x":800,"y":360},"hp":1,"phase":2}],"projectiles":[{"type":"spear","position":{"x":900,"y":300},"angle":0,"damage":18,"speed":0,"attackId":"cleanup-boss-spear"}],"areas":[{"type":"ritual","position":{"x":700,"y":420},"attackId":"cleanup-boss-ritual","phase":"active"}]}'
snapshot
eval_js 'const boss=sceneTree.findByTag("boss")[0]; boss.receiveDamage(boss.hp,"cleanup-boss"); return true;'
advance 1
snapshot
take_screenshot stale-danger-after-boss.png

reset_trace feedback-cap.jsonl
setup_combat '{"stage":3,"player":{"position":{"x":640,"y":360}},"enemies":[],"projectiles":[],"areas":[]}'
eval_js 'const root=sceneTree.root; for(let i=0;i<64;i++) root.emit("damage_number",{amount:20,x:480+(i%8)*24,y:260+Math.floor(i/8)*24}); return true;'
snapshot
eval_js 'const root=sceneTree.root; for(let i=0;i<64;i++) root.emit("damage_number",{amount:20,x:500+(i%8)*24,y:280+Math.floor(i/8)*24}); return true;'
snapshot
take_screenshot crowded-feedback.png
advance 90
snapshot

setup_combat '{"stage":1,"player":{"position":{"x":640,"y":360}},"enemies":[],"projectiles":[],"areas":[]}'
eval_js 'const choice=sceneTree.root.getChild("SigilChoice"); choice.showOffer(["ash_crown","blood_prayer","close_flame"],()=>{}); return true;'
capture_eval text-reflow-choice.json <<'JS'
const box = element => { const r=element.getBoundingClientRect(); return {left:r.left,top:r.top,right:r.right,bottom:r.bottom,width:r.width,height:r.height} }
const root = sceneTree.ui.root
const elements = [...document.querySelectorAll('.up-card')].filter(e=>e.getClientRects().length).map((element,index)=>({role:'card',label:`card-${index}`,rect:box(element),scrollWidth:element.scrollWidth,clientWidth:element.clientWidth,scrollHeight:element.scrollHeight,clientHeight:element.clientHeight}))
const actions = [...document.querySelectorAll('.up-card-key-label')].map((element,index)=>({label:`action-${index}`,text:element.textContent,rect:box(element),scrollWidth:element.scrollWidth,clientWidth:element.clientWidth,scrollHeight:element.scrollHeight,clientHeight:element.clientHeight}))
return { bounds:box(root), elements, actions }
JS
take_screenshot text-reflow-desktop.png

capture_eval viewport-resize-portrait.json <<'JS'
const container=document.querySelector('#game-container')
const canvas=container.querySelector('canvas')
const desktopRect=container.getBoundingClientRect()
window.__visualIntegrationDesktopContainer={style:container.getAttribute('style'),canvasStyle:canvas.getAttribute('style'),width:desktopRect.width,height:desktopRect.height}
container.style.width='405px'; container.style.height='720px'; container.style.aspectRatio='auto'; container.style.maxWidth='none'
sceneTree.root.getChild('Input')._enableTouchMode()
sceneTree.root.scene.scale.refresh()
sceneTree.ui.sync()
await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))
const box = element => { const r=element.getBoundingClientRect(); return {left:r.left,top:r.top,right:r.right,bottom:r.bottom,width:r.width,height:r.height} }
const visible = element => getComputedStyle(element).display!=='none' && getComputedStyle(element).visibility!=='hidden' && element.getClientRects().length
const cards=[...document.querySelectorAll('.up-card')].filter(visible).map((element,index)=>({role:'card',label:`card-${index}`,rect:box(element),scrollWidth:element.scrollWidth,clientWidth:element.clientWidth,scrollHeight:element.scrollHeight,clientHeight:element.clientHeight}))
const commands=[...document.querySelectorAll('#touch-controls button,#touch-aim')].filter(visible).map((element,index)=>({role:'command',label:`touch-${index}`,rect:box(element),scrollWidth:element.scrollWidth,clientWidth:element.clientWidth,scrollHeight:element.scrollHeight,clientHeight:element.clientHeight}))
const input=sceneTree.root.getChild('Input').runtimeState()
const choice=sceneTree.root.getChild('SigilChoice').runtimeState()
const overlay=sceneTree.root.getChild('Overlay').runtimeState()
const actions=[...document.querySelectorAll('.up-card-key-label')].map((element,index)=>({label:`action-${index}`,text:element.textContent,rect:box(element),scrollWidth:element.scrollWidth,clientWidth:element.clientWidth,scrollHeight:element.scrollHeight,clientHeight:element.clientHeight}))
return {bounds:box(sceneTree.ui.root),elements:[...cards,...commands],actions,touchControlsVisible:input.touchControlsVisible,actionState:input.actionState,authority:choice.visible?'sigil-choice':overlay.authority}
JS
take_screenshot text-reflow-portrait.png

capture_eval touch-detail-action.json <<'JS'
const box = element => { const r=element.getBoundingClientRect(); return {left:r.left,top:r.top,right:r.right,bottom:r.bottom,width:r.width,height:r.height} }
const card=document.querySelector('.up-card')
const r=card.getBoundingClientRect()
for(const type of ['pointerdown','pointerup']) card.dispatchEvent(new PointerEvent(type,{bubbles:true,pointerId:93,pointerType:'touch',isPrimary:true,clientX:r.left+r.width/2,clientY:r.top+r.height/2}))
card.click()
await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))
const choice=sceneTree.root.getChild('SigilChoice').runtimeState()
const actions=[...document.querySelectorAll('.up-card-key-label')].map((element,index)=>({label:`action-${index}`,text:element.textContent,rect:box(element),scrollWidth:element.scrollWidth,clientWidth:element.clientWidth,scrollHeight:element.scrollHeight,clientHeight:element.clientHeight,ariaPressed:element.closest('.up-card')?.getAttribute('aria-pressed')}))
return {choice,actions}
JS

capture_eval touch-confirm-action.json <<'JS'
const card=document.querySelector('.up-card')
const r=card.getBoundingClientRect()
for(const type of ['pointerdown','pointerup']) card.dispatchEvent(new PointerEvent(type,{bubbles:true,pointerId:94,pointerType:'touch',isPrimary:true,clientX:r.left+r.width/2,clientY:r.top+r.height/2}))
card.click()
await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))
return {choice:sceneTree.root.getChild('SigilChoice').runtimeState(),overlayPresent:!!document.querySelector('#upgrade-overlay'),cardCount:document.querySelectorAll('.up-card').length}
JS

eval_js 'const container=document.querySelector("#game-container"); const canvas=container.querySelector("canvas"); const desktop=window.__visualIntegrationDesktopContainer; if(!desktop) throw new Error("desktop container baseline missing"); if(desktop.style===null) container.removeAttribute("style"); else container.setAttribute("style",desktop.style); container.style.width=`${desktop.width}px`; container.style.height=`${desktop.height}px`; sceneTree.root.scene.scale.refresh(); if(desktop.canvasStyle===null) canvas.removeAttribute("style"); else canvas.setAttribute("style",desktop.canvasStyle); delete window.__visualIntegrationDesktopContainer; await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))); sceneTree.ui.sync(); const restored=container.getBoundingClientRect(); const uiRect=sceneTree.ui.root.getBoundingClientRect(); if(Math.abs(restored.width-desktop.width)>1 || Math.abs(restored.height-desktop.height)>1) throw new Error(`desktop container restore mismatch ${restored.width}x${restored.height}`); if(Math.abs(uiRect.width-desktop.width)>1 || Math.abs(uiRect.height-desktop.height)>1) throw new Error(`desktop UI restore mismatch ${uiRect.width}x${uiRect.height}`); const choice=sceneTree.root.getChild("SigilChoice"); choice.hide(); sceneTree.root.scene.scene.resume(); sceneTree.running=true; return {width:restored.width,height:restored.height};'
setup_combat '{"stage":4,"player":{"position":{"x":640,"y":360},"hp":40},"enemies":[],"projectiles":[],"areas":[]}'
capture_eval text-reflow-route.json <<'JS'
const box = element => { const r=element.getBoundingClientRect(); return {left:r.left,top:r.top,right:r.right,bottom:r.bottom,width:r.width,height:r.height} }
const visible = element => getComputedStyle(element).display!=='none' && element.getClientRects().length
const elements=[...document.querySelectorAll('.route-label')].filter(visible).map((element,index)=>({role:'label',label:`route-${index}`,rect:box(element),scrollWidth:element.scrollWidth,clientWidth:element.clientWidth,scrollHeight:element.scrollHeight,clientHeight:element.clientHeight}))
return {bounds:box(sceneTree.ui.root),elements}
JS

setup_combat '{"stage":7,"player":{"position":{"x":640,"y":360},"hp":1,"sigils":["piercing_ember","ash_crown","sacred_nail","light_ember","rekindle","wide_radiance","close_flame","last_candle","blood_prayer"]},"enemies":[],"projectiles":[],"areas":[]}'
eval_js 'sceneTree.root.getChild("Overlay").showResult("death",{stage:7,sigils:["piercing_ember","ash_crown","sacred_nail","light_ember","rekindle","wide_radiance","close_flame","last_candle","blood_prayer"],remainingHp:0,damageSource:"失火主教的熄火仪式"}); return true;'
capture_eval text-reflow-result.json <<'JS'
const box = element => { const r=element.getBoundingClientRect(); return {left:r.left,top:r.top,right:r.right,bottom:r.bottom,width:r.width,height:r.height} }
const visible = element => getComputedStyle(element).display!=='none' && element.getClientRects().length
const panel=[...document.querySelectorAll('[id$="-panel"]')].find(visible)
if(!panel) throw new Error('visible result panel missing')
const elements=[{role:'panel',label:'result-panel',rect:box(panel),scrollWidth:panel.scrollWidth,clientWidth:panel.clientWidth,scrollHeight:panel.scrollHeight,clientHeight:panel.clientHeight},...[...panel.querySelectorAll('button')].filter(visible).map((element,index)=>({role:'command',label:`result-command-${index}`,rect:box(element),scrollWidth:element.scrollWidth,clientWidth:element.clientWidth,scrollHeight:element.scrollHeight,clientHeight:element.clientHeight}))]
return {bounds:box(sceneTree.ui.root),elements}
JS

capture_eval formal-asset-failure.json <<'JS'
const director=sceneTree.root
const scene=director.scene
const failuresBefore=director.runtimeState().assetFailures || []
const magentaCount=()=>scene.children.list.filter(object=>object?.type==='Rectangle' && object?.fillColor===0xff00ff).length
const result={}

const {VisualFactory}=await import('/engine/VisualFactory.js')
let before=magentaCount(), visualRejected=false, created=null
try { created=VisualFactory.create(scene,{type:'image',texture:'__runtime_missing_image__',width:32,height:32},{x:0,y:0},sceneTree.assetManifest) } catch(error) { visualRejected=true }
const magentaDelta=magentaCount()-before
created?.destroy?.()
result.visual={rejected:visualRejected || created==null,magentaDelta}

const player=sceneTree.findByTag('player')[0]
const visual=player.getVisualObject()
const badClip='__runtime_missing_frame_clip__'
player.animationPlayer.def.clips[badClip]={source:{type:'atlas',texture:'ember_keeper'},frames:['__runtime_missing_frame__'],loop:false}
let animationRejected=false
try { const accepted=player.animationPlayer.play(badClip); animationRejected=accepted===false } catch(error) { animationRejected=true }
await Promise.resolve()
const animationFailures=director.runtimeState().assetFailures || []
result.animation={rejected:animationRejected || animationFailures.length>failuresBefore.length,hidden:visual.visible===false || visual.alpha===0}
delete player.animationPlayer.def.clips[badClip]
visual.setVisible?.(true); visual.setAlpha?.(1); player.playAnim('idle')

const TileMap=(await import('/engine/scripts/TileMap.js')).default
const buildProbe=(config)=>{ const probe=new TileMap(); probe.scene=scene; probe.sceneTree=sceneTree; probe.config=config; return probe }
const actual=sceneTree.tilesets.sanctuary_tiles
let textureProbe=null, textureRejected=false
const missingDef={...structuredClone(actual),name:'__runtime_missing_tileset_texture__'}
try { textureProbe=buildProbe({tilesetDef:missingDef,layers:[{name:'probe',collision:false,data:[['floor_stone']]}]}); textureProbe.ready() } catch(error) { textureRejected=true }
try { textureProbe?.destroy?.() } catch {}
delete sceneTree.tilesets.__runtime_missing_tileset_texture__
result.tilesetTexture={rejected:textureRejected}

let semanticProbe=null, semanticRejected=false
try { semanticProbe=buildProbe({tileset:'sanctuary_tiles',layers:[{name:'probe',collision:false,data:[['__runtime_missing_semantic__']]}]}); semanticProbe.ready() } catch(error) { semanticRejected=true }
try { semanticProbe?.destroy?.() } catch {}
result.tileSemantic={rejected:semanticRejected}

const ui=sceneTree.ui
let syncRejected=false
try { ui.assetUrl('__runtime_missing_ui_key__') } catch(error) { syncRejected=true }
const asyncKey='__runtime_missing_ui_url__'
const oldEntry=ui.manifest[asyncKey]
ui.manifest[asyncKey]={type:'image',path:'assets/__runtime_missing_ui__.png'}
ui._assetUrlCache.delete(asyncKey)
const image=document.createElement('img')
ui.root.appendChild(image)
await new Promise(resolve=>{ const done=()=>setTimeout(resolve,0); image.addEventListener('error',done,{once:true}); ui.setImage(image,asyncKey); setTimeout(resolve,750) })
result.ui={syncRejected,asyncCleared:!image.getAttribute('src') || image.getAttribute('src')==='',asyncHidden:getComputedStyle(image).display==='none' || getComputedStyle(image).visibility==='hidden' || image.hidden}
image.remove(); ui._assetUrlCache.delete(asyncKey); if(oldEntry) ui.manifest[asyncKey]=oldEntry; else delete ui.manifest[asyncKey]

const vfx=await director.instantiate('entities/hit-spark.node.json',{x:640,y:360,texture:'__runtime_missing_vfx__',ttl:2})
await Promise.resolve()
const vfxState=vfx.runtimeState()
const vfxVisual=vfx.getVisualObject()
const failuresAfter=director.runtimeState().assetFailures || []
result.vfx={missingTextureKeys:vfxState.missingTextureKeys || [],hidden:vfxVisual?.visible===false || vfxVisual?.alpha===0,reported:failuresAfter.some(item=>item.texture==='__runtime_missing_vfx__')}
vfx.removeSelf()
return result
JS

TRACE="$EVIDENCE/player-actions.jsonl"
setup_combat '{"stage":1,"player":{"position":{"x":640,"y":360},"hp":15},"enemies":[],"projectiles":[{"type":"dart","position":{"x":640,"y":360},"angle":0,"damage":15,"speed":0,"attackId":"visual-player-death"}],"areas":[]}'
advance 1
snapshot
take_screenshot player-death.png

"${PLAY[@]}" console > "$EVIDENCE/console.json"
"${PLAY[@]}" network > "$EVIDENCE/network.json"
python3 "$DIR/assert_visual_integration.py" "$EVIDENCE"
