import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, URL } from "node:url";

const previewRoot = fileURLToPath(new URL(".", import.meta.url));
const projectRoot = path.resolve(previewRoot, "..");
let backendProcess: ReturnType<typeof spawn> | null = null;

export default defineConfig({
  plugins: [
    react(),
    {
      name: "local-batch-api",
      configureServer(server) {
        server.middlewares.use("/media", (req, res, next) => {
          try {
            const requestPath = decodeURIComponent((req.url ?? "").split("?")[0] ?? "");
            const normalizedRequestPath = requestPath.replace(/^\/+/, "");
            const resolvedPath = path.resolve(projectRoot, "data/media", normalizedRequestPath);
            const mediaRoot = `${path.resolve(projectRoot, "data/media")}${path.sep}`;

            if (resolvedPath !== path.resolve(projectRoot, "data/media") && !resolvedPath.startsWith(mediaRoot)) {
              res.statusCode = 403;
              res.end("Path escapes media root.");
              return;
            }

            if (!fs.existsSync(resolvedPath) || !fs.statSync(resolvedPath).isFile()) {
              next();
              return;
            }

            const ext = path.extname(resolvedPath).toLowerCase();
            const contentType =
              ext === ".mp3" ? "audio/mpeg" : ext === ".png" ? "image/png" : "application/octet-stream";

            res.statusCode = 200;
            res.setHeader("Content-Type", contentType);
            res.setHeader("Cache-Control", "no-store");
            res.end(fs.readFileSync(resolvedPath));
          } catch {
            next();
          }
        });

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

        server.middlewares.use("/api/start-backend", (_req, res) => {
          try {
            if (backendProcess !== null && backendProcess.exitCode === null) {
              res.statusCode = 200;
              res.setHeader("Content-Type", "application/json");
              res.end(JSON.stringify({ ok: true }));
              return;
            }

            const venvPython = path.resolve(projectRoot, ".venv/bin/python");
            const pythonBin = fs.existsSync(venvPython) ? venvPython : "python3";
            backendProcess = spawn(pythonBin, ["-m", "korean_anki.cli", "serve"], {
              cwd: projectRoot,
              detached: true,
              env: {
                ...process.env,
                PYTHONPATH: path.resolve(projectRoot, "src")
              },
              stdio: "ignore"
            });
            backendProcess.unref();

            res.statusCode = 200;
            res.setHeader("Content-Type", "application/json");
            res.end(JSON.stringify({ ok: true }));
          } catch (error) {
            res.statusCode = 500;
            res.setHeader("Content-Type", "application/json");
            res.end(
              JSON.stringify({
                error: error instanceof Error ? error.message : "Failed to start backend."
              })
            );
          }
        });

        server.middlewares.use("/api/open-anki", (_req, res) => {
          try {
            const ankiProcess = spawn("open", ["-a", "Anki"], {
              detached: true,
              stdio: "ignore"
            });
            ankiProcess.unref();

            res.statusCode = 200;
            res.setHeader("Content-Type", "application/json");
            res.end(JSON.stringify({ ok: true }));
          } catch (error) {
            res.statusCode = 500;
            res.setHeader("Content-Type", "application/json");
            res.end(
              JSON.stringify({
                error: error instanceof Error ? error.message : "Failed to open Anki."
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
      "/api/status": {
        target: "http://127.0.0.1:8767",
        changeOrigin: true
      },
      "/api/dashboard": {
        target: "http://127.0.0.1:8767",
        changeOrigin: true
      },
      "/api/jobs": {
        target: "http://127.0.0.1:8767",
        changeOrigin: true
      },
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
