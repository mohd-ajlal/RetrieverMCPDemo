import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  root: path.resolve(__dirname),
  base: "/static/frontend/",
  build: {
    outDir: path.resolve(__dirname, "../static/frontend"),
    emptyOutDir: true,
    manifest: "manifest.json",
    rollupOptions: {
      input: path.resolve(__dirname, "src/main.jsx"),
    },
  },
  server: {
    origin: "http://localhost:5173",
  },
});
