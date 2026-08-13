import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

type McpServer = {
  id: string
  name: string
  icon: string
  vendor: string
  description: string
  connected: boolean
  lastSync: string | null
}

const MOCK_SERVERS: McpServer[] = [
  {
    id: 'dingtalk',
    name: '钉钉',
    icon: '📌',
    vendor: '阿里巴巴',
    description: '连接钉钉开放平台，支持工作通知、审批流程和群机器人消息推送。',
    connected: false,
    lastSync: null,
  },
  {
    id: 'feishu',
    name: '飞书',
    icon: '🕊',
    vendor: '字节跳动',
    description: '接入飞书文档、多维表格和消息 API，实现研报协同与日程同步。',
    connected: false,
    lastSync: null,
  },
  {
    id: 'wecom',
    name: '企业微信',
    icon: '💼',
    vendor: '腾讯',
    description: '打通企业微信客户联系、群消息和微盘，在合规范围内管理客户互动。',
    connected: false,
    lastSync: null,
  },
  {
    id: 'wps',
    name: 'WPS 云文档',
    icon: '📄',
    vendor: '金山办公',
    description: '连接 WPS 365 云文档 API，支持在线表格读取、模板填充和批量导出。',
    connected: false,
    lastSync: null,
  },
  {
    id: 'tencent-docs',
    name: '腾讯文档',
    icon: '📊',
    vendor: '腾讯',
    description: '访问腾讯文档开放接口，将研报导出到在线表格并同步数据刷新。',
    connected: false,
    lastSync: null,
  },
  {
    id: 'yuque',
    name: '语雀',
    icon: '📖',
    vendor: '蚂蚁集团',
    description: '对接语雀知识库与文档 API，沉淀研究框架并同步内部知识资产。',
    connected: false,
    lastSync: null,
  },
]

export function McpPage() {
  const navigate = useNavigate()
  const [servers, setServers] = useState<McpServer[]>(MOCK_SERVERS)
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<'全部' | '已连接' | '未连接'>(
    '全部',
  )
  const [connectingId, setConnectingId] = useState<string | null>(null)

  const visible = servers.filter((s) => {
    const matchQuery = (s.name + s.vendor + s.description).includes(
      query.trim(),
    )
    const matchStatus =
      statusFilter === '全部' ||
      (statusFilter === '已连接' && s.connected) ||
      (statusFilter === '未连接' && !s.connected)
    return matchQuery && matchStatus
  })

  function toggleConnection(id: string) {
    setConnectingId(id)
    // 模拟连接/断开
    setTimeout(() => {
      setServers((prev) =>
        prev.map((s) =>
          s.id === id
            ? {
                ...s,
                connected: !s.connected,
                lastSync: !s.connected
                  ? new Date().toLocaleString('zh-CN')
                  : null,
              }
            : s,
        ),
      )
      setConnectingId(null)
    }, 600)
  }

  const connectedCount = servers.filter((s) => s.connected).length

  return (
    <section className="custom-page skills-page">
      <div className="custom-tabs">
        <button className="active">MCP</button>
        <button onClick={() => navigate('/custom/skills')}>Skills</button>
      </div>

      <header className="skills-head">
        <div>
          <h1>MCP 连接</h1>
          <p>
            通过 Model Context Protocol 接入国产办公与协作平台，打通数据与研究流程。
          </p>
        </div>
        <div className="skills-actions">
          <label>
            <span>⌕</span>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="搜索服务名称或厂商…"
            />
          </label>
        </div>
      </header>

      <div className="skills-filter-tabs">
        <div className="mcp-status-summary">
          <span className="mcp-dot active" />
          已连接 {connectedCount}/{servers.length}
        </div>
        {(['全部', '已连接', '未连接'] as const).map((item) => (
          <button
            className={statusFilter === item ? 'active' : ''}
            onClick={() => setStatusFilter(item)}
            key={item}
          >
            {item}
          </button>
        ))}
      </div>

      <div className="skills-grid">
        {visible.map((server) => (
          <article key={server.id}>
            <div>
              <h2>
                <span className="mcp-icon">{server.icon}</span>
                {server.name}
              </h2>
              <button
                aria-label={'连接 ' + server.name}
                className={
                  'mcp-toggle ' + (server.connected ? 'connected' : '')
                }
                disabled={connectingId === server.id}
                onClick={() => toggleConnection(server.id)}
              >
                {connectingId === server.id
                  ? '…'
                  : server.connected
                    ? '断开'
                    : '连接'}
              </button>
            </div>
            <p>{server.description}</p>
            <div className="mcp-meta">
              <span className="mcp-vendor">{server.vendor}</span>
              {server.connected && server.lastSync && (
                <span className="mcp-sync">上次同步：{server.lastSync}</span>
              )}
              {!server.connected && (
                <span className="mcp-sync disabled">未连接</span>
              )}
            </div>
          </article>
        ))}
      </div>

      {!visible.length && (
        <div className="skills-no-result">没有找到匹配的 MCP 服务。</div>
      )}

      <p className="mcp-footnote">
        MCP 连接基于标准协议，凭证在本地加密存储；第三方数据访问遵循各平台授权范围。
      </p>
    </section>
  )
}
