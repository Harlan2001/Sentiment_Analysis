const pageKey = new URLSearchParams(location.search).get('page') || 'home'

const pageMeta = {
  home: { title: '债券市场智能分析', active: '', search: '搜索债券、新闻、因子或策略…' },
  'computer-strategy': { title: 'Computer · 策略开发', active: 'computer', search: '搜索策略任务、会话或回测文件…' },
  'strategy-prompt': { title: 'Computer · 策略提示词确认', active: 'computer', search: '搜索策略会话、版本或回测结果…' },
  'computer-report': { title: 'Computer · 研报生成', active: 'computer', search: '搜索研报任务、主题或结果文件…' },
  'computer-news': { title: 'Computer · 每日新闻总结', active: 'computer', search: '搜索新闻总结、日期或重点事件…' },
  'factor-library': { title: '研究资源与技能', active: 'custom', search: '搜索因子、宏观指标或 Skill…' },
  'factor-detail': { title: '研究资源与技能', active: 'custom', search: '搜索因子、宏观指标或 Skill…' },
  macro: { title: '研究资源与技能', active: 'custom', search: '搜索宏观指标、代码或主题…' },
  project: { title: '国债策略研究', active: 'project', search: '搜索项目会话、共享记忆或成员…' },
}

const meta = pageMeta[pageKey] || pageMeta.home
document.title = `${meta.title} · BondSense`

function sidebar(active) {
  const nav = (key, icon, label) => `<div class="navitem ${active === key ? 'active' : ''}"><span class="navicon">${icon}</span>${label}</div>`
  return `<div class="brand"><div class="brandmark">B</div><div><strong>债券信号</strong><small>BondSense</small></div></div>
  <button class="new-chat">＋ 新建对话</button>
  <div class="nav">${nav('computer','▣','Computer')}${nav('artifact','◇','工件')}${nav('custom','⬡','自定义')}</div>
  <div class="sidehead"><span>项目</span><span>＋⌄</span></div>
  <div class="sideitem ${active === 'project' ? 'current' : ''}">▣ 国债策略研究</div><div class="sideitem">▣ 信用债跟踪</div>
  ${active === 'project' ? '<div class="sideitem">　流动性交易框架</div><div class="sideitem">　曲线策略复盘</div>' : ''}
  <div class="sidehead"><span>${active === 'computer' ? 'Computer 会话' : '对话'}</span><span>⌄</span></div>
  ${active === 'computer' ? '<div class="sideitem live">8月6日债券市场日报</div><div class="sideitem live">每日AI策略推荐</div><div class="sideitem">每日新闻总结</div><div class="sideitem">信用利差周报生成</div><div class="sideitem">7月宏观数据解读</div>' : '<div class="sideitem">流动性对债市影响分析</div><div class="sideitem">因子与宏观指标设计</div><div class="sideitem">本周利率债复盘</div><div class="sideitem">信用利差变化原因</div><div class="sideitem">央行政策解读</div>'}
  <div class="sidebottom"><div class="navitem"><span class="navicon">⚙</span>设置</div><div class="user"><div class="avatar">李</div><div>junlin.li<small>研究员</small></div></div></div>`
}

function topbar() {
  return `<h1>${meta.title}</h1><div class="search">⌕&nbsp;&nbsp;${meta.search}</div><div class="top-actions"><button class="btn">通知</button>${pageKey === 'home' || pageKey.startsWith('factor') || pageKey === 'macro' ? '<button class="btn primary">分享</button>' : ''}</div>`
}

function factorSpark(values, color='var(--green)') {
  return `<span class="spark">${values.map(v=>`<i style="height:${v}px;background:${color}"></i>`).join('')}</span>`
}

function assetMiniChart(path,color='var(--green)') {
  return `<svg viewBox="0 0 330 90" class="asset-chart" aria-hidden="true"><line class="gridline" x1="5" y1="45" x2="325" y2="45" stroke-dasharray="3 3"/><path d="${path}" fill="none" stroke="${color}" stroke-width="2.5"/><circle cx="323" cy="65" r="3" fill="${color}"/></svg>`
}

