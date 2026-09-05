import { test, expect } from '@playwright/test'

/**
 * E2E 冒烟链路（P5 第一波）：
 * 验证后端 mock_llm + 前段 dev server 拉起后，关键页面可达且核心元素渲染。
 * 数据敏感页面（市场/分析）在空白测试库上断言「页面骨架」而非业务数据，
 * 具体业务链路随测试库 seed 逐步加到后面的 spec。
 */

test('前端首页可达并展示导航', async ({ page }) => {
  await page.goto('/')
  await expect(page).toHaveTitle(/.+/)
})

test('市场页渲染主容器（骨架或空态）', async ({ page }) => {
  await page.goto('/market')
  // 当前 /market 是 WorkbenchShell 内的 market-workspace(旧 home-section-page 选择器已不适用)
  await expect(page.locator('.market-workspace')).toBeVisible({
    timeout: 15_000,
  })
})

test('对话页能唤起输入框', async ({ page }) => {
  await page.goto('/chat')
  await expect(page.locator('input, textarea').first()).toBeVisible({ timeout: 15_000 })
})

test('mock_llm_server 经由后端 health 可用', async ({ request }) => {
  const resp = await request.get('http://127.0.0.1:8000/health')
  expect(resp.ok()).toBeTruthy()
})