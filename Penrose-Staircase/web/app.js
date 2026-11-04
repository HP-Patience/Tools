'use strict';
const $ = (id) => document.getElementById(id);
const canvas = $('scene'), ctx = canvas.getContext('2d');
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
const state = {data:null, theme:'pool', light:70, zoom:1, panX:0, panY:0, motion:!reducedMotion.matches, mode:"curated", catalog:[], explain:false, time:0};
const palettes = {
 pool: {wall:'#e3eadd',shade:'#8ba99b',floor:'#b5c7b6',water:'#76a99b',deep:'#396f64',rim:'#e0e7d5',top:'#f1efdc',front:'#b8cbb9',side:'#779d8f',line:'#426b5d'},
 plaster: {wall:'#eee9dc',shade:'#b8ae9c',floor:'#cec8b8',water:'#b4ad98',deep:'#888675',rim:'#e9e1cf',top:'#f5edda',front:'#d0c6ac',side:'#aaa38c',line:'#827963'},
 ink: {wall:'#e4e1d4',shade:'#a4a69a',floor:'#c7c8b9',water:'#afb5a3',deep:'#747e6e',rim:'#e9e6d6',top:'#f1edde',front:'#c0c3b1',side:'#899380',line:'#4c5749'}
};
let cssWidth=0, cssHeight=0, pixelRatio=1, stageScale=1, stageOffsetX=0, stageOffsetY=0;
let architecture=null, reflection=null, room=null, basin=null, foreground=null, geom=null, requestId=0, timer, drag=null, lastFrame=0;
const path = (g, pts) => {g.beginPath();pts.forEach((p,i)=>i?g.lineTo(...p):g.moveTo(...p));g.closePath();};
function polygon(g,pts,fill,stroke){path(g,pts);g.fillStyle=fill;g.fill();if(stroke){g.strokeStyle=stroke;g.lineWidth=.8;g.stroke();}}
function line(g,a,b,color,width=1){g.beginPath();g.moveTo(...a);g.lineTo(...b);g.strokeStyle=color;g.lineWidth=width;g.stroke();}
function mix(a,b,f){const c=(x)=>x.match(/\w\w/g).map(v=>parseInt(v,16));const x=c(a.slice(1)),y=c(b.slice(1));return '#'+x.map((v,i)=>Math.round(v+(y[i]-v)*f).toString(16).padStart(2,'0')).join('');}
function surface(){const c=document.createElement('canvas');c.width=1800;c.height=1368;const g=c.getContext('2d');g.scale(1.8,1.8);return [c,g];}
const roomLayout=globalThis.PenroseRoom;
const poolSlope=roomLayout.slope, poolOuter=roomLayout.outer, poolInner=roomLayout.inner;
const lerpPoint=(a,b,t)=>a.map((v,i)=>v+(b[i]-v)*t);
const lower=(p,d)=>[p[0],p[1]+d];
function buildRoom(){
 const [c,roomG]=surface(),p=palettes[state.theme];
 let g=roomG;
 let sky=g.createLinearGradient(0,0,0,760);sky.addColorStop(0,p.wall);sky.addColorStop(1,p.floor);g.fillStyle=sky;g.fillRect(0,0,1000,760);
 const {corner,left:wallLeft,right:wallRight,floor}=roomLayout;
 polygon(g,[[0,0],[corner[0],0],corner,wallLeft],p.wall);
 let side=g.createLinearGradient(corner[0],100,1100,100);side.addColorStop(0,mix(p.shade,p.wall,.28));side.addColorStop(1,p.wall);
 polygon(g,[[corner[0],0],[1000,0],wallRight,corner],side);
 // All tile axes, wall/floor seams, and pool edges share one projection.
 for(let y=-300;y<610;y+=29){line(g,[0,y+corner[0]*poolSlope],[corner[0],y],'#456b5310',.7);line(g,[corner[0],y],[1000,y+(1000-corner[0])*poolSlope],'#456b5310',.7);}
 for(let x=0;x<1000;x+=31)line(g,[x,0],[x,650],'#456b530c',.7);
 polygon(g,floor,p.floor);
 g.save();path(g,floor);g.clip();
 for(let v=-900;v<1200;v+=42){line(g,[0,v],[1000,v+1000*poolSlope],'#395d451c');line(g,[0,v],[1000,v-1000*poolSlope],'#395d451c');}
 // A restrained wall-foot seam makes the surrounding walkway legible.
 line(g,wallLeft,corner,mix(p.floor,p.deep,.20),1.5);
 line(g,corner,wallRight,mix(p.floor,p.deep,.20),1.5);
 g.restore();
 // High clerestory. The bright plane, not a decorative UI frame, lights the scene.
 polygon(g,[[722,42],[928,127],[928,239],[722,147]],mix(p.shade,p.deep,.18));
 polygon(g,[[731,47],[927,129],[927,224],[731,138]],'#f7f6df');
 for(let x=775;x<922;x+=49){const y=47+(x-731)*.418;line(g,[x,y],[x,y+92],mix(p.wall,p.shade,.3),5);}
 polygon(g,[[722,147],[928,239],[938,231],[731,138]],mix(p.rim,p.shade,.12));
 g.save();g.globalAlpha=.08+state.light*.002;
 const beam=g.createLinearGradient(760,145,410,610);beam.addColorStop(0,'#ffffed');beam.addColorStop(1,'#fffedf00');
 polygon(g,[[733,139],[929,224],[638,662],[136,521]],beam);g.restore();
 // Keep the room fixed; pool, stairs, reflections and overlays move together.
 room=c;
 const [basinCanvas,basinG]=surface();g=basinG;
 // A single coherent projected plane, shared by the pool and foundation solver.
 const [left,back,right,front]=poolOuter;
 const plinthDepth=roomLayout.plinthDepth;
 // Cast the contact shadow from the BOTTOM outline directly onto the floor.
 // No Y-offset: an offset shadow made the slab read as hovering.
 g.save();path(g,roomLayout.floor.map(v=>v.map((n,i)=>n-roomLayout.placement[i])));g.clip();g.shadowColor='#274b3a48';g.shadowBlur=12;
 polygon(g,roomLayout.ground,mix(p.floor,p.deep,.25));g.restore();
 polygon(g,[left,front,lower(front,plinthDepth),lower(left,plinthDepth)],mix(p.rim,p.shade,.25));
 polygon(g,[front,right,lower(right,plinthDepth),lower(front,plinthDepth)],mix(p.rim,p.shade,.47));
 line(g,lower(left,plinthDepth),lower(front,plinthDepth),'#274b3a55',1.2);
 line(g,lower(front,plinthDepth),lower(right,plinthDepth),'#274b3a55',1.2);
 polygon(g,poolOuter,p.rim,'#5c7b5b25');
 let water=g.createLinearGradient(520,290,520,695);water.addColorStop(0,p.deep);water.addColorStop(.65,p.water);water.addColorStop(1,mix(p.water,p.rim,.3));
 polygon(g,poolInner,water);
 // Back pool edges belong behind the building.
 for(const [i,j] of [[0,1],[1,2]])polygon(g,[poolInner[i],poolInner[j],lower(poolInner[j],10),lower(poolInner[i],10)],mix(p.deep,p.water,.23));
 g.save();path(g,poolInner);g.clip();
 for(let y=-50;y<1100;y+=25){line(g,[0,y],[1000,y+1000*poolSlope],'#e4eedb12',.8);line(g,[0,y],[1000,y-1000*poolSlope],'#e4eedb12',.8);}
 let depth=g.createRadialGradient(520,470,30,520,510,360);depth.addColorStop(0,'#244e3a40');depth.addColorStop(1,'#2c6c4800');g.fillStyle=depth;g.fillRect(0,250,1000,460);g.restore();
 // Foreground coping is a separate layer, not a clip of the entire building.
 const [fg,frontG]=surface();
 for(const [i,j] of [[0,3],[3,2]]){
  polygon(frontG,[poolOuter[i],poolOuter[j],poolInner[j],poolInner[i]],p.rim,'#5c7b5b25');
  for(let k=1;k<20;k++)line(frontG,lerpPoint(poolOuter[i],poolOuter[j],k/20),lerpPoint(poolInner[i],poolInner[j],k/20),'#738b702b',.8);
 }
 foreground=fg;
 basin=basinCanvas;
}
function buildArchitecture(){
 if(!state.data)return;
 const p=palettes[state.theme];
 // All fitting and water-plane placement now come from the tested geometry solver.
 geom=state.data.scene;
 if(!geom || geom.clearance<37.9)throw new Error('Invalid foundation placement');
 const [c,g]=surface();
 for(const poly of geom.polygons){
  const points=poly.points,ys=points.map(v=>v[1]),xs=points.map(v=>v[0]);
  const minY=Math.min(...ys),maxY=Math.max(...ys),minX=Math.min(...xs),maxX=Math.max(...xs);
  let grad=g.createLinearGradient(minX,minY,maxX,maxY+1);
  const col=p[poly.face], brightness=(state.light-50)/500;
  grad.addColorStop(0,mix(col,'#ffffff',.09+Math.max(0,brightness)));
  grad.addColorStop(1,mix(col,p.deep,poly.face==='top'?.025:.17-Math.max(0,brightness)));
  polygon(g,points,grad);
  g.save();path(g,points);g.clip();
  // Tile lines follow each face's projected axes, never screen-aligned wallpaper.
  const step=14;
  g.strokeStyle=state.theme==='ink'?'#364a333d':'#416b5625';g.lineWidth=.55;
  g.beginPath();
  if(poly.face==='top'){
   for(let y=-650;y<1250;y+=step){g.moveTo(0,y);g.lineTo(1000,y+462);g.moveTo(0,y);g.lineTo(1000,y-462);}
  }else{
   const slope=poly.face==='front'?.462:-.462;
   for(let x=0;x<1000;x+=step*1.7){g.moveTo(x,0);g.lineTo(x,760);}
   for(let y=-650;y<1250;y+=step){g.moveTo(0,y);g.lineTo(1000,y+1000*slope);}
  }
  g.stroke();
  if(poly.face!=='top'){
   const ambient=g.createLinearGradient(0,minY,0,maxY);ambient.addColorStop(0,'#173f3120');ambient.addColorStop(.25,'#173f3100');ambient.addColorStop(1,'#173f3130');g.fillStyle=ambient;g.fillRect(minX,minY,maxX-minX,maxY-minY);
  }
  if(state.theme==='ink'&&poly.face!=='top'){
   for(let y=-900;y<1300;y+=5)line(g,[0,y],[1000,y+900],'#27372313',.65);
  }
  g.restore();
  path(g,points);g.lineWidth=poly.face==='top'?.8:.65;g.strokeStyle=poly.face==='top'?'#f9fbe8b0':'#375e4c37';g.stroke();
 }
 architecture=c;
 // Cache an artistic reflection anchored to the visible foundation edge at each X.
 const [rc,rg]=surface();rg.save();path(rg,poolInner);rg.clip();rg.globalAlpha=.12;
 const [left,,right,front]=geom.footprint;
 for(let x=Math.floor(left[0]);x<right[0];x+=3){
  const a=x<front[0]?left:front,b=x<front[0]?front:right;
  const y=a[1]+(x-a[0])*(b[1]-a[1])/(b[0]-a[0]);
  rg.save();rg.beginPath();rg.rect(x,y,3,760-y);rg.clip();rg.translate(0,y*1.24);rg.scale(1,-.24);rg.drawImage(c,0,0,1000,760);rg.restore();
 }
 rg.restore();reflection=rc;
}
function rebuild(){buildRoom();buildArchitecture();render();}
function drawWater(g,t){
 const p=palettes[state.theme];g.save();path(g,poolInner);g.clip();
 // Gentle procedural caustics. No textures, CDN, or remote image requests.
 g.lineWidth=.8;
 for(let row=0;row<20;row++){
  g.beginPath();for(let x=65;x<965;x+=9){const y=330+row*20+Math.sin(x*.019+t*.32+row*1.37)*5+Math.sin(x*.043-row+t*.23)*2; x===65?g.moveTo(x,y):g.lineTo(x,y);}
  g.strokeStyle=`rgba(232,247,208,${.055+Math.sin(row*2.7)*.022})`;g.stroke();
 }
 for(let i=0;i<6;i++){
  g.beginPath();g.ellipse(245+i*115,515+Math.sin(i*2)*59,30+Math.sin(t*.4+i)*8,9,0,0,Math.PI*2);g.strokeStyle='#e6f2cd16';g.stroke();
 }
 // Low-contrast artistic reflection, compressed into the basin plane.
 if(reflection)g.drawImage(reflection,0,0,1000,760);
 g.restore();
}
function drawWorld(g){
 g.drawImage(room,0,0,1000,760);
 g.save();g.translate(...roomLayout.placement);
 if(basin)g.drawImage(basin,0,0,1000,760);
 drawWater(g,state.time);
 if(architecture){
  // The shadow and low foundation follow the actual footprint, not a generic ellipse.
  const p=palettes[state.theme];
  g.save();path(g,poolInner);g.clip();g.shadowColor='#173d3540';g.shadowBlur=17;g.shadowOffsetY=6;
  polygon(g,geom.collar,mix(p.rim,p.deep,.33));g.restore();
  polygon(g,geom.footprint,mix(p.water,p.deep,.25));
  g.drawImage(architecture,0,0,1000,760);
  // A continuous contact line makes the common water plane legible.
  line(g,geom.footprint[0],geom.footprint[3],'#254f3e40',1.15);
  line(g,geom.footprint[3],geom.footprint[2],'#254f3e40',1.15);
 }
 if(foreground)g.drawImage(foreground,0,0,1000,760);
 if(state.explain&&geom){
  const r=geom.route;g.save();g.strokeStyle='#a05c39';g.lineWidth=1.6;g.setLineDash([5,5]);path(g,r);g.stroke();g.setLineDash([]);
  r.forEach((p,i)=>{g.beginPath();g.arc(...p,i===0?5:2.1,0,Math.PI*2);g.fillStyle=i===0?'#a05c39':'#fcf7e7';g.fill();});
  g.font='11px Georgia';g.fillStyle='#8b4e2b';g.fillText('START / END',r[0][0]+11,r[0][1]-8);g.restore();
 }
 g.restore(); // End the shared pool assembly placement.
 // Soft environmental vignette and photographic warmth.
 const glow=g.createRadialGradient(650,200,30,520,365,700);glow.addColorStop(0,'#ffffe513');glow.addColorStop(.7,'#e9efcc00');glow.addColorStop(1,'#28544023');g.fillStyle=glow;g.fillRect(0,0,1000,760);
 if(state.light<50){g.fillStyle=`rgba(16,43,35,${(50-state.light)*.003})`;g.fillRect(0,0,1000,760);}
}
function render(){
 if(!room||!cssWidth)return;
 ctx.setTransform(pixelRatio,0,0,pixelRatio,0,0);ctx.fillStyle=palettes[state.theme].floor;ctx.fillRect(0,0,cssWidth,cssHeight);
 ctx.save();ctx.translate(cssWidth/2+state.panX,cssHeight/2+state.panY);ctx.scale(state.zoom,state.zoom);ctx.translate(-cssWidth/2,-cssHeight/2);ctx.translate(stageOffsetX,stageOffsetY);ctx.scale(stageScale,stageScale);drawWorld(ctx);ctx.restore();
}
function resize(){const r=canvas.getBoundingClientRect();cssWidth=r.width;cssHeight=r.height;pixelRatio=Math.min(devicePixelRatio||1,2);canvas.width=Math.round(cssWidth*pixelRatio);canvas.height=Math.round(cssHeight*pixelRatio);stageScale=Math.min(cssWidth/1000,cssHeight/760);stageOffsetX=(cssWidth-1000*stageScale)/2;stageOffsetY=(cssHeight-760*stageScale)/2;render();}
function toast(msg){$('toast').textContent=msg;$('toast').classList.add('visible');clearTimeout(timer);timer=setTimeout(()=>$('toast').classList.remove('visible'),3200);}
async function load(n){
 if(!Number.isInteger(n)||n<1||n>10000){toast('请输入 1 到 10000 之间的整数');$('number').value=state.data?.number||25;return;}
 const id=++requestId;
 try{const response=await fetch(`/api/staircase?n=${n}`);if(!response.ok)throw new Error('geometry');const data=await response.json();if(id!==requestId)return;state.data=data;$('number').value=n;$('specimen').textContent=`Nº ${String(n).padStart(4,'0')}`;$('stats').textContent=`${data.steps} 级台阶 / 底座已校准 / ${state.mode==='curated'?'精选场景':'全部编号'}`;reset();buildArchitecture();render();}
 catch(error){if(id!==requestId)return;toast('生成失败，请确认本地服务仍在运行，再点击「生成」重试。');}
}
function reset(){state.zoom=1;state.panX=state.panY=0;$('reset').textContent='100%';render();}
function zoom(factor){state.zoom=Math.max(.6,Math.min(2.5,state.zoom*factor));$('reset').textContent=Math.round(state.zoom*100)+'%';render();}
function step(delta){
 const n=state.data?.number||25;
 if(state.mode==='curated'&&state.catalog.length){
  const list=state.catalog;let next=delta>0?list.find(v=>v>n):[...list].reverse().find(v=>v<n);
  if(next===undefined)next=delta>0?list[0]:list[list.length-1];load(next);
 }else load(Math.max(1,Math.min(10000,n+delta)));
}
function setMode(value){state.mode=value;$('catalog-mode').value=value;$('catalog-note').textContent=value==='curated'?'精选比例 · 箭头切换':'全部 10000 种 · 含极端比例';if(state.data)$('stats').textContent=`${state.data.steps} 级台阶 / 底座已校准 / ${value==='curated'?'精选场景':'全部编号'}`;}
$('catalog-mode').onchange=()=>{setMode($('catalog-mode').value);if(state.mode==='curated'&&state.catalog.length&&!state.catalog.includes(state.data?.number))load(25);};
async function fetchCatalog(){try{const r=await fetch('/api/catalog');if(!r.ok)throw Error('catalog');state.catalog=await r.json();}catch{state.catalog=[];setMode('all');$('catalog-mode').disabled=true;toast('精选列表暂不可用，已切换全部编号');}}