function homePage() {
  return `<div class="page finance-home">
    <div class="finance-nav"><button class="active">市场</button><button>收益</button><button>预测</button><button>筛选器</button><button>关注列表</button><button>投资组合</button><button>工作流</button><div class="spacer"></div><span class="badge yellow">市场情绪：谨慎偏多</span></div>
    <div class="finance-layout"><div class="asset-grid">
      <div class="asset-card"><div class="asset-top"><div><strong>10年国债收益率</strong><div class="asset-price">1.842%</div></div><span class="delta down">-1.7 bp</span></div>${assetMiniChart('M5 38 C45 32 72 48 105 39 S155 25 188 48 S245 58 275 61 S310 68 323 65','var(--green)')}</div>
      <div class="asset-card"><div class="asset-top"><div><strong>30年国债收益率</strong><div class="asset-price">2.091%</div></div><span class="delta down">-1.2 bp</span></div>${assetMiniChart('M5 30 C40 22 72 28 105 35 S162 43 190 37 S244 52 274 55 S305 62 323 65','var(--green)')}</div>
      <div class="asset-card"><div class="asset-top"><div><strong>国债期货 T 主力</strong><div class="asset-price">108.42</div></div><span class="delta up">+0.18%</span></div>${assetMiniChart('M5 66 C42 71 72 63 105 67 S158 38 185 40 S235 31 270 34 S306 38 323 42','var(--red)')}</div>
      <div class="asset-card"><div class="asset-top"><div><strong>DR007</strong><div class="asset-price">1.563%</div></div><span class="delta up">+2.1 bp</span></div>${assetMiniChart('M5 36 C38 40 60 32 90 38 S135 50 171 47 S225 58 260 62 S300 70 323 65','var(--green)')}</div>
    </div><div class="card watch-card"><div class="section-title"><h2>我的关注</h2><span class="small muted">编辑</span></div>
      <div class="watch-row"><span class="watch-icon">10Y</span><div><div class="name">10年国债</div><div class="sub">CGB10Y</div></div><div class="right"><div>1.842%</div><div class="small delta down">-1.7 bp</div></div></div>
      <div class="watch-row"><span class="watch-icon">30Y</span><div><div class="name">30年国债</div><div class="sub">CGB30Y</div></div><div class="right"><div>2.091%</div><div class="small delta down">-1.2 bp</div></div></div>
      <div class="watch-row"><span class="watch-icon">T</span><div><div class="name">国债期货T</div><div class="sub">T2609</div></div><div class="right"><div>108.42</div><div class="small delta up">+0.18%</div></div></div>
      <div class="watch-row"><span class="watch-icon">TF</span><div><div class="name">5年国债期货</div><div class="sub">TF2609</div></div><div class="right"><div>106.83</div><div class="small delta up">+0.09%</div></div></div>
      <div class="watch-row"><span class="watch-icon">CS</span><div><div class="name">AAA信用利差</div><div class="sub">3Y · 中债</div></div><div class="right"><div>32 bp</div><div class="small delta down">-0.8 bp</div></div></div>
    </div></div>
    <div class="finance-bottom"><div class="market-summary"><div class="section-title"><h2>市场摘要</h2><span class="small muted">10:20更新</span></div><div class="bottom-chat"><textarea placeholder="询问关于今日债券市场的任何问题…"></textarea><div class="compose-actions"><button class="btn">＋</button><span class="badge">⌕ 搜索</span><span class="badge">▣ Computer</span><button class="send">↑</button></div></div></div><div class="card"><div class="section-title"><h2>今日信号</h2><span class="badge green">偏多</span></div><div class="memory-row"><span class="small">资金面宽松预期增强</span></div><div class="memory-row"><span class="small">长端配置需求回升</span></div></div></div>
  </div>`
}

const computerTabs = active => `<div class="tabs"><button class="tab">全部</button><button class="tab ${active==='report'?'active':''}">研报生成</button><button class="tab ${active==='strategy'?'active':''}">策略开发</button><button class="tab ${active==='news'?'active':''}">每日新闻总结</button><div class="spacer"></div>${active==='strategy'?'<button class="btn">自动推荐设置</button><button class="btn primary">＋ 新建策略</button>':active==='report'?'<button class="btn primary">＋ 新建研报</button>':'<button class="btn">计划管理</button><button class="btn primary">＋ 立即生成</button>'}</div>`

