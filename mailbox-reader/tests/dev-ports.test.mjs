import test from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:net';
import { spawn } from 'node:child_process';
import { once } from 'node:events';

async function occupy() {
  const server=createServer(); server.listen(0,'127.0.0.1'); await once(server,'listening'); return server;
}
test('development changes occupied frontend and backend ports and preserves API proxy', {timeout:30000}, async()=>{
  const front=await occupy(), back=await occupy();
  const child=spawn(process.execPath,['scripts/dev.mjs'],{
    cwd:new URL('../',import.meta.url),
    env:{...process.env,NO_COLOR:'1',MAILBOX_DEV_PORT:String(front.address().port),MAILBOX_DEV_BACKEND_PORT:String(back.address().port)},
    windowsHide:true,stdio:['ignore','pipe','pipe'],
  });
  try {
    const url=await new Promise((resolve,reject)=>{
      let output='';
      const timer=setTimeout(()=>reject(new Error('Startup timed out: '+output)),15000);
      child.stdout.on('data',chunk=>{
        output+=chunk;
        const match=output.match(/Local:\s+(http:\/\/127\.0\.0\.1:\d+\/)/);
        if(match){clearTimeout(timer);resolve(match[1]);}
      });
      child.stderr.on('data',chunk=>output+=chunk);
      child.once('exit',code=>{clearTimeout(timer);reject(new Error(`Exited ${code}: ${output}`));});
    });
    assert.notEqual(Number(new URL(url).port),front.address().port);
    const session=await (await fetch(url+'api/session')).json();
    const response=await fetch(url+'api/preview',{method:'POST',headers:{'Content-Type':'application/json','Origin':url.slice(0,-1),'X-Session-Token':session.token},body:JSON.stringify({text:'test@example.com----DEMO----00000000-0000-4000-8000-000000000001----DEMO'})});
    assert.equal(response.status,200);
    assert.equal((await response.json()).counts.valid,1);
    const rejected=await fetch(url+'api/session',{headers:{Origin:'https://untrusted.example'}});
    assert.equal(rejected.status,403);
  } finally {
    if(process.platform==='win32'){
      const kill=spawn('taskkill',['/pid',String(child.pid),'/t','/f'],{windowsHide:true,stdio:'ignore'});
      await once(kill,'exit');
    }else{child.kill('SIGTERM');await once(child,'exit');}
    front.close();back.close();
  }
});
