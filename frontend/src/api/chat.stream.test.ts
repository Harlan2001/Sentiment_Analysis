import { describe, expect, it, vi } from 'vitest'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/server'
import { sendMessage, sendVisitorMessage } from '@/api/chat'

/** 构造成流式 SSE 响应：把给定文本块按顺序 enqueue 到 ReadableStream。 */
function sseResponse(chunks: string[]) {
  return new HttpResponse(
    new ReadableStream({
      start(controller) {
        for (const chunk of chunks) {
          controller.enqueue(new TextEncoder().encode(chunk))
        }
        controller.close()
      },
    }),
    { status: 200, headers: { 'Content-Type': 'text/event-stream' } },
  )
}

describe('chat SSE 流式解析', () => {
  it('sendVisitorMessage 逐 delta 回调', async () => {
    server.use(
      http.post('/sapi/workbench/conversations/visitor-chat', () =>
        sseResponse([
          'event: assistant.delta\ndata: {"delta":"你好"}\n\n',
          'event: assistant.delta\ndata: {"delta":"世界"}\n\n',
        ]),
      ),
    )
    const onDelta = vi.fn()
    await sendVisitorMessage('hi', [], onDelta)
    expect(onDelta.mock.calls.map((c) => c[0])).toEqual(['你好', '世界'])
  })

  it('sendVisitorMessage 跨 chunk 的帧被正确拼接', async () => {
    server.use(
      http.post('/sapi/workbench/conversations/visitor-chat', () =>
        sseResponse(['event: assistant.delta\ndata: {"delta":"跨', 'chunk"}\n\n']),
      ),
    )
    const onDelta = vi.fn()
    await sendVisitorMessage('hi', [], onDelta)
    expect(onDelta).toHaveBeenCalledWith('跨chunk')
  })

  it('sendVisitorMessage 收到 failed 事件抛错', async () => {
    server.use(
      http.post('/sapi/workbench/conversations/visitor-chat', () =>
        sseResponse([
          'event: assistant.failed\ndata: {"error":{"code":"x","message":"流失败"}}\n\n',
        ]),
      ),
    )
    const onDelta = vi.fn()
    await expect(sendVisitorMessage('hi', [], onDelta)).rejects.toThrow('流失败')
  })

  it('sendMessage 按序分发多个事件', async () => {
    server.use(
      http.post('/sapi/workbench/conversations/c1/messages', () =>
        sseResponse([
          'event: message.accepted\ndata: {"message":{"id":"m1"}}\n\n',
          'event: assistant.delta\ndata: {"message_id":"m1","delta":"好"}\n\n',
          'event: stream.done\ndata: {"conversation_id":"c1"}\n\n',
        ]),
      ),
    )
    const onEvent = vi.fn()
    await sendMessage('c1', '内容', 'cm1', onEvent)
    expect(onEvent.mock.calls.map((c) => c[0].event)).toEqual([
      'message.accepted',
      'assistant.delta',
      'stream.done',
    ])
  })
})