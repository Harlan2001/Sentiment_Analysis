import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          "vendor-react": ["react", "react-dom", "react-router-dom"],
          "vendor-echarts": ["echarts", "echarts-for-react"],
          "vendor-ui": ["@headlessui/react", "framer-motion", "reactflow"],
          "vendor-utils": ["date-fns", "clsx", "zustand", "react-hook-form"],
        },
      },
    },
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/sapi/augment": {
        target: "http://10.253.50.113:8080",
        changeOrigin: true,
      },
      "/sapi": {
        target: "http://127.0.0.1:8001",
        changeOrigin: true,
      },
    },
  },
  resolve: {
    alias: {
      "@": "/src",
    },
  },
});
