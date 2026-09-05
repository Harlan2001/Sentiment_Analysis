import { describe, expect, it } from 'vitest'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/server'
import {
  createConversation,
  getConversation,
  getConversations,
  getSidebar,
} from '@/api/chat'

const WB = '/sapi/workbench'

describe('chat api — request 封装的简单函数', () => {
  it('getConversations 附加 limit 并解包 items', async () => {
    let url = ''
    server.use(
      http.get(`${WB}/conversations`, (info) => {
        url = info.request.url
        return HttpResponse.json({ data: { items: [{ id: 'c1', title: '会话' }] } })
      }),
    )
    const res = await getConversations(20)
    expect(url).toContain('limit=20')
    expect(res.items[0].id).toBe('c1')
  })

  it('getConversation 解包 conversation + messages', async () => {
    server.use(
      http.get(`${WB}/conversations/abc`, () =>
        HttpResponse.json({
          data: {
            conversation: { id: 'abc' },
            messages: [{ id: 'm1', role: 'user', content: 'hi' }],
          },
        }),
      ),
    )
    const res = await getConversation('abc')
    expect(res.conversation.id).toBe('abc')
    expect(res.messages).toHaveLength(1)
  })

  it('createConversation POST 携 body 并返回会话', async () => {
    let body: unknown = null
    server.use(
      http.post(`${WB}/conversations`, async (info) => {
        body = await info.request.json()
        return HttpResponse.json({ data: { id: 'new1', title: '', status: 'active' } })
      }),
    )
    const conv = await createConversation({ source: 'sidebar' })
    expect(body).toEqual({ source: 'sidebar' })
    expect(conv.id).toBe('new1')
  })

  it('getSidebar 解包 projects 与 recent_conversations', async () => {
    server.use(
      http.get(`${WB}/sidebar`, () =>
        HttpResponse.json({
          data: { projects: [{ id: 'p1', name: '项目' }], recent_conversations: [] },
        }),
      ),
    )
    const res = await getSidebar()
    expect(res.projects[0].name).toBe('项目')
    expect(res.recent_conversations).toEqual([])
  })
})