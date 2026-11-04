'use strict';
const assert=require('node:assert/strict');
const room=require('./room-layout.js');
const wallY=x=>room.corner[1]+Math.abs(x-room.corner[0])*room.slope;
function checkWalkway(points,wallHeight,gap){
 for(const [x,y] of points)assert.ok(y-wallHeight(x)>=gap-1e-7,`Pool crosses room wall at ${x},${y}`);
}
const placed=points=>points.map(p=>p.map((v,i)=>v+room.placement[i]));
assert.ok(room.visibleWallGap>=48,'Keep a visible walkway after moving the pool');
checkWalkway(placed(room.outer),wallY,room.visibleWallGap);
checkWalkway(placed(room.ground),wallY,room.visibleWallGap+room.plinthDepth);
// Top outline is more restrictive than the slab's ground-contact footprint.
checkWalkway(room.outer,wallY,room.wallGap);
checkWalkway(room.ground,wallY,room.wallGap+room.plinthDepth);
for(let i=0;i<4;i++){
 const a=room.outer[i],b=room.outer[(i+1)%4];
 assert.ok(Math.abs(Math.abs((b[1]-a[1])/(b[0]-a[0]))-room.slope)<1e-9);
 assert.equal(room.ground[i][0],a[0]);
 assert.equal(room.ground[i][1],a[1]+room.plinthDepth);
 assert.ok(room.ground[i][1]<room.height);
}
// Prove the new test catches the previous fixed wall/floor coordinates.
const legacyWall=x=>x<=635?602+(340-602)*x/635:340+(510-340)*(x-635)/365;
assert.throws(()=>checkWalkway(room.outer,legacyWall,0));
(async()=>{
 const data=await (await fetch('http://127.0.0.1:8767/api/staircase?n=31')).json();
 assert.deepEqual(room.outer,data.scene.poolOuter);
 assert.deepEqual(room.inner,data.scene.poolInner);
 console.log('PASS: floor clearance, ground contact, shared pool projection, and legacy regression.');
 console.log(`Minimum projected vertical walkway gap: ${room.visibleWallGap}; plinth depth: ${room.plinthDepth}`);
})().catch(error=>{console.error(error);process.exitCode=1;});