function strategyPromptPage() {
  return `<div class="page">
    <div class="detail-head"><button class="btn">← 返回策略开发</button><div><h2>国债期货趋势策略</h2><div class="sub">策略会话 #ST-20260806-02</div></div><div class="spacer"></div><span class="badge yellow">已修改 · 待确认</span><button class="btn">···</button></div>
    <div class="stepper"><div class="step done">需求确认</div><div class="step active">提示词草稿</div><div class="step">用户确认</div><div class="step">代码与回测</div><div class="step">生成完成</div></div>
    <div class="prompt-layout"><div class="requirement-card card"><div><div class="card-title">用户原始需求</div><div class="requirement-box small">帮我生成一个国债期货趋势策略，主要使用资金面和期限利差信号，回测最近三年，最大回撤不要超过10%。</div></div>
      <div><div class="card-title">AI提取的需求</div><div class="requirement-tags" style="margin-top:9px"><span class="badge">标的：国债期货</span><span class="badge">类型：趋势策略</span><span class="badge">信号：资金面</span><span class="badge">信号：期限利差</span><span class="badge">回测：近3年</span><span class="badge red">最大回撤≤10%</span></div></div>
      <div><div class="card-title">可继续补充</div><div class="requirement-box small muted">交易频率、手续费、止损方式、基准合约及换月规则。</div></div>
      <div class="version-note">右侧是AI生成的完整提示词草稿。用户修改后的内容会作为最终策略生成依据，系统草稿仍会保留，便于还原。</div>
      <div class="spacer"></div><button class="btn soft">通过对话补充要求</button>
    </div><div class="prompt-editor card"><div class="section-title"><div><h2>策略提示词草稿</h2><p>可直接编辑 · 已修改2处</p></div><span class="badge">草稿版本 V1</span></div>
      <textarea>你是一名债券量化策略研究员。请生成一个可回测的国债期货趋势策略。

【交易标的】
国债期货T主力连续合约；换月前5个交易日完成移仓。

【核心信号】
1. 使用DR007与7天逆回购利率之差衡量资金面松紧。
2. 使用10年-2年国债收益率期限利差判断曲线方向。
3. 当资金面转松且期限利差连续3日上行时建立多头仓位。
4. 当资金面收紧或期限利差反向突破时平仓。

【回测要求】
回测区间为最近3年；计入手续费和滑点；最大回撤目标不超过10%。
输出累计收益、年化收益、Sharpe、胜率、最大回撤和完整交易记录。

【用户补充修改】
增加20日波动率过滤条件；单次仓位不得超过组合净值的30%。</textarea>
      <div class="prompt-actions"><button class="btn">还原系统草稿</button><button class="btn">重新生成草稿</button><span class="spacer"></span><span class="small muted">确认后将进入代码与回测阶段</span><button class="btn primary">确认并生成策略</button></div>
    </div></div>
  </div>`
}
function taskRows(rows) {
  return rows.map(r=>`<tr><td class="center"><span class="status-icon ${r[0]}">${r[1]}</span></td><td><div class="name">${r[2]}</div><div class="sub">${r[3]}</div>${r[0]==='run'?`<div class="progress" style="width:220px"><i style="width:${r[7]||68}%"></i></div>`:''}</td><td>${r[4]}</td><td>${r[5].startsWith('▤')?`<span class="file-pill">${r[5]}</span>`:`<span class="badge ${r[0]==='fail'?'red':r[0]==='wait'?'yellow':r[0]==='run'?'blue':'green'}">${r[5]}</span>`}</td><td class="right muted">${r[6]}</td></tr>`).join('')
}

