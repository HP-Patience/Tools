import { spawn } from 'node:child_process';
import { createInterface } from 'node:readline';
import { createServer } from 'vite';

let backend, vite, stopping = false;
async function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  if (vite) await vite.close();
  if (backend && backend.exitCode === null) backend.kill();
  process.exit(code);
}
process.on('SIGINT', () => stop());
process.on('SIGTERM', () => stop());
try {
  backend = spawn(process.env.PYTHON || 'python', ['-u', 'app.py', '--report-port'], {
    cwd:new URL('../',import.meta.url),
    env:{...process.env, MAILBOX_PORT:process.env.MAILBOX_DEV_BACKEND_PORT || '48373', MAILBOX_AUTH:'0', PYTHONIOENCODING:'utf-8'},
    stdio:['ignore','pipe','inherit'], windowsHide:true,
  });
  const backendPort = await new Promise((resolve,reject) => {
    const timer=setTimeout(()=>reject(new Error('Python backend did not become ready.')),15000);
    const lines=createInterface({input:backend.stdout});
    backend.once('error',error=>{clearTimeout(timer);reject(error);});
    backend.once('exit',code=>{clearTimeout(timer);reject(new Error(`Python backend exited (${code}).`));});
    lines.on('line',line=>{
      try {
        const data=JSON.parse(line);
        if(Number.isInteger(data.mailroom_port)) { clearTimeout(timer);resolve(data.mailroom_port);return; }
      } catch {}
      console.log(line);
    });
  });
  // Use the port reported by our child, never an unrelated service on the preferred port.
  process.env.MAILBOX_DEV_BACKEND_PORT=String(backendPort);
  backend.on('exit',code=>{if(!stopping)stop(code || 1);});
  vite=await createServer();
  await vite.listen();
  vite.printUrls();
} catch(error) {
  console.error(error.message);
  await stop(1);
}
