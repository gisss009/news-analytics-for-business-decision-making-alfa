import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Запросы /api/* проксируются на backend (uvicorn :8000). Из Docker-контейнера хост доступен как host.docker.internal.
const target = process.env.VITE_PROXY_TARGET ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // в контейнере на Windows события файловой системы не доходят — опрос файлов
    watch: process.env.VITE_POLL === "1" ? { usePolling: true, interval: 300 } : undefined,
    proxy: { "/api": { target, changeOrigin: true, rewrite: (p) => p.replace(/^\/api/, "") } },
  },
  preview: { proxy: { "/api": { target, changeOrigin: true, rewrite: (p) => p.replace(/^\/api/, "") } } },
});