function computerPage(kind) {
  const data = {
    strategy:{count:'5段策略会话',attention:['每日AI策略推荐 · 2026-08-06','新闻总结已完成，推荐草稿等待确认','等待确认','查看并确认'],placeholder:'描述策略目标、市场范围和回测要求…',mode:'⌁ 策略开发',filters:'<button class="chip">来源：全部⌄</button><span class="badge blue">自动推荐：新闻总结完成后触发</span>',rows:[
      ['wait','●','每日AI策略推荐 · 2026-08-06','由86条新闻和12个高热度因子自动生成','自动推荐','等待确认','10:20'],
      ['wait','●','国债期货趋势策略','策略提示词草稿已经生成','用户生成','等待确认','10:06'],
      ['run','◐','利率债动量与期限利差策略','正在运行样本外回测','用户生成','运行中 · 68%','09:36',68],
      ['ok','✓','信用债估值偏离策略','策略代码及回测报告已经生成','用户生成','▤ 回测报告.pdf · +2','昨天'],
      ['fail','!','城投债筛选策略回测','行情数据缺失，可从失败步骤重试','用户生成','执行失败 · 可重试','昨天']]},
    report:{count:'4段研报会话',attention:['8月6日债券市场日报','部分行情数据待确认，确认后继续生成','缺少输入','补充数据'],placeholder:'输入研报主题、业务日期和分析范围…',mode:'▤ 研报生成',filters:'<button class="chip">报告类型：全部⌄</button>',rows:[
      ['run','◐','8月6日债券市场日报','正在生成收益率曲线与市场观点','研报生成','运行中 · 68%','11:06',68],
      ['ok','✓','信用债利差跟踪周报','报告及数据附件已经生成','研报生成','▤ 信用利差周报.pdf','08:46'],
      ['ok','✓','7月宏观数据与债市影响','已生成报告、图表及数据引用','研报生成','▤ 宏观解读.pdf · +1','昨天'],
      ['ok','✓','二季度机构配置行为复盘','已归入国债策略研究项目','研报生成','▤ 配置行为复盘.docx','8月4日']]},
    news:{count:'4段总结会话',attention:['每日新闻总结计划','每天08:30自动运行，下次执行：2026-08-07','已启用','查看计划'],placeholder:'补充今日新闻总结的关注主题或排除来源…',mode:'◷ 每日新闻总结',filters:'<button class="chip">执行方式：全部⌄</button><span class="badge green">计划已启用 · 每日08:30</span>',rows:[
      ['ok','✓','8月6日每日债券新闻总结','汇总86条新闻，识别12个重要事件','自动计划','▤ 新闻总结_0806.md','09:02'],
      ['ok','✓','8月5日每日债券新闻总结','汇总74条新闻，识别9个重要事件','自动计划','▤ 新闻总结_0805.md','昨天'],
      ['ok','✓','信用债风险新闻专题总结','汇总31条新闻，识别5个主体风险','手动生成','▤ 信用风险专题.md','昨天'],
      ['fail','!','8月4日每日债券新闻总结','一个新闻源连接失败，可以单独重试','自动计划','执行失败 · 可重试','8月4日']]}
  }[kind]
  return `<div class="page">${computerTabs(kind)}
    <div class="toolbar"><button class="chip">状态：全部⌄</button>${data.filters}<button class="chip">仅未读</button><input class="input" value="📅 2026-08-06"><button class="chip">已归档</button><span class="spacer"></span><span class="small muted">${data.count}</span></div>
    <div class="attention"><div class="attention-head"><span>需要处理 · 1</span><span>⌃</span></div><div class="attention-row"><span class="dot"></span><div><div class="name">${data.attention[0]}</div><div class="sub">${data.attention[1]}</div></div><span class="badge yellow">${data.attention[2]}</span><button class="btn primary">${data.attention[3]}</button><span class="small muted">10:20</span></div></div>
    <div class="listhead"><div><strong>2026 年 8 月 6 日</strong> <span class="small muted">· ${data.count}</span></div><div class="switch"><button class="active">会话与文档</button><button>仅会话</button><button>仅文档</button></div></div>
    <div class="table-wrap task-table"><table class="table"><thead><tr><th style="width:32px"></th><th>任务会话</th><th style="width:140px">来源/类型</th><th style="width:250px">状态或结果</th><th class="right" style="width:90px">更新时间</th></tr></thead><tbody>${taskRows(data.rows)}</tbody></table></div>
    <div class="composer"><input placeholder="${data.placeholder}"><div class="compose-actions"><button class="btn">＋ 添加文件</button><span class="badge">${data.mode}</span><button class="send">↑</button></div></div>
  </div>`
}

