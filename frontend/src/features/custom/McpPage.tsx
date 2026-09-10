import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Modal from '@/components/ui/Modal'
import { DemoNotice } from '@/components/ui/DemoNotice'
import './mcp.css'

type Connector = {
  id: 'feishu' | 'dingtalk' | 'wecom' | 'wps'
  name: string
  vendor: string
  description: string
  accounts: string[]
  scopes: Array<{ id: string; label: string; description: string }>
  capabilities: string[]
}

type MockConnection = {
  connected: boolean
  account: string
  scopes: string[]
  connectedAt: string | null
  lastSync: string | null
}

const STORAGE_KEY = 'bondsense-mcp-mock-connections'

const CONNECTORS: Connector[] = [
  {
    id: 'feishu', name: '飞书', vendor: '字节跳动', description: '接入文档、多维表格与群消息，供投研工作流检索使用。',
    accounts: ['陈晨 · 投研团队', 'BondSense 工作空间'],
    scopes: [
      { id: 'docs.read', label: '文档只读', description: '读取已授权的云文档正文' },
      { id: 'bitable.read', label: '多维表格只读', description: '读取表结构与记录' },
      { id: 'chat.read', label: '群消息只读', description: '检索已授权群组的消息' },
    ],
    capabilities: ['文档检索', '多维表格读取', '群消息检索'],
  },
  {
    id: 'dingtalk', name: '钉钉', vendor: '阿里巴巴', description: '接入工作通知、审批摘要与群机器人消息。',
    accounts: ['林然 · 债券研究组', '钉钉研究组织'],
    scopes: [
      { id: 'notice.read', label: '工作通知只读', description: '读取已授权的通知摘要' },
      { id: 'approval.read', label: '审批摘要只读', description: '读取审批流程与状态' },
      { id: 'group.read', label: '群消息只读', description: '检索已授权群组消息' },
    ],
    capabilities: ['通知摘要', '审批查询', '群消息检索'],
  },
  {
    id: 'wecom', name: '企业微信', vendor: '腾讯', description: '接入客户联系、群消息和企业微盘文件。',
    accounts: ['周宁 · 固收策略组', '企业微信研究组织'],
    scopes: [
      { id: 'contacts.read', label: '客户联系只读', description: '读取已授权客户联系信息' },
      { id: 'group.read', label: '群消息只读', description: '检索已授权群组消息' },
      { id: 'drive.read', label: '微盘文件只读', description: '读取已授权企业微盘文件' },
    ],
    capabilities: ['客户联系查询', '群消息检索', '微盘文件读取'],
  },
  {
    id: 'wps', name: 'WPS 云文档', vendor: '金山办公', description: '接入在线文档、表格、模板和导出能力。',
    accounts: ['宋妍 · 固收投研', 'WPS 工作空间'],
    scopes: [
      { id: 'docs.read', label: '云文档只读', description: '读取已授权在线文档' },
      { id: 'sheets.read', label: '在线表格只读', description: '读取已授权表格数据' },
      { id: 'templates.read', label: '模板只读', description: '读取可用的投研模板' },
    ],
    capabilities: ['文档检索', '表格读取', '模板查询'],
  },
]

function emptyConnections(): Record<string, MockConnection> {
  return Object.fromEntries(CONNECTORS.map((connector) => [connector.id, {
    connected: false,
    account: connector.accounts[0],
    scopes: [],
    connectedAt: null,
    lastSync: null,
  }]))
}

function formatSync(value: string | null) {
  return value ? new Date(value).toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false }) : '尚未同步'
}

