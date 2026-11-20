// Configuration Vite : le commit court est injecté au build (règle 2 : version, lot, commit sur les pages d'administration).
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { execSync } from "node:child_process";

function commitCourt() {
  try { return execSync("git rev-parse --short HEAD").toString().trim(); } catch { return ""; }
}

export default defineConfig({
  plugins: [react()],
  define: { __COMMIT__: JSON.stringify(process.env.RENDER_GIT_COMMIT ? process.env.RENDER_GIT_COMMIT.slice(0, 7) : commitCourt()) },
  // En développement, l'API (port 8000) est relayée sous /api.
  server: { proxy: { "/api": "http://localhost:8000" } },
});
