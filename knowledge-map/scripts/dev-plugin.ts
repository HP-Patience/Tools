import type { Plugin } from "vite";
import { mapFile, readValidMap, saveBackup } from "./files.ts";
import path from "node:path";
export function atlasDevPlugin(): Plugin {
  return {
    name: "atlas-local-data",
    apply: "serve",
    configureServer(server) {
      server.watcher.add(mapFile);
      let timer: ReturnType<typeof setTimeout> | undefined;
      const update = (file: string) => {
        if (path.resolve(file) !== mapFile) return;
        clearTimeout(timer);
        timer = setTimeout(
          () =>
            server.ws.send({ type: "custom", event: "atlas:update", data: {} }),
          220,
        );
      };
      server.watcher.on("change", update);
      server.watcher.on("add", update);
      server.watcher.on("unlink", update);
      server.httpServer?.once("close", () => {
        clearTimeout(timer);
        server.watcher.off("change", update);
        server.watcher.off("add", update);
        server.watcher.off("unlink", update);
      });
      server.middlewares.use("/__atlas/map", async (req, res, next) => {
        if (req.method !== "GET") {
          res.statusCode = 405;
          res.end("Method not allowed");
          return;
        }
        if (
          req.url &&
          req.url.split("?")[0] !== "/" &&
          req.url.split("?")[0] !== ""
        ) {
          next();
          return;
        }
        res.setHeader("Content-Type", "application/json; charset=utf-8");
        res.setHeader("Cache-Control", "no-store");
        try {
          const { raw } = await readValidMap();
          await saveBackup(raw);
          res.statusCode = 200;
          res.end(raw);
        } catch (error) {
          res.statusCode = 422;
          res.end(
            JSON.stringify({
              errors: [
                error instanceof Error ? error.message : "无法读取知识文件",
              ],
            }),
          );
        }
      });
    },
    handleHotUpdate(context) {
      if (path.resolve(context.file) === mapFile) return [];
    },
  };
}