export function McpPage() {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<'all' | 'connected' | 'available'>('all')
  const [connections, setConnections] = useState<Record<string, MockConnection>>(emptyConnections)
  const [selected, setSelected] = useState<Connector | null>(null)
  const [account, setAccount] = useState('')
  const [selectedScopes, setSelectedScopes] = useState<string[]>([])

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(STORAGE_KEY)
      if (!saved) return
      setConnections((current) => ({ ...current, ...JSON.parse(saved) }))
    } catch {
      window.localStorage.removeItem(STORAGE_KEY)
    }
  }, [])

  function updateConnections(next: Record<string, MockConnection>) {
    setConnections(next)
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
  }

  function openAuthorization(connector: Connector) {
    const saved = connections[connector.id]
    setSelected(connector)
    setAccount(saved?.account || connector.accounts[0])
    setSelectedScopes(saved?.scopes.length ? saved.scopes : connector.scopes.map((scope) => scope.id))
  }

  function toggleScope(scopeId: string) {
    setSelectedScopes((current) => current.includes(scopeId) ? current.filter((id) => id !== scopeId) : [...current, scopeId])
  }

  function confirmAuthorization() {
    if (!selected || selectedScopes.length === 0) return
    const now = new Date().toISOString()
    updateConnections({
      ...connections,
      [selected.id]: { connected: true, account, scopes: selectedScopes, connectedAt: now, lastSync: now },
    })
    setSelected(null)
  }

  function disconnect(connector: Connector) {
    const saved = connections[connector.id]
    updateConnections({
      ...connections,
      [connector.id]: { ...saved, connected: false, scopes: [], connectedAt: null, lastSync: null },
    })
  }

  const visible = useMemo(() => CONNECTORS.filter((connector) => {
    const matchesSearch = (connector.name + connector.vendor + connector.description).toLowerCase().includes(query.toLowerCase())
    const connected = connections[connector.id]?.connected
    return matchesSearch && (filter === 'all' || filter === 'available' || connected)
  }), [connections, filter, query])
  const connectedCount = CONNECTORS.filter((connector) => connections[connector.id]?.connected).length

  return <section className="custom-page mcp-page">
    <div className="custom-tabs"><button className="active">MCP</button><button onClick={() => navigate('/custom/skills')}>Skills</button><button onClick={() => navigate('/custom/memory')}>记忆</button></div>
    <DemoNotice
      title="MCP 连接为演示版本"
      description="当前连接状态、账号和权限范围均为演示数据，不会连接或授权任何真实外部服务；实际功能尚在开发中。"
    />
    <header className="skills-head"><div><h1>MCP 连接</h1><p>将已授权的数据源接入研究工作流。</p></div><div className="skills-actions"><label><span>⌕</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索服务或厂商" /></label></div></header>
    <div className="mcp-toolbar"><div className="skills-filter-tabs">{([['all', '全部'], ['connected', '已连接'], ['available', '可连接']] as const).map(([key, label]) => <button className={filter === key ? 'active' : ''} onClick={() => setFilter(key)} key={key}>{label}</button>)}</div><span className={'mcp-summary ' + (connectedCount ? 'active' : '')}><i />已连接 {connectedCount}/{CONNECTORS.length}</span></div>
    <div className="mcp-grid">{visible.map((connector) => {
      const connection = connections[connector.id]
      return <article className="mcp-card mcp-mock-card" key={connector.id}>
        <div className="mcp-card-top"><span className={'mcp-state ' + (connection?.connected ? 'on' : '')}>{connection?.connected ? '● 已连接' : '○ 可连接'}</span>{connection?.connected ? <button onClick={() => openAuthorization(connector)}>重新授权</button> : <button className="primary" onClick={() => openAuthorization(connector)}>连接</button>}</div>
        <div className="mcp-card-body"><h2>{connector.name}<small>{connector.vendor}</small></h2><p>{connector.description}</p></div>
        <div className="mcp-capability-list">{connector.capabilities.map((capability) => <em key={capability}>{capability}</em>)}</div>
        {connection?.connected && <div className="mcp-connection-row"><span>{connection.account}</span><small>{formatSync(connection.lastSync)}</small><button onClick={() => disconnect(connector)}>断开</button></div>}
      </article>
    })}</div>
    {!visible.length && <div className="skills-no-result">没有找到匹配的 MCP 服务。</div>}
    <p className="mcp-footnote">授权范围和连接状态会在当前设备保留。</p>

    <Modal isOpen={Boolean(selected)} onClose={() => setSelected(null)} title={selected ? `授权 · ${selected.name}` : '授权'} size="sm" panelClassName="mcp-auth-modal" contentClassName="mcp-auth-content">
      {selected && <div className="mcp-auth-form">
        <div className="mcp-auth-brand"><b>{selected.name.slice(0, 1)}</b><span><strong>{selected.name}</strong><small>{selected.vendor} · 模拟授权</small></span></div>
        <p>选择连接账号与访问范围。确认后，连接状态将保存在当前设备。</p>
        <label>连接账号<select value={account} onChange={(event) => setAccount(event.target.value)}>{selected.accounts.map((item) => <option key={item}>{item}</option>)}</select></label>
        <fieldset><legend><span>授权范围</span><small>已选 {selectedScopes.length}/{selected.scopes.length}</small></legend>{selected.scopes.map((scope) => <label className="mcp-scope" key={scope.id}><input type="checkbox" checked={selectedScopes.includes(scope.id)} onChange={() => toggleScope(scope.id)} /><span><strong>{scope.label}</strong><small>{scope.description}</small></span></label>)}</fieldset>
        <div className="mcp-auth-capabilities"><span>连接后可用能力</span><p>{selected.capabilities.join(' · ')}</p></div>
        <div className="mcp-auth-actions"><button type="button" onClick={() => setSelected(null)}>取消</button><button type="button" className="primary" onClick={confirmAuthorization} disabled={selectedScopes.length === 0}>确认授权</button></div>
      </div>}
    </Modal>
  </section>
}
