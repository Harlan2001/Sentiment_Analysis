import { test, expect } from '@playwright/test'

/**
 * E2E 对话链路：访客在对话页发送问题，经后端 /visitor-chat 调 mock_llm_server 流式回复并落屏。
 * 依赖：webServer 已拉起 mock_llm(8080) + backend(8000) + 前端(5173)，AUTH_ENABLED=false 免登录。
 */

test('访客对话可发送问题并收到流式回复', async ({ page }) => {
  await page.goto('/chat')

  const input = page.locator('input, textarea').first()
  await expect(input).toBeVisible({ timeout: 15_000 })
  await input.fill('如何看待当前债市？')

  await page.getByRole('button', { name: '发送消息' }).first().click()

  // mock_llm 流式回复三段内容, 期待聚合后的文案出现
  await expect(page.getByText('当前债市情绪以')).toBeVisible({ timeout: 20_000 })
})

test('对话输入框为空时不发送', async ({ page }) => {
  await page.goto('/chat')
  const input = page.locator('input, textarea').first()
  await expect(input).toBeVisible({ timeout: 15_000 })

  // 空内容时发送按钮是禁用态, 无法点击触发发送
  const sendBtn = page.getByRole('button', { name: '发送消息' }).first()
  await expect(sendBtn).toBeDisabled()
  // Enter 走表单 requestSubmit()(不受按钮 disabled 拦截), 复测 submit 里对空内容的守卫:
  // 用户消息数必须保持不变(新会话为 0; 侧边栏历史会话标题不在此列)
  const userMessages = page.locator('.chat-message.user')
  const userCount = await userMessages.count()
  await input.press('Enter')
  await expect(userMessages).toHaveCount(userCount)
})