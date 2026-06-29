import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    // Dev: proxy API calls to the FastAPI backend. In prod they share an origin.
    proxy: { "/api": "http://localhost:8000" },
  },
  build: { outDir: "dist" },
  test: { environment: "jsdom" },
});
