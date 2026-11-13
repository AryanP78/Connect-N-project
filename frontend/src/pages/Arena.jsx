import { useState } from 'react'
import LiveMatch from '../components/LiveMatch.jsx'
import { AgentPicker, Card, ConfigPanel, Dot, ErrorBanner, SectionTitle, Spinner, Stat } from '../components/ui.jsx'
import { DEFAULT_CONFIG } from '../hooks/useGame.js'
import { api } from '../services/api.js'
import { AGENT_COLORS, agentLabel, fmtNum } from '../services/agents.js'

function ScoreBoard({ a, b, tally }) {
  const total = tally.a + tally.b + tally.d
  const pct = (v) => (total ? (v / total) * 100 : 0)
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="label">Scoreboard</div>
        <div className="text-xs text-muted">{total} game{total === 1 ? '' : 's'}</div>
      </div>
      <div className="grid grid-cols-3 gap-2 text-center">
        <Stat label={agentLabel(a)} value={tally.a} color={AGENT_COLORS[a.kind]} sub={`${pct(tally.a).toFixed(0)}% wins`} />
        <Stat label="Draws" value={tally.d} sub={`${pct(tally.d).toFixed(0)}%`} />
        <Stat label={agentLabel(b)} value={tally.b} color={AGENT_COLORS[b.kind]} sub={`${pct(tally.b).toFixed(0)}% wins`} />
      </div>
      {total > 0 && (
        <div className="flex h-2.5 rounded-full overflow-hidden mt-3 gap-0.5" role="img" aria-label="Win share">
          <div style={{ width: `${pct(tally.a)}%`, background: AGENT_COLORS[a.kind] }} />
          <div style={{ width: `${pct(tally.d)}%`, background: '#5b5b57' }} />
          <div style={{ width: `${pct(tally.b)}%`, background: AGENT_COLORS[b.kind] }} />
        </div>
      )}
    </Card>
  )
}

export default function Arena() {
  const [config, setConfig] = useState(DEFAULT_CONFIG)
  const [a, setA] = useState({ kind: 'alphabeta', depth: 5 })
  const [b, setB] = useState({ kind: 'minimax', depth: 3 })
  const [tally, setTally] = useState({ a: 0, b: 0, d: 0 })
  const [resetKey, setResetKey] = useState(0)
  const [games, setGames] = useState(10)
  const [running, setRunning] = useState(false)
  const [series, setSeries] = useState(null)
  const [error, setError] = useState(null)

  const onFinish = ({ winnerSlot }) =>
    setTally((t) => (winnerSlot === 0 ? { ...t, a: t.a + 1 } : winnerSlot === 1 ? { ...t, b: t.b + 1 } : { ...t, d: t.d + 1 }))

  const changeAgent = (setter) => (v) => { setter(v); setTally({ a: 0, b: 0, d: 0 }); setSeries(null); setResetKey((k) => k + 1) }

  const runSeries = async () => {
    setRunning(true); setError(null)
    try {
      const res = await api.series({ config, agent1: a, agent2: b, games, seed: Math.floor(Math.random() * 1e6), opening_plies: 2 })
      setSeries(res)
      setTally((t) => ({ a: t.a + res.a_wins, b: t.b + res.b_wins, d: t.d + res.draws }))
    } catch (e) { setError(e.message) } finally { setRunning(false) }
  }

  return (
    <div className="space-y-5">
      <SectionTitle eyebrow="AI Arena" title="Agent vs agent">
        Select two agents and watch them play, or run a whole series at once. Sides alternate between games so neither agent keeps the first-move advantage.
      </SectionTitle>
      <Card className="p-4 grid md:grid-cols-4 gap-5">
        <AgentPicker value={a} onChange={changeAgent(setA)} label="Agent A" />
        <AgentPicker value={b} onChange={changeAgent(setB)} label="Agent B" />
        <div><div className="label mb-2">Board</div>
          <ConfigPanel config={config} onChange={(c) => { setConfig(c); setTally({ a: 0, b: 0, d: 0 }); setSeries(null) }} /></div>
        <div className="space-y-3">
          <div className="label">Run a series</div>
          <div>
            <div className="flex justify-between text-xs text-ink2"><span>Games</span><span className="tabular-nums">{games}</span></div>
            <input type="range" min="2" max="30" step="2" value={games} onChange={(e) => setGames(Number(e.target.value))} />
          </div>
          <button className="btn btn-primary w-full" onClick={runSeries} disabled={running}>
            {running ? <Spinner label="Running..." /> : `Play ${games} games`}
          </button>
          <p className="text-xs text-muted">Paired random openings, sides swapped. Large depths are capped to keep the server responsive.</p>
        </div>
      </Card>
      <ErrorBanner message={error} onClose={() => setError(null)} />
      <ScoreBoard a={a} b={b} tally={tally} />
      {series && (
        <Card className="p-4">
          <div className="label mb-3">Last series ({series.games} games)</div>
          {series.notes?.map((n) => <p key={n} className="text-xs text-p2 mb-2">{n}</p>)}
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-2">
            <Stat label={`${series.agent_a} wins`} value={series.a_wins} color={AGENT_COLORS[a.kind]} />
            <Stat label={`${series.agent_b} wins`} value={series.b_wins} color={AGENT_COLORS[b.kind]} />
            <Stat label="Draws" value={series.draws} />
            <Stat label="Avg game length" value={`${fmtNum(series.avg_game_length)} plies`} />
            <Stat label={`${series.agent_a} avg time`} value={`${fmtNum(series.a_stats.avg_time_ms)} ms`} sub={`${fmtNum(series.a_stats.avg_nodes)} nodes`} />
            <Stat label={`${series.agent_b} avg time`} value={`${fmtNum(series.b_stats.avg_time_ms)} ms`} sub={`${fmtNum(series.b_stats.avg_nodes)} nodes`} />
          </div>
        </Card>
      )}
      <LiveMatch config={config} specs={[a, b]} onFinish={onFinish} resetKey={resetKey} />
    </div>
  )
}
