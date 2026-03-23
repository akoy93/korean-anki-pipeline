import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, URL } from "node:url";

const previewRoot = fileURLToPath(new URL(".", import.meta.url));
const projectRoot = path.resolve(previewRoot, "..");

export default defineConfig({
  plugins: [
    react(),
    {
      name: "local-batch-api",
      configureServer(server) {
        server.middlewares.use("/api/batch", (req, res) => {
          try {
            const requestUrl = new URL(req.url ?? "", "http://127.0.0.1");
            const requestedPath = requestUrl.searchParams.get("path");

            if (requestedPath === null || requestedPath.trim() === "") {
              res.statusCode = 400;
              res.setHeader("Content-Type", "application/json");
              res.end(JSON.stringify({ error: "Missing path query parameter." }));
              return;
            }

            if (path.isAbsolute(requestedPath)) {
              res.statusCode = 400;
              res.setHeader("Content-Type", "application/json");
              res.end(JSON.stringify({ error: "Use a project-relative batch path." }));
              return;
            }

            if (!requestedPath.endsWith(".batch.json")) {
              res.statusCode = 400;
              res.setHeader("Content-Type", "application/json");
              res.end(JSON.stringify({ error: "Only .batch.json files are supported." }));
              return;
            }

            const resolvedPath = path.resolve(projectRoot, requestedPath);
            const normalizedRoot = `${projectRoot}${path.sep}`;
            if (resolvedPath !== projectRoot && !resolvedPath.startsWith(normalizedRoot)) {
              res.statusCode = 403;
              res.setHeader("Content-Type", "application/json");
              res.end(JSON.stringify({ error: "Path escapes project root." }));
              return;
            }

            if (!fs.existsSync(resolvedPath)) {
              res.statusCode = 404;
              res.setHeader("Content-Type", "application/json");
              res.end(JSON.stringify({ error: "Batch file not found." }));
              return;
            }

            const body = fs.readFileSync(resolvedPath, "utf-8");
            res.statusCode = 200;
            res.setHeader("Content-Type", "application/json; charset=utf-8");
            res.setHeader("Cache-Control", "no-store");
            res.end(body);
          } catch (error) {
            res.statusCode = 500;
            res.setHeader("Content-Type", "application/json");
            res.end(
              JSON.stringify({
                error: error instanceof Error ? error.message : "Failed to read batch file."
              })
            );
          }
        });
      }
    }
  ],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url))
    }
  },
  server: {
    port: 5173,
    proxy: {
      "/api/health": {
        target: "http://127.0.0.1:8767",
        changeOrigin: true
      },
      "/api/push": {
        target: "http://127.0.0.1:8767",
        changeOrigin: true
      }
    }
  }
});
