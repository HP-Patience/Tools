import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { atlasDevPlugin } from "./scripts/dev-plugin.ts";
export default defineConfig({
  plugins: [react(), atlasDevPlugin()],
  define: {
    __ATLAS_RELEASE__: JSON.stringify({
      version: "local",
      builtAt: "",
      sourceHash: "",
      mapHash: "",
    }),
  },
  build: {
    outDir: "release",
    assetsInlineLimit: 0,
    sourcemap: false,
    emptyOutDir: true,
    chunkSizeWarningLimit: 650,
  },
  server: { host: "127.0.0.1", strictPort: true },
});