const customTabs = active => `<div class="tabs"><button class="tab ${active==='factor'?'active':''}">因子库</button><button class="tab ${active==='macro'?'active':''}">宏观指标</button><button class="tab">Skills</button><div class="spacer"></div><button class="btn">我的关注</button></div>`

function categoryCard(name,count,pos,neu,neg,active=false) {
  const total=pos+neu+neg
  return `<div class="category-card ${active?'active':''}"><strong>${name}</strong><span class="count small">${count}</span><div class="sub">近7日方向分布</div><div class="bar"><span class="pos" style="width:${pos/total*100}%"></span><span class="neu" style="width:${neu/total*100}%"></span><span class="neg" style="width:${neg/total*100}%"></span></div></div>`
}

function factorLibraryPage() {
  const rows=[
    ['银行间流动性','LQ001','货币流动性','利多','高','较高',[5,8,6,12,15,18,16],'18','今天10:20'],
    ['央行公开市场操作','PL027','政策监管','中性','高','高',[4,5,9,7,13,12,10],'12','今天09:40'],
    ['制造业景气度','GR015','经济增长','利空','中','中',[8,7,6,11,8,6,5],'9','昨天'],
    ['地方债发行节奏','SD008','债券供需','利空','中','较高',[3,5,4,8,10,7,6],'7','昨天'],
    ['机构风险偏好','ST041','情绪风险','利多','中','高',[2,4,7,5,8,11,9],'6','2天前'],
    ['资金面宽松预期','LQ033','货币流动性','利多','低','中',[3,4,3,6,5,7,8],'5','3天前']]
  return `<div class="page">${customTabs('factor')}
    <div class="section-title"><div><h2>因子库 <span class="badge">400个因子</span></h2><p>默认展示今日活跃，热度由事件、时效、来源和用户关注共同计算</p></div><div class="switch"><button class="active">今日活跃</button><button>我的关注</button><button>全部因子</button></div></div>
    <div class="category-grid">${categoryCard('政策监管',72,12,18,9)}${categoryCard('经济增长',88,8,15,14)}${categoryCard('货币流动性',96,19,10,6,true)}${categoryCard('债券供需',71,7,12,13)}${categoryCard('情绪风险',73,14,11,8)}</div>
    <div class="filter-row"><input class="input search-input" placeholder="搜索因子名称、代码或主题"><button class="chip">方向：全部⌄</button><button class="chip">热度：全部⌄</button><button class="chip">时间：近7日⌄</button><button class="chip">来源：全部⌄</button><span class="spacer"></span><button class="chip">排序：综合热度⌄</button></div>
    <div class="table-wrap" style="flex:1"><table class="table"><thead><tr><th>因子</th><th>分类</th><th>当前方向</th><th>研究热度</th><th>用户关注</th><th>7日趋势</th><th class="right">事件</th><th>最后更新</th></tr></thead><tbody>${rows.map(r=>`<tr><td><div class="name">${r[0]}</div><div class="sub">${r[1]}</div></td><td>${r[2]}</td><td><span class="badge ${r[3]==='利多'?'green':r[3]==='利空'?'red':''}">${r[3]}</span></td><td><span class="badge ${r[4]==='高'?'yellow':''}">${r[4]}</span></td><td>${r[5]}</td><td>${factorSpark(r[6],r[3]==='利空'?'var(--red)':'var(--green)')}</td><td class="right">${r[7]}</td><td>${r[8]}</td></tr>`).join('')}</tbody></table></div>
    <div class="small muted">综合排序默认权重：研究热度80% · 用户关注20%；原始点击量不直接作为重要度。</div>
  </div>`
}

