/* Shared room/pool projection. Also loadable by the Node regression test. */
(function(root){
 'use strict';
 const slope=.8/Math.sqrt(3), width=1000, height=760;
 const outer=[[65,485],[520,485-455*slope],[975,485],[520,485+455*slope]];
 const inner=[[110,485],[520,485-410*slope],[930,485],[520,485+410*slope]];
 const wallGap=96, plinthDepth=28;
 const placement=[0,-40]; // Move the complete pool assembly toward the corner.
 const visibleWallGap=wallGap+placement[1];
 // Both walls recede parallel to the pool edges. Leave a visible floor strip
 // even behind the raised TOP outline, not just beneath its ground footprint.
 const corner=[outer[1][0],outer[1][1]-wallGap];
 const left=[0,corner[1]+corner[0]*slope];
 const right=[width,corner[1]+(width-corner[0])*slope];
 const floor=[left,corner,right,[width,height],[0,height]];
 const ground=outer.map(([x,y])=>[x,y+plinthDepth]);
 const layout={slope,width,height,outer,inner,wallGap,plinthDepth,corner,left,right,floor,ground,placement,visibleWallGap};
 if(typeof module!=='undefined' && module.exports)module.exports=layout;
 else root.PenroseRoom=layout;
})(globalThis);
