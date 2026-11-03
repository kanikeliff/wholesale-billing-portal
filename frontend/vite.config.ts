import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv, type Plugin } from "vite";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { readFileSync, readdirSync } from "node:fs";

// Resolve PDF.js from React-PDF so the worker and decoders always match.
const require = createRequire(import.meta.url);
const pdfRoot = dirname(createRequire(require.resolve("react-pdf")).resolve("pdfjs-dist/package.json"));
function pdfAssets(): Plugin {
  const files = new Map<string, Buffer>([
    ["pdf.worker.min.mjs", readFileSync(join(pdfRoot, "build/pdf.worker.min.mjs"))],
    ...readdirSync(join(pdfRoot, "wasm")).map(name =>
      [name, readFileSync(join(pdfRoot, "wasm", name))] as [string, Buffer]),
  ]);
  return {
    name: "pdfjs-assets",
    configureServer(server) {
      server.middlewares.use("/pdfjs-assets/", (request, response, next) => {
        const name = request.url?.split("?")[0]?.slice(1) ?? "";
        const content = files.get(name);
        if (!content) return next();
        response.setHeader("Content-Type", name.endsWith(".wasm")
          ? "application/wasm" : name.endsWith(".js") || name.endsWith(".mjs")
          ? "text/javascript" : "text/plain");
        response.end(content);
      });
    },
    generateBundle() {
      for (const [name, source] of files) {
        this.emitFile({ type: "asset", fileName: `pdfjs-assets/${name}`, source });
      }
    },
  };
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "PORTAL_");
  const allowedHosts = (env.PORTAL_PUBLIC_ORIGINS || "")
    .split(",")
    .map((origin) => origin.trim())
    .filter(Boolean)
    .map((origin) => new URL(origin).hostname);
  return {
    plugins: [react(), pdfAssets()],
    server: {
      allowedHosts,
      proxy: {
        "/api": {
          target: "http://127.0.0.1:8000",
          changeOrigin: true,
        },
        "/media": {
          target: "http://127.0.0.1:8000",
          changeOrigin: true,
        },
      },
    },
  };
});