function factorTimelineSvg() {
  const xs=[95,210,325,440,555,670,785,900]
  const pos=[42,26,55,36,68,44,58,31], neg=[18,31,16,22,36,19,27,15]
  return `<svg class="svg-chart" viewBox="0 0 1000 255" aria-label="因子事件方向时间线"><line class="gridline" x1="65" y1="50" x2="960" y2="50"/><line class="axis" x1="65" y1="135" x2="960" y2="135"/><line class="gridline" x1="65" y1="205" x2="960" y2="205"/><text class="axis-text" x="24" y="54">+4</text><text class="axis-text" x="38" y="139">0</text><text class="axis-text" x="24" y="209">-2</text>${xs.map((x,i)=>`<rect class="pos-fill" x="${x-17}" y="${135-pos[i]}" width="34" height="${pos[i]}" rx="2"/><rect class="neg-fill" x="${x+19}" y="135" width="24" height="${neg[i]}" rx="2"/><circle class="neutral-fill" cx="${x+8}" cy="${125-(i%3)*5}" r="${i%3===0?5:3}"/><text class="axis-text" x="${x-24}" y="235">${['07-07','07-12','07-17','07-22','07-27','08-01','08-05','08-06'][i]}</text>`).join('')}</svg>`
}

function factorDetailPage() {
  return `<div class="page">${customTabs('factor')}
    <div class="factor-head"><div><h2>银行间流动性 <span class="badge green">当前利多</span></h2><div class="sub">LQ001 · 货币流动性 · 影响资金价格与债券配置需求</div></div><div class="spacer"></div><span class="badge">近7日18个事件</span><span class="badge">近30日46个事件</span><span class="badge">10:20更新</span><button class="btn">关注</button></div>
    <div class="timeline-card card"><div class="chart-title"><div><div class="card-title">事件方向时间线</div><div class="sub">柱高代表事件数量，零轴上方为利多、下方为利空</div></div><div><button class="chip">7日</button> <button class="chip active">30日</button> <button class="chip">90日</button> <button class="chip">1年</button></div></div>${factorTimelineSvg()}<div class="legend"><span><i class="swatch pos-fill"></i>利多事件</span><span><i class="swatch neg-fill"></i>利空事件</span><span><i class="swatch neutral-fill"></i>中性事件</span><span>点击日期可筛选下方新闻</span></div></div>
    <div class="section-title"><h2>相关新闻 <span class="small muted">· 与时间线双向联动</span></h2><div><button class="chip active">全部</button> <button class="chip">利多</button> <button class="chip">利空</button></div></div>
    <div class="news-list"><div class="news-row"><span class="badge green">利多</span><div><div class="name">央行连续开展逆回购操作，资金面保持宽松</div><div class="sub">央行官方网站 · 官方来源权重1.00 · 对应时间线08-06</div></div><span class="small muted">今天09:35</span></div><div class="news-row"><span class="badge green">利多</span><div><div class="name">跨月后资金价格回落，机构配置需求回升</div><div class="sub">专业财经媒体 · 来源权重0.75 · 对应时间线08-05</div></div><span class="small muted">昨天16:20</span></div><div class="news-row"><span class="badge red">利空</span><div><div class="name">地方债缴款规模上升，短期资金需求增加</div><div class="sub">财政部 · 官方来源权重1.00 · 对应时间线08-01</div></div><span class="small muted">8月1日</span></div></div>
  </div>`
}

function macroChartSvg() {
  return `<svg class="svg-chart" viewBox="0 0 850 340" aria-label="宏观指标标准化比较"><line class="gridline" x1="60" y1="50" x2="820" y2="50"/><line class="gridline" x1="60" y1="130" x2="820" y2="130"/><line class="axis" x1="60" y1="210" x2="820" y2="210"/><line class="gridline" x1="60" y1="290" x2="820" y2="290"/><text class="axis-text" x="18" y="54">120</text><text class="axis-text" x="18" y="134">110</text><text class="axis-text" x="18" y="214">100</text><text class="axis-text" x="25" y="294">90</text><path class="line-green" d="M65 210 C150 190 180 142 270 135 S400 98 475 126 S595 145 660 98 S765 88 815 102"/><path class="line-red" d="M65 210 C150 165 205 72 290 90 S420 220 500 245 S650 268 720 205 S780 185 815 192"/><path class="line-purple" d="M65 210 C150 225 210 236 285 205 S430 180 510 135 S640 150 710 166 S785 150 815 145"/><circle class="point-green" cx="815" cy="102" r="5"/><circle class="point-red" cx="815" cy="192" r="5"/><circle class="point-purple" cx="815" cy="145" r="5"/><text class="axis-text" x="65" y="325">2022</text><text class="axis-text" x="245" y="325">2023</text><text class="axis-text" x="430" y="325">2024</text><text class="axis-text" x="615" y="325">2025</text><text class="axis-text" x="780" y="325">2026</text></svg>`
}

