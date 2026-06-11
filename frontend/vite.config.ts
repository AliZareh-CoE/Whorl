import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";

// Islands build: each entry becomes one self-contained ES module under
// static/js/islands/, loaded lazily by static/js/islands-loader.js.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: resolve(__dirname, "../static/js"),
    emptyOutDir: false, // static/js also holds the hand-written islands-loader.js
    rollupOptions: {
      // keep each entry's default export — the loader calls mod.default(el, props)
      preserveEntrySignatures: "exports-only",
      input: {
        "documents-table": resolve(__dirname, "src/islands/documents-table.tsx"),
        assistant: resolve(__dirname, "src/islands/assistant.tsx"),
        spa: resolve(__dirname, "src/app/main.tsx"),
      },
      output: {
        format: "es",
        entryFileNames: (chunk) => (chunk.name === "spa" ? "spa.js" : "islands/[name].js"),
        chunkFileNames: "islands/[name]-chunk.js",
        assetFileNames: "islands/[name][extname]",
      },
    },
  },
});
