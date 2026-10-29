import { Fragment, useState } from 'react'
import type { FactorSignal, FactorSignalPanel } from '@/api/strategy'

type Props = {
  panel: FactorSignalPanel | null | undefined
}

function percent(value: number | null): string {
  return value === null || value === undefined ? '—' : value.toFixed(3)
}

function directionTone(direction: FactorSignal['direction']): string {
  if (direction === 'positive') return 'long'
  if (direction === 'negative') return 'short'
  return 'neutral'
}

function FactorDetail({ factor }: { factor: FactorSignal }) {
  return (
    <div className="sf-signal-detail">
      <dl>
        <div><dt>信号分</dt><dd>{factor.signal_score.toFixed(3)}</dd></div>
        <div><dt>置信度</dt><dd>{factor.confidence.toFixed(3)}</dd></div>
        <div><dt>命中率</dt><dd>{percent(factor.hit_rate)}</dd></div>
        <div><dt>多数类基准</dt><dd>{percent(factor.majority_base)}</dd></div>
        <div><dt>样本量</dt><dd>{factor.sample_size}</dd></div>
        <div><dt>持有期</dt><dd>T+{factor.holding_days}</dd></div>
        <div><dt>窗口内事件</dt><dd>{factor.event_count} 条</dd></div>
        <div>
          <dt>多/空/中性</dt>
          <dd>{factor.positive_count} / {factor.negative_count} / {factor.event_count - factor.positive_count - factor.negative_count}</dd>
        </div>
      </dl>
      <p className="sf-signal-caveat">
        命中率为<strong>全模型混合口径</strong>（历史事件由 doubao / deepseek / glm 三个模型分批产出），
        与当前在线模型 glm 的单一模型口径不同，仅作方向可靠性参考。
      </p>
    </div>
  )
}

/**
 * 因子信号面板：把"这次策略凭什么这么定"摆到台面上。
 *
 * 每行可展开查看命中率、基准、样本量等依据，鼠标悬停也能看到核心数字——
 * 需求文档 §6.2 要求页面上每个结论都能溯源，这里的命中率与样本量就是
 * "因子方向"这个结论的依据。
 */
export function FactorSignalTable({ panel }: Props) {
  const [expanded, setExpanded] = useState<string | null>(null)
  const items = panel?.items ?? []

  if (!panel) {
    return <p className="strategy-empty-state">本轮未生成因子信号面板。</p>
  }

  if (items.length === 0) {
    return (
      <div className="sf-signal-empty">
        <strong>证据不足</strong>
        <p>
          当前窗口内没有通过历史检验的因子信号（要求样本量 ≥ {panel.min_samples} 且命中率跑赢多数类基准）。
          本轮策略不含情绪门控，仅依据技术信号生成。
        </p>
      </div>
    )
  }

  return (
    <div className="sf-signal-panel">
      <header className="sf-signal-head">
        <div>
          <h4>因子信号面板</h4>
          <p>
            窗口 {panel.window_days} 天 · 抽取模型 {panel.model_name} · 持有期 T+{panel.holding_days}
            · 样本门槛 ≥{panel.min_samples}
          </p>
        </div>
        <span className="sf-signal-caliber">历史表现：全模型口径</span>
      </header>

      <table className="sf-signal-table">
        {/* 固定列宽：因子名占大头，数值列给足空间放强度条与命中率 */}
        <colgroup>
          <col className="sf-col-name" />
          <col className="sf-col-dir" />
          <col className="sf-col-score" />
          <col className="sf-col-hit" />
          <col className="sf-col-n" />
          <col className="sf-col-time" />
        </colgroup>
        <thead>
          <tr>
            <th>因子</th>
            <th>方向</th>
            <th>信号分</th>
            <th>命中率(基准)</th>
            <th>样本量</th>
            <th>最近触发</th>
          </tr>
        </thead>
        <tbody>
          {items.map((factor) => {
            const isOpen = expanded === factor.code
            const tone = directionTone(factor.direction)
            // 信号强度条：长度取 |信号分|，方向决定颜色
            const strength = Math.min(100, Math.abs(factor.signal_score) * 100)
            // 命中率超出基准的幅度，用小数条体现"高出多少"
            const edge =
              factor.hit_rate !== null && factor.majority_base !== null
                ? factor.hit_rate - factor.majority_base
                : null
            const edgePct = edge === null ? 0 : Math.min(100, Math.max(0, edge * 1000))
            return (
              <Fragment key={factor.code}>
                <tr
                  className={`sf-signal-row sf-signal-row--${tone}`}
                  onClick={() => setExpanded(isOpen ? null : factor.code)}
                  title="点击展开依据"
                >
                  <td>
                    <span className="sf-signal-name">{factor.name}</span>
                    <small>{factor.code}</small>
                  </td>
                  <td>
                    <span className={`sf-signal-badge sf-signal-badge--${tone}`}>
                      {factor.direction_label}
                    </span>
                  </td>
                  <td className="sf-signal-num">
                    <div className="sf-signal-meter">
                      <span className="sf-signal-meter-track">
                        <i className={`sf-signal-meter-fill sf-signal-meter-fill--${tone}`} style={{ width: `${strength}%` }} />
                      </span>
                      <b>{factor.signal_score.toFixed(2)}</b>
                    </div>
                  </td>
                  <td className="sf-signal-num">
                    <div className="sf-signal-hit">
                      <b>{percent(factor.hit_rate)}</b>
                      <span className="sf-signal-hit-base">基准 {percent(factor.majority_base)}</span>
                      {edge !== null && (
                        <span className="sf-signal-hit-edge">
                          <i style={{ width: `${edgePct}%` }} />
                          <em>+{(edge * 100).toFixed(1)}pt</em>
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="sf-signal-num">{factor.sample_size}</td>
                  <td className="sf-signal-time">
                    {(factor.latest_event_time || '').slice(0, 10) || '—'}
                  </td>
                </tr>
                {isOpen && (
                  <tr className="sf-signal-detail-row">
                    <td colSpan={6}><FactorDetail factor={factor} /></td>
                  </tr>
                )}
              </Fragment>
            )
          })}
        </tbody>
      </table>

      <p className="sf-signal-footnote">
        方向为债市口径：多 = 利多债券（收益率下行）。信号条长度代表方向强度，
        命中率须高于基准才有参考价值；差值越大越可靠。
      </p>
    </div>
  )
}