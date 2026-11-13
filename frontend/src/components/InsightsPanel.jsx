import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { AGENT_COLORS, fmtNum, isForced, kindOfLabel, moveLabel, moveName } from '../services/agents.js'
import { Card, Dot, Stat } from './ui.jsx'

const CLAMP = 400

function scoreText(score, decision) {
  if (score == null) return '-'
  if (decision.extra?.scores_are_win_probabilities) return `${(score * 100).toFixed(0)}% win`
  if (isForced(score)) return score > 0 ? 'forced win' : 'forced loss'
  return (score > 0 ? '+' : '') + fmtNum(score)
}

/** AI Insights: what the agent chose, how hard it worked, and why. */
export default function InsightsPanel({ decision, config, title = 'AI Insights', playerLabel, accent }) {
  if (!decision) {
    return (
      <Card className="p-4">
        <div className="label mb-2">{title}</div>
        <p className="text-sm text-muted">The AI's reasoning appears here after its first move: selected move, thinking
          time, search depth, nodes explored and a plain-language explanation.</p>
      </Card>
    )
  }
  const kind = kindOfLabel(decision.agent)
  const color = accent ?? AGENT_COLORS[kind]
  const isProb = decision.extra?.scores_are_win_probabilities
  const bounds = decision.extra?.scores_are_exact === false
  const entries = Object.entries(decision.move_scores ?? {}).map(([m, s]) => {
    const score = s ?? 0
    const shown = isProb ? score * 100 : Math.max(-CLAMP, Math.min(CLAMP, score))
    return { move: m, label: moveLabel(m, config), shown, raw: score, chosen: Number(m) === decision.move }
  }).sort((a, b) => Number(a.move) - Number(b.move))
  const showChart = entries.length > 1 && entries.length <= 16
  const isSearch = decision.depth > 0
  return (
    <Card className="p-4 space-y-3">
      <div className="flex items-center justify-between gap-2">
        <div className="label flex items-center gap-2"><Dot color={color} />{title}{playerLabel ? ` - ${playerLabel}` : ''}</div>
        <div className="text-sm font-semibold" style={{ color }}>{decision.agent}</div>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <Stat label="Selected move" value={moveName(decision.move, config)} color={color} />
        <Stat label="Thinking time" value={`${fmtNum(decision.time_ms)} ms`} />
        <Stat label="Search depth" value={isSearch ? `${decision.depth} plies` : kind === 'mcts' ? 'rollouts' : 'none'}
              sub={isSearch ? `deepest line ${decision.max_depth}` : kind === 'mcts' ? `tree depth ${decision.max_depth}` : '1-move lookahead'} />
        <Stat label={kind === 'mcts' ? 'Simulations' : 'Nodes explored'} value={decision.nodes.toLocaleString()}
              sub={decision.extra?.cutoffs != null ? `${decision.extra.cutoffs.toLocaleString()} cut-offs` : undefined} />
      </div>
      <Stat label={isProb ? 'Estimated win probability' : 'Evaluation (from the mover)'} value={scoreText(decision.score, decision)} />
      <p className="text-sm text-ink2 leading-relaxed">{decision.explanation}</p>
      {decision.notes?.map((n) => <p key={n} className="text-xs text-p2">{n}</p>)}
      {showChart && (
        <div>
          <div className="label mb-1">
            {isProb ? 'Win probability per move (%)' : `Value per move${bounds ? ' (non-chosen moves are upper bounds)' : ''}`}
          </div>
          <div className="h-36" aria-label="Move values chart">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={entries} margin={{ top: 6, right: 4, left: -18, bottom: 0 }}>
                <XAxis dataKey="label" tick={{ fill: '#898781', fontSize: 11 }} axisLine={{ stroke: '#2c2c2a' }} tickLine={false} />
                <YAxis tick={{ fill: '#898781', fontSize: 10 }} axisLine={false} tickLine={false} width={44}
                       tickFormatter={(v) => (isProb ? v : fmtNum(v, 0))} />
                <Tooltip cursor={{ fill: '#ffffff0d' }}
                  contentStyle={{ background: '#232321', border: '1px solid #2c2c2a', borderRadius: 8, color: '#f0efec', fontSize: 12 }}
                  formatter={(_v, _n, p) => [isProb ? `${(p.payload.raw * 100).toFixed(1)}%` : (isForced(p.payload.raw) ? (p.payload.raw > 0 ? 'forced win' : 'forced loss') : `${bounds && !p.payload.chosen ? '<= ' : ''}${fmtNum(p.payload.raw)}`), 'value']}
                  labelFormatter={(l) => `Move ${l}`} />
                <Bar dataKey="shown" radius={[4, 4, 0, 0]} maxBarSize={28}>
                  {entries.map((e) => <Cell key={e.move} fill={e.chosen ? color : '#4a4a46'} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </Card>
  )
}
