import { mkdir, copyFile } from "node:fs/promises";
import path from "node:path";
// Tests never write the real learner's map.
const fixture = path.resolve(".local/e2e-map.json");
await mkdir(".local", { recursive: true });
await copyFile("data/map.json", fixture);
process.env.ATLAS_MAP_FILE = fixture;
process.env.ATLAS_BACKUP_DIR = path.resolve(".local/e2e-backups");
const { createServer } = await import("vite");
const server = await createServer({
  server: { port: 5174, host: "127.0.0.1", strictPort: true },
});
await server.listen();
