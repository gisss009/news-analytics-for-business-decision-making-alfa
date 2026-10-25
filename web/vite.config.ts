import fs from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"
import { defineConfig, type Plugin } from "vite"
import react from "@vitejs/plugin-react"

const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..")

function sendData(url: string | undefined, next: () => void, send: (file: string) => void) {
  const pathname = decodeURIComponent((url ?? "").split("?")[0] ?? "")
  if (!pathname.startsWith("/data/")) {
    next()
    return
  }
  const file = path.normalize(path.join(repo, pathname))
  const dataRoot = path.join(repo, "data")
  if (!file.startsWith(dataRoot) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
    next()
    return
  }
  send(file)
}

function serveRepoData(): Plugin {
  return {
    name: "serve-repo-data",
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        sendData(req.url, next, (file) => {
          res.setHeader("Content-Type", file.endsWith(".pdf") ? "application/pdf" : "application/json; charset=utf-8")
          fs.createReadStream(file).pipe(res)
        })
      })
    },
    configurePreviewServer(server) {
      server.middlewares.use((req, res, next) => {
        sendData(req.url, next, (file) => {
          res.setHeader("Content-Type", file.endsWith(".pdf") ? "application/pdf" : "application/json; charset=utf-8")
          fs.createReadStream(file).pipe(res)
        })
      })
    },
  }
}

export default defineConfig({
  plugins: [react(), serveRepoData()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    fs: { allow: [repo] },
  },
})