function macroPage() {
  const cats=[['通胀与价格',28,9,11,8,true],['经济增长',35,12,15,8],['货币与信贷',31,14,10,7],['流动性与利率',24,11,8,5],['就业与收入',21,7,10,4],['房地产',26,5,9,12],['财政与融资',19,8,7,4],['外贸与国际',22,6,9,7]]
  return `<div class="page">${customTabs('macro')}
    <div class="section-title"><div><h2>宏观指标 <span class="badge">200+指标</span></h2><p>按经济含义分类，相关性只作为辅助标签</p></div><div class="switch"><button>单指标</button><button class="active">对比模式</button></div></div>
    <div class="macro-categories">${cats.map(c=>`<div class="macro-card ${c[5]?'active':''}"><strong>${c[0]}</strong><span class="small" style="float:right">${c[1]}</span><div class="meta">本周更新 ${Math.max(2,Math.round(c[1]/6))} 个</div><div class="bar"><span class="pos" style="width:${c[2]/(c[2]+c[3]+c[4])*100}%"></span><span class="neu" style="width:${c[3]/(c[2]+c[3]+c[4])*100}%"></span><span class="neg" style="width:${c[4]/(c[2]+c[3]+c[4])*100}%"></span></div></div>`).join('')}</div>
    <div class="toolbar"><input class="input search-input" placeholder="搜索指标名称、代码或主题"><button class="chip">频率：全部⌄</button><button class="chip">来源：全部⌄</button><span class="spacer"></span><button class="chip active">近5年</button><button class="chip">起始值=100⌄</button></div>
    <div class="macro-main"><div class="indicator-list"><div class="indicator-row active"><input type="checkbox" checked><div><div class="name">居民消费价格指数同比</div><div class="sub">月度 · % · 国家统计局</div></div><code>CPI_YOY</code></div><div class="indicator-row active"><input type="checkbox" checked><div><div class="name">工业生产者出厂价格同比</div><div class="sub">月度 · % · 国家统计局</div></div><code>PPI_YOY</code></div><div class="indicator-row active"><input type="checkbox" checked><div><div class="name">10年期国债收益率</div><div class="sub">日度 · % · 中债</div></div><code>CGB10Y</code></div><div class="indicator-row"><input type="checkbox"><div><div class="name">核心CPI同比</div><div class="sub">月度 · % · 国家统计局</div></div><code>CORE_CPI</code></div><div class="indicator-row"><input type="checkbox"><div><div class="name">GDP平减指数</div><div class="sub">季度 · % · 国家统计局</div></div><code>GDP_DEF</code></div></div>
      <div class="compare-panel card"><div class="chart-title"><div><div class="card-title">指标比较</div><div class="sub">已选3/4 · 不同单位已标准化为起始值100</div></div><div class="selected-pills"><span class="badge green">CPI同比</span><span class="badge red">PPI同比</span><span class="badge" style="color:var(--purple)">10年国债</span></div></div><div style="flex:1;min-height:0">${macroChartSvg()}</div><div class="legend"><span><i class="swatch" style="background:var(--green)"></i>CPI同比</span><span><i class="swatch" style="background:var(--red)"></i>PPI同比</span><span><i class="swatch" style="background:var(--purple)"></i>10年国债收益率</span></div></div>
    </div>
  </div>`
}

