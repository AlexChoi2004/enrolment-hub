import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// The build goes straight into the Flask app's static folder, with fixed file names, so the page can load
// /static/dist/dashboard.js and /static/dist/dashboard.css. The built files are committed, so Node is only
// needed to change the dashboard, never to run the app.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../shared/static/dist",
    emptyOutDir: true,
    cssCodeSplit: false,
    target: "es2022",
    rollupOptions: {
      input: "src/main.tsx",
      output: { entryFileNames: "dashboard.js", chunkFileNames: "dashboard-[name].js", assetFileNames: "dashboard[extname]" },
    },
  },
  test: { environment: "jsdom", globals: true, setupFiles: ["src/test/setup.ts"], include: ["src/**/*.test.{ts,tsx}"] },
});
