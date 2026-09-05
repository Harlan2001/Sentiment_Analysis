/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    // 只收 src 下测试, 避免 e2e/tests/*.spec.ts 被 vitest 误收集(那是 Playwright 的)
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    coverage: {
      provider: "v8",
      reporter: ["text", "lcov"],
      reportsDirectory: "coverage",
      // 报告模式（不上阈）：前端从零铺测试，先出数字再渐进收门槛
      thresholds: { statements: 0, branches: 0, functions: 0, lines: 0 },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          "vendor-react": ["react", "react-dom", "react-router-dom"],
          "vendor-echarts": ["echarts", "echarts-for-react"],
          "vendor-ui": ["@headlessui/react", "framer-motion"],
        },
      },
    },
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    proxy: {
      "/sapi/augment": {
        target: "http://10.253.50.113:8080",
        changeOrigin: true,
      },
      "/sapi": {
        target: "http://127.0.0.1:8000",
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
