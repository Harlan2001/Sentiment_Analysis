import { defineConfig, devices } from '@playwright/test'

/**
 * E2E 配置。运行拓扑（三条服务由 webServer 自动拉起，CI/本地共用）：
 *   1. mock_llm_server (8080) —— 假 LLM，后端 LLM_BASE_URL 指向它
 *   2. backend uvicorn   (8000) —— 连 MySQL（本地=WSL 测试库，CI=services mysql）
 *   3. 前端 dev server   (5173) —— Vite dev
 *
 * 后端依赖的环境（MYSQL_*、LLM_*、AUTH_ENABLED=false）由外层（CI job env / 本地 shell env）提供，
 * webServer command 继承 process env，不在此重复设置。
 */
export default defineConfig({
  testDir: './tests',
  timeout: 30_000,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? 'list' : [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: 'http://127.0.0.1:5173',
    headless: true,
    viewport: { width: 1280, height: 800 },
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      // bash -c 先 source ~/.bashrc: 本机 WSL 的 uv/nvm 等常在用户 shell 配置里,
      // Playwright 用 /bin/sh 起命令默认 PATH 找不到; CI runner 无此问题(source 失败被忽略)。
      // 注意: Playwright webServer 默认 cwd = config 文件所在目录(frontend/e2e),
      // 而 uvicorn 需在仓库根(main.py / scripts/ 在根), 故先 cd ../.. 回到仓库根。
      command:
        'bash -c "source ~/.bashrc 2>/dev/null; cd ../.. && uv run uvicorn scripts.mock_llm_server:app --host 127.0.0.1 --port 8080"',
      url: 'http://127.0.0.1:8080/health',
      reuseExistingServer: true,
      timeout: 30_000,
    },
    {
      command:
        'bash -c "source ~/.bashrc 2>/dev/null; cd ../.. && uv run uvicorn main:app --host 127.0.0.1 --port 8000"',
      url: 'http://127.0.0.1:8000/health',
      reuseExistingServer: true,
      timeout: 60_000,
    },
    {
      command:
        'bash -c "source ~/.bashrc 2>/dev/null; npm run dev -- --host 127.0.0.1 --port 5173 --strictPort"',
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: true,
      timeout: 60_000,
    },
  ],
})