$('number-form').addEventListener('submit',e=>{e.preventDefault();const n=Number($('number').value);if(Number.isInteger(n)&&n>=1&&n<=10000&&state.mode==='curated'&&!state.catalog.includes(n))setMode('all');load(n);});
$('previous').onclick=()=>step(-1);$('next').onclick=()=>step(1);$('next-hero').onclick=()=>step(1);
$('zoom-in').onclick=()=>zoom(1.15);$('zoom-out').onclick=()=>zoom(1/1.15);$('reset').onclick=reset;
canvas.addEventListener('wheel',e=>{e.preventDefault();zoom(Math.exp(-e.deltaY*.001));},{passive:false});
canvas.addEventListener('pointerdown',e=>{drag={x:e.clientX,y:e.clientY,px:state.panX,py:state.panY};canvas.setPointerCapture(e.pointerId);});
canvas.addEventListener('pointermove',e=>{if(!drag)return;state.panX=Math.max(-cssWidth*.6,Math.min(cssWidth*.6,drag.px+e.clientX-drag.x));state.panY=Math.max(-cssHeight*.6,Math.min(cssHeight*.6,drag.py+e.clientY-drag.y));render();});
canvas.addEventListener('pointerup',()=>drag=null);canvas.addEventListener('pointercancel',()=>drag=null);canvas.addEventListener('lostpointercapture',()=>drag=null);
canvas.addEventListener('keydown',e=>{const delta=25;if(e.key==='0')reset();else if(e.key==='+'||e.key==='=')zoom(1.15);else if(e.key==='-')zoom(1/1.15);else if(e.key==='ArrowLeft')state.panX-=delta;else if(e.key==='ArrowRight')state.panX+=delta;else if(e.key==='ArrowUp')state.panY-=delta;else if(e.key==='ArrowDown')state.panY+=delta;else return;e.preventDefault();state.panX=Math.max(-cssWidth*.6,Math.min(cssWidth*.6,state.panX));state.panY=Math.max(-cssHeight*.6,Math.min(cssHeight*.6,state.panY));render();});
for(const button of document.querySelectorAll('[data-theme]'))button.onclick=()=>{state.theme=button.dataset.theme;document.querySelectorAll('[data-theme]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));$('scene-title').textContent={pool:'01 / 静水中庭',plaster:'02 / 石膏习作',ink:'03 / 版画回廊'}[state.theme];rebuild();};
$('light').oninput=e=>{state.light=Number(e.target.value);$('light-value').textContent=state.light+'%';rebuild();};
function syncMotion(){$('motion').setAttribute('aria-pressed',String(state.motion));$('motion-icon').textContent=state.motion?'Ⅱ':'▷';$('motion-label').textContent=state.motion?'暂停水纹':'开启水纹';}
$('motion').onclick=()=>{state.motion=!state.motion;syncMotion();};syncMotion();
reducedMotion.addEventListener('change',e=>{if(e.matches){state.motion=false;syncMotion();}});
$('explain').onclick=()=>{state.explain=!state.explain;$('explain').setAttribute('aria-pressed',String(state.explain));$('explanation').hidden=!state.explain;render();};
$('fullscreen').onclick=async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await document.querySelector('.viewer').requestFullscreen();}catch{toast('当前浏览器不支持全屏，请尝试 F11');}};
$('about').onclick=()=>$('about-dialog').showModal();$('close-about').onclick=$('back-scene').onclick=()=>$('about-dialog').close();
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&state.explain){state.explain=false;$('explanation').hidden=true;$('explain').setAttribute('aria-pressed','false');render();}});
$('export').onclick=()=>{
 if(!state.data){toast('请等待空间加载完成');return;}
 const c=document.createElement('canvas');c.width=3000;c.height=2280;const g=c.getContext('2d');g.scale(3,3);drawWorld(g);
 g.fillStyle='#294c3bb3';g.font='11px Georgia';g.fillText(`PENROSE ATRIUM   /   No. ${state.data.number}   /   ${state.theme.toUpperCase()}`,30,735);
 c.toBlob(blob=>{if(!blob){toast('导出失败，请重试');return;}const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=`penrose-${state.data.number}-${state.theme}.png`;a.click();setTimeout(()=>URL.revokeObjectURL(url),30000);toast('已导出 3000 × 2280 PNG 图像');},'image/png');
};
function animate(now){if(now-lastFrame>40){const dt=lastFrame?Math.min((now-lastFrame)/1000,.1):0;lastFrame=now;if(state.motion&&!document.hidden){state.time+=dt;render();}}requestAnimationFrame(animate);}
new ResizeObserver(resize).observe(canvas);rebuild();resize();fetchCatalog();load(25);requestAnimationFrame(animate);