function projectPage() {
  return `<div class="page"><div class="project-hero"><div><h2>国债策略研究</h2><p class="muted small">围绕利率债、资金面和国债期货策略开展持续研究</p></div><div class="top-actions"><div class="mini-avatar-group"><span>李</span><span>王</span><span>陈</span><span>+2</span></div><button class="btn">邀请成员</button><button class="btn">项目设置</button></div></div>
    <div class="tabs"><button class="tab active">会话</button><button class="tab">项目记忆</button><button class="tab">成员与权限</button><div class="spacer"></div><button class="btn primary">＋ 新建项目会话</button></div>
    <div class="metric-grid"><div class="metric"><div class="metric-label">我的私有会话</div><div class="metric-value">12</div><div class="metric-note">默认仅自己可见</div></div><div class="metric"><div class="metric-label">项目共享会话</div><div class="metric-value">8</div><div class="metric-note">所有有权限成员可查看</div></div><div class="metric"><div class="metric-label">共享记忆</div><div class="metric-value">24</div><div class="metric-note">3条等待确认</div></div><div class="metric"><div class="metric-label">项目成员</div><div class="metric-value">5</div><div class="metric-note">1所有者 · 3编辑者 · 1查看者</div></div></div>
    <div class="project-main"><div class="card stack"><div class="section-title"><h2>最近会话</h2><div><input class="input" placeholder="搜索项目会话"><button class="chip">可见范围⌄</button></div></div><div class="conversation-list"><div class="conversation-row"><div><div class="name">流动性变化与国债期货多头策略</div><div class="sub">今天10:18 · 已读取项目共享记忆6条</div></div><span class="badge">🔒 仅自己可见</span></div><div class="conversation-row"><div><div class="name">收益率曲线陡峭化交易框架</div><div class="sub">昨天16:42 · 王明更新</div></div><span class="badge green">项目共享</span></div><div class="conversation-row"><div><div class="name">二季度机构配置行为复盘</div><div class="sub">8月4日 · 已保存2条项目记忆</div></div><span class="badge green">项目共享</span></div><div class="conversation-row"><div><div class="name">央行操作对资金价格的影响</div><div class="sub">8月3日 · 个人研究草稿</div></div><span class="badge">🔒 仅自己可见</span></div><div class="conversation-row"><div><div class="name">国债期货基差策略讨论</div><div class="sub">8月1日 · 陈晨更新</div></div><span class="badge green">项目共享</span></div></div><button class="btn soft">查看全部项目会话</button></div>
      <div class="stack"><div class="card"><div class="section-title"><h2>项目共享记忆</h2><span class="badge yellow">3条待确认</span></div><div class="memory-row"><div class="name">项目默认使用中债收益率曲线作为估值基准</div><div class="sub">来源：项目设置 · 李俊林 · 已启用</div></div><div class="memory-row"><div class="name">策略回测默认覆盖最近3年并计入手续费</div><div class="sub">来源：共享会话 · 王明 · 已启用</div></div><div class="memory-row"><div class="name">建议保存：资金面宽松是当前核心假设</div><div class="sub">来源：私有会话 · 写入后项目成员可见</div><div style="margin-top:7px"><button class="btn primary">确认共享</button> <button class="btn">忽略</button></div></div></div>
      <div class="card"><div class="section-title"><h2>成员与权限</h2><span class="small muted">5人</span></div><div class="member-row"><div class="avatar">李</div><div><div class="name">junlin.li</div><div class="sub">所有者</div></div><span class="spacer"></span><span class="badge">所有者</span></div><div class="member-row"><div class="avatar">王</div><div><div class="name">王明</div><div class="sub">研究员</div></div><span class="spacer"></span><span class="badge">编辑者</span></div><div class="member-row"><div class="avatar">陈</div><div><div class="name">陈晨</div><div class="sub">交易员</div></div><span class="spacer"></span><span class="badge">查看者</span></div></div></div>
    </div>
  </div>`
}

document.getElementById('sidebar').innerHTML = sidebar(meta.active)
document.getElementById('topbar').innerHTML = topbar()
const renderers = {
  home: homePage,
  'computer-strategy': () => computerPage('strategy'),
  'strategy-prompt': strategyPromptPage,
  'computer-report': () => computerPage('report'),
  'computer-news': () => computerPage('news'),
  'factor-library': factorLibraryPage,
  'factor-detail': factorDetailPage,
  macro: macroPage,
  project: projectPage,
}
document.getElementById('content').innerHTML = (renderers[pageKey] || homePage)()
