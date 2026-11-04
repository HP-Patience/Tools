import { defineConfig } from 'vite';
import { fileURLToPath } from 'node:url';

const backendPort = process.env.MAILBOX_DEV_BACKEND_PORT || '48373';
const devPort = Number(process.env.MAILBOX_DEV_PORT || 48372);
let actualPort = devPort;
const origin = () => `http://127.0.0.1:${actualPort}`;

export default defineConfig({
  root: fileURLToPath(new URL('./static', import.meta.url)),
  publicDir: false,
  plugins: [{
    name: 'local-only-api',
    configureServer(server) {
      server.httpServer.on('listening', () => { actualPort = server.httpServer.address().port; });
      server.middlewares.use((req, res, next) => {
        if (req.headers.host !== `127.0.0.1:${actualPort}` || (req.headers.origin && req.headers.origin !== origin())) {
          res.statusCode = 403;
          res.end('Local requests only');
          return;
        }
        next();
      });
    },
  }],
  server: {
    host: '127.0.0.1', port: devPort, strictPort: false,
    fs: { strict: true, allow: [fileURLToPath(new URL('./static', import.meta.url))] },
    proxy: {
      '/api': {
        target: `http://127.0.0.1:${backendPort}`, changeOrigin: true,
        configure(proxy) {
          proxy.on('proxyReq', (proxyReq, req) => {
            if (req.headers.origin === origin()) proxyReq.setHeader('Origin', `http://127.0.0.1:${backendPort}`);
          });
        },
      },
    },
  },
  build: { outDir: '../dist', emptyOutDir: true },
});
