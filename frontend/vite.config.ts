import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";

// Islands build: each entry becomes one self-contained ES module under
// static/js/islands/, loaded lazily by static/js/islands-loader.js.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: resolve(__dirname, "../static/js/islands"),
    emptyOutDir: true,
    rollupOptions: {
      // keep each entry's default export — the loader calls mod.default(el, props)
      preserveEntrySignatures: "exports-only",
      input: {
        "documents-table": resolve(__dirname, "src/islands/documents-table.tsx"),
      },
      output: {
        format: "es",
        entryFileNames: "[name].js",
        chunkFileNames: "[name]-chunk.js",
        assetFileNames: "[name][extname]",
      },
    },
  },
});
