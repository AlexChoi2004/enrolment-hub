import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Each island is built on its own into the Flask app's static folder, with fixed file names:
//   vite build               -> /static/dist/dashboard.js and dashboard.css   (cleans the folder first)
//   vite build --mode board  -> /static/dist/board.js and board.css
// The built files are committed, so Node is only needed to change an island, never to run the app.
export default defineConfig(({ mode }) => {
  const island = mode === "board" ? "board" : "dashboard";
  return {
    plugins: [react()],
    build: {
      outDir: "../shared/static/dist",
      emptyOutDir: island === "dashboard",
      cssCodeSplit: false,
      target: "es2022",
      rollupOptions: {
        input: island === "board" ? "src/board/main.tsx" : "src/main.tsx",
        output: { entryFileNames: `${island}.js`, chunkFileNames: `${island}-[name].js`, assetFileNames: `${island}[extname]` },
      },
    },
    test: { environment: "jsdom", globals: true, setupFiles: ["src/test/setup.ts"], include: ["src/**/*.test.{ts,tsx}"] },
  };
});
