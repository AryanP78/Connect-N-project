import { useEffect, useMemo, useState } from 'react'
import {
  Bar, BarChart, CartesianGrid, Cell, LabelList, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { AgentPicker, Card, Dot, ErrorBanner, SectionTitle, Spinner, Stat } from '../components/ui.jsx'
import { DEFAULT_CONFIG } from '../hooks/useGame.js'
import { api } from '../services/api.js'
import { AGENT_COLORS, colorOfLabel, fmtNum } from '../services/agents.js'

const AX = { tick: { fill: '#898781', fontSize: 11 }, axisLine: { stroke: '#2c2c2a' }, tickLine: false }
const TT = {
  contentStyle: { background: '#232321', border: '1px solid #2c2c2a', borderRadius: 8, color: '#f0efec', fontSize: 12 },
  cursor: { fill: '#ffffff0d' }, itemStyle: { color: '#f0efec' }, labelStyle: { color: '#c3c2b7' },
}
// log-scale helpers: ticks at powers of ten only (Recharts' automatic log ticks are unreadable)
const logTicks = (lo, hi) => {
  const out = []
  for (let e = Math.round(Math.log10(lo)); e <= Math.round(Math.log10(hi)); e++) out.push(10 ** e)
  return out
}
const tickLog = (v) => (v >= 1000 ? `${v / 1000}k` : `${+v.toPrecision(3)}`)
const logDomain = (values, pad = 1.5) => [
  10 ** (Math.floor(Math.log10(Math.min(...values))) - 1),
  10 ** Math.ceil(Math.log10(Math.max(...values) * pad)),
]
const OUTCOME = { Wins: '#0ca30c', Draws: '#5b5b57', Losses: '#d03b3b' }

function ChartCard({ title, subtitle, height = 260, children }) {
  return (
    <Card className="p-4">
      <div className="text-sm font-semibold">{title}</div>
      {subtitle && <div className="text-xs text-muted mt-0.5">{subtitle}</div>}
      <div className="mt-3" style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">{children}</ResponsiveContainer>
      </div>
    </Card>
  )
}

/** Horizontal bars, one colour per agent (colour follows the entity), direct value labels. */
function AgentBars({ rows, dataKey, title, subtitle, unit = '', log = false, height = 240 }) {
  const [lo, hi] = logDomain(rows.map((r) => r[dataKey]))
  return (
    <ChartCard title={title} subtitle={subtitle} height={height}>
      <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 56, left: 4, bottom: 0 }}>
        <CartesianGrid horizontal={false} stroke="#2c2c2a" />
        <XAxis type="number" scale={log ? 'log' : 'auto'} domain={log ? [lo, hi] : [0, 'auto']}
               ticks={log ? logTicks(lo, hi) : undefined} allowDataOverflow {...AX}
               tickFormatter={log ? tickLog : (v) => fmtNum(v, 0)} />
        <YAxis type="category" dataKey="agent" width={118} {...AX} />
        <Tooltip {...TT} formatter={(v) => `${fmtNum(v)} ${unit}`.trim()} />
        <Bar dataKey={dataKey} radius={[0, 4, 4, 0]} maxBarSize={26}>
          {rows.map((r) => <Cell key={r.agent} fill={colorOfLabel(r.agent)} />)}
          <LabelList dataKey={dataKey} position="right" fill="#f0efec" fontSize={11}
                     formatter={(v) => `${fmtNum(v)}${unit ? ' ' + unit : ''}`} />
        </Bar>
      </BarChart>
    </ChartCard>
  )
}

function OutcomeBars({ standings, title, subtitle }) {
  const rows = [...standings].sort((a, b) => b.win_rate - a.win_rate).map((s) => ({
    agent: s.agent, Wins: s.win_rate * 100, Draws: s.draw_rate * 100, Losses: s.loss_rate * 100,
  }))
  const pct = (v) => (v >= 7 ? `${v.toFixed(0)}%` : '')
  return (
    <ChartCard title={title} subtitle={subtitle} height={250}>
      <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 12, left: 4, bottom: 0 }} barCategoryGap="22%">
        <CartesianGrid horizontal={false} stroke="#2c2c2a" />
        <XAxis type="number" domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} {...AX} tickFormatter={(v) => `${v}%`} />
        <YAxis type="category" dataKey="agent" width={118} {...AX} />
        <Tooltip {...TT} formatter={(v) => `${v.toFixed(1)}%`} />
        <Legend wrapperStyle={{ fontSize: 12, color: '#c3c2b7' }}
                payload={Object.keys(OUTCOME).map((k) => ({ value: k, type: 'circle', color: OUTCOME[k], id: k }))} />
        {Object.keys(OUTCOME).map((k) => (
          <Bar key={k} dataKey={k} stackId="o" fill={OUTCOME[k]} stroke="#1a1a19" strokeWidth={2} maxBarSize={30}>
            <LabelList dataKey={k} position="center" fill={k === 'Draws' ? '#f0efec' : '#fff'} fontSize={11} fontWeight={700} formatter={pct} />
          </Bar>
        ))}
      </BarChart>
    </ChartCard>
  )
}

function StandingsTable({ standings }) {
  const rows = [...standings].sort((a, b) => b.win_rate - a.win_rate)
  const th = 'text-left font-medium text-muted px-3 py-2 text-xs uppercase tracking-wide whitespace-nowrap'
  return (
    <Card className="overflow-x-auto">
      <table className="w-full text-sm tabular-nums">
        <thead><tr className="border-b border-line">
          {['Agent', 'Games', 'Win', 'Loss', 'Draw', 'Win rate', 'Avg time (ms)', 'Avg nodes', 'Depth (set / reached)'].map((h) => <th key={h} className={th}>{h}</th>)}
        </tr></thead>
        <tbody>
          {rows.map((s) => (
            <tr key={s.agent} className="border-b border-line/60 last:border-0">
              <td className="px-3 py-2 font-medium whitespace-nowrap"><Dot color={colorOfLabel(s.agent)} className="mr-2" />{s.agent}</td>
              <td className="px-3 py-2">{s.games}</td><td className="px-3 py-2">{s.wins}</td>
              <td className="px-3 py-2">{s.losses}</td><td className="px-3 py-2">{s.draws}</td>
              <td className="px-3 py-2">{(s.win_rate * 100).toFixed(1)}%</td>
              <td className="px-3 py-2">{fmtNum(s.avg_time_ms)}</td><td className="px-3 py-2">{fmtNum(s.avg_nodes)}</td>
              <td className="px-3 py-2">{s.configured_depth ? `${s.configured_depth} / ${s.avg_depth_reached.toFixed(1)}` : '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  )
}

function Exp1({ d }) {
  const st = d.standings.map((s) => ({ ...s }))
  return (
    <section className="space-y-4">
      <SectionTitle eyebrow="Experiment 1" title="Win-rate comparison: Random vs Greedy vs Minimax vs Alpha-Beta">
        Round robin on the default 6 x 7 board. Each agent played {st[0].games} games ({d.games_per_pair} per opponent); every pair of games
        shares a random {d.opening_plies}-ply opening with the sides swapped.
      </SectionTitle>
      <div className="grid xl:grid-cols-3 gap-4">
        <OutcomeBars standings={st} title="Outcomes" subtitle="% of each agent's games" />
        <AgentBars rows={st} dataKey="avg_time_ms" title="Average decision time" subtitle="log scale" unit="ms" log />
        <AgentBars rows={st} dataKey="avg_nodes" title="Average nodes explored per decision" subtitle="log scale" log />
      </div>
      <StandingsTable standings={st} />
    </section>
  )
}

const LINE_TT = { ...TT, cursor: { stroke: '#898781', strokeDasharray: '3 3' } }

function Exp2({ d }) {
  const profile = d.cost_profile.map((p) => ({ depth: p.spec.depth, nodes: p.avg_nodes, time: p.avg_time_ms }))
  const wins = [...d.tournament.standings].sort((a, b) => a.configured_depth - b.configured_depth)
    .map((s) => ({ depth: s.configured_depth, win: s.win_rate * 100 }))
  const c = AGENT_COLORS.minimax
  const line = (key, title, unit) => {
    const [lo, hi] = logDomain(profile.map((r) => r[key]), 1)
    return (
    <ChartCard title={title} subtitle="log scale" height={230}>
      <LineChart data={profile} margin={{ top: 14, right: 16, left: 0, bottom: 4 }}>
        <CartesianGrid vertical={false} stroke="#2c2c2a" />
        <XAxis dataKey="depth" padding={{ left: 22, right: 22 }} {...AX} label={{ value: 'search depth (plies)', fill: '#898781', fontSize: 11, dy: 14 }} height={40} />
        <YAxis scale="log" domain={[lo, hi]} ticks={logTicks(lo, hi)} allowDataOverflow {...AX} width={48} tickFormatter={tickLog} />
        <Tooltip {...LINE_TT} formatter={(v) => `${fmtNum(v)} ${unit}`.trim()} labelFormatter={(l) => `Depth ${l}`} />
        <Line type="monotone" dataKey={key} stroke={c} strokeWidth={2.5} dot={{ r: 5, fill: c, stroke: '#1a1a19', strokeWidth: 2 }} activeDot={{ r: 7 }}>
          <LabelList dataKey={key} position="top" fill="#f0efec" fontSize={11} formatter={(v) => fmtNum(v)} />
        </Line>
      </LineChart>
    </ChartCard>
    )
  }
  return (
    <section className="space-y-4">
      <SectionTitle eyebrow="Experiment 2" title="Search-depth comparison: Minimax at depths 1-5">
        Strength comes from a round robin of depths 1-4 ({d.tournament.games_per_pair} games per pairing); cost is the mean over {d.sample_positions} sampled positions.
        Each extra ply multiplies the work by roughly the branching factor.
      </SectionTitle>
      <div className="grid lg:grid-cols-3 gap-4">
        <ChartCard title="Win rate vs the other depths" subtitle="% of games" height={230}>
          <BarChart data={wins} margin={{ top: 14, right: 12, left: 0, bottom: 4 }}>
            <CartesianGrid vertical={false} stroke="#2c2c2a" />
            <XAxis dataKey="depth" {...AX} label={{ value: 'search depth (plies)', fill: '#898781', fontSize: 11, dy: 14 }} height={40} />
            <YAxis domain={[0, 100]} {...AX} width={40} tickFormatter={(v) => `${v}%`} />
            <Tooltip {...TT} formatter={(v) => `${v.toFixed(1)}%`} labelFormatter={(l) => `Depth ${l}`} />
            <Bar dataKey="win" fill={c} radius={[4, 4, 0, 0]} maxBarSize={44}>
              <LabelList dataKey="win" position="top" fill="#f0efec" fontSize={11} formatter={(v) => `${v.toFixed(0)}%`} />
            </Bar>
          </BarChart>
        </ChartCard>
        {line('nodes', 'Average nodes per decision', '')}
        {line('time', 'Average decision time (ms)', 'ms')}
      </div>
    </section>
  )
}

function Exp3({ d }) {
  const rows = d.comparison.map((r) => ({
    depth: r.depth, Minimax: r.minimax_avg_nodes, 'Alpha-Beta': r.alphabeta_avg_nodes,
    reduction: r.node_reduction_pct, speedup: r.speedup,
  }))
  const allSame = d.comparison.every((r) => r.same_move_rate === 1 && r.same_score_rate === 1)
  const minSame = Math.min(...d.comparison.map((r) => r.same_move_rate)) * 100
  const deeper = d.alphabeta_deeper_profile
  return (
    <section className="space-y-4">
      <SectionTitle eyebrow="Experiment 3" title="Minimax vs Alpha-Beta at equal depth">
        Same heuristic, same move ordering. Alpha-Beta chose {allSame ? 'the identical move and value' : `the same move in at least ${minSame.toFixed(0)}% of positions`} as
        Minimax in every sampled position at every depth, while exploring far fewer nodes.
      </SectionTitle>
      <div className="grid lg:grid-cols-[1.5fr_1fr] gap-4">
        <ChartCard title="Average nodes explored per decision" subtitle="log scale - lower is better" height={260}>
          <BarChart data={rows} margin={{ top: 18, right: 12, left: 0, bottom: 4 }}>
            <CartesianGrid vertical={false} stroke="#2c2c2a" />
            <XAxis dataKey="depth" {...AX} label={{ value: 'search depth (plies)', fill: '#898781', fontSize: 11, dy: 14 }} height={40} />
            <YAxis scale="log" domain={[1, 100000]} ticks={[1, 10, 100, 1000, 10000, 100000]} allowDataOverflow {...AX} width={48} tickFormatter={tickLog} />
            <Tooltip {...TT} formatter={(v) => fmtNum(v)} labelFormatter={(l) => `Depth ${l}`} />
            <Legend wrapperStyle={{ fontSize: 12, color: '#c3c2b7' }} iconType="circle" />
            <Bar dataKey="Minimax" fill={AGENT_COLORS.minimax} radius={[4, 4, 0, 0]} maxBarSize={36}>
              <LabelList dataKey="Minimax" position="top" fill="#f0efec" fontSize={10} formatter={(v) => fmtNum(v)} />
            </Bar>
            <Bar dataKey="Alpha-Beta" fill={AGENT_COLORS.alphabeta} radius={[4, 4, 0, 0]} maxBarSize={36}>
              <LabelList dataKey="Alpha-Beta" position="top" fill="#f0efec" fontSize={10} formatter={(v) => fmtNum(v)} />
            </Bar>
          </BarChart>
        </ChartCard>
        <ChartCard title="Wall-clock speed-up of Alpha-Beta" subtitle="Minimax time / Alpha-Beta time" height={260}>
          <BarChart data={rows} margin={{ top: 18, right: 12, left: 0, bottom: 4 }}>
            <CartesianGrid vertical={false} stroke="#2c2c2a" />
            <XAxis dataKey="depth" {...AX} label={{ value: 'search depth (plies)', fill: '#898781', fontSize: 11, dy: 14 }} height={40} />
            <YAxis {...AX} width={40} tickFormatter={(v) => `${v}x`} />
            <Tooltip {...TT} formatter={(v, n, p) => [`${v.toFixed(1)}x (${p.payload.reduction.toFixed(0)}% fewer nodes)`, 'speed-up']} labelFormatter={(l) => `Depth ${l}`} />
            <Bar dataKey="speedup" fill={AGENT_COLORS.alphabeta} radius={[4, 4, 0, 0]} maxBarSize={44}>
              <LabelList dataKey="speedup" position="top" fill="#f0efec" fontSize={11} formatter={(v) => `${v.toFixed(1)}x`} />
            </Bar>
          </BarChart>
        </ChartCard>
      </div>
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {d.matches.map((m) => (
          <Stat key={m.agent_a} label={`Match at depth ${m.spec_a.depth}`} value={`${m.a_wins} - ${m.b_wins}`}
                sub={`Minimax - Alpha-Beta, ${m.draws} draws (${m.games} games)`} />
        ))}
        {deeper?.length > 0 && (
          <Stat label="Alpha-Beta goes deeper" value={deeper.map((p) => `d${p.spec.depth}`).join(', ')}
                sub={deeper.map((p) => `d${p.spec.depth}: ${fmtNum(p.avg_nodes)} nodes, ${fmtNum(p.avg_time_ms)} ms`).join(' | ')} />
        )}
      </div>
      <p className="text-xs text-muted">Equal-depth matches are decided by opening luck: both agents make identical decisions, so the paired (side-swapped) games split evenly - evidence of equivalence, not of a bug.</p>
    </section>
  )
}

function Exp4({ d }) {
  const keys = Object.keys(d.opponents)
  const colors = { greedy: AGENT_COLORS.greedy, alphabeta_d3: AGENT_COLORS.alphabeta }
  const rows = d.budgets.map((b, i) => {
    const row = { sims: b }
    keys.forEach((k) => { row[d.opponents[k].label] = d.opponents[k].results[i].mcts_win_rate * 100 })
    row.time = d.opponents[keys[0]].results[i].avg_time_ms
    return row
  })
  const games = d.opponents[keys[0]].results[0].games
  return (
    <section className="space-y-4">
      <SectionTitle eyebrow="Experiment 4" title="Monte Carlo at different simulation budgets">
        MCTS (UCT, random rollouts) against two fixed opponents, {games} games each. More simulations buy strength at a roughly linear time cost.
      </SectionTitle>
      <div className="grid lg:grid-cols-[1.5fr_1fr] gap-4">
        <ChartCard title="MCTS win rate vs simulation budget" subtitle="% of games won (draws excluded)" height={270}>
          <LineChart data={rows} margin={{ top: 14, right: 16, left: 0, bottom: 4 }}>
            <CartesianGrid vertical={false} stroke="#2c2c2a" />
            <XAxis dataKey="sims" padding={{ left: 20, right: 20 }} {...AX} label={{ value: 'simulations per move', fill: '#898781', fontSize: 11, dy: 14 }} height={40} />
            <YAxis domain={[0, 100]} {...AX} width={40} tickFormatter={(v) => `${v}%`} />
            <Tooltip {...LINE_TT} formatter={(v) => `${v.toFixed(0)}%`} labelFormatter={(l) => `${l} simulations`} />
            <Legend wrapperStyle={{ fontSize: 12, color: '#c3c2b7' }} iconType="circle" formatter={(v) => `vs ${v}`} />
            {keys.map((k, idx) => (
              <Line key={k} type="monotone" dataKey={d.opponents[k].label} stroke={colors[k]} strokeWidth={2.5}
                    dot={{ r: 5, fill: colors[k], stroke: '#1a1a19', strokeWidth: 2 }} activeDot={{ r: 7 }}>
                <LabelList dataKey={d.opponents[k].label} content={({ x, y, value, index }) => {
                  // the higher of the two points labels above, the lower below, so labels never collide
                  const others = keys.filter((o) => o !== k).map((o) => rows[index][d.opponents[o].label])
                  const above = others.every((v) => value > v || (value === v && idx === 0))
                  return <text x={x} y={above ? y - 11 : y + 20} textAnchor="middle" fill="#f0efec" fontSize={10}>{value.toFixed(0)}</text>
                }} />
              </Line>
            ))}
          </LineChart>
        </ChartCard>
        <ChartCard title="Average decision time" subtitle="ms per move" height={270}>
          <BarChart data={rows} margin={{ top: 18, right: 12, left: 0, bottom: 4 }}>
            <CartesianGrid vertical={false} stroke="#2c2c2a" />
            <XAxis dataKey="sims" {...AX} label={{ value: 'simulations per move', fill: '#898781', fontSize: 11, dy: 14 }} height={40} />
            <YAxis {...AX} width={44} />
            <Tooltip {...TT} formatter={(v) => `${fmtNum(v)} ms`} labelFormatter={(l) => `${l} simulations`} />
            <Bar dataKey="time" fill={AGENT_COLORS.mcts} radius={[4, 4, 0, 0]} maxBarSize={40}>
              <LabelList dataKey="time" position="top" fill="#f0efec" fontSize={10} formatter={(v) => fmtNum(v)} />
            </Bar>
          </BarChart>
        </ChartCard>
      </div>
    </section>
  )
}

function Memory({ rows }) {
  const data = rows.map((r) => ({ agent: r.agent, kb: r.avg_peak_kb }))
  return (
    <section className="space-y-4">
      <SectionTitle eyebrow="Memory" title="Peak memory per decision">
        Python-heap peak (tracemalloc) during a single move. Search agents use make/undo on one board, so their footprint is tiny; MCTS stores a search tree.
      </SectionTitle>
      <AgentBars rows={data} dataKey="kb" title="Average peak allocation" unit="KB" height={250} />
    </section>
  )
}

function LiveBenchmark() {
  const [a, setA] = useState({ kind: 'alphabeta', depth: 4 })
  const [b, setB] = useState({ kind: 'greedy' })
  const [games, setGames] = useState(10)
  const [running, setRunning] = useState(false)
  const [res, setRes] = useState(null)
  const [error, setError] = useState(null)
  const run = async () => {
    setRunning(true); setError(null)
    try { setRes(await api.series({ config: DEFAULT_CONFIG, agent1: a, agent2: b, games, seed: 7, opening_plies: 4 })) }
    catch (e) { setError(e.message) } finally { setRunning(false) }
  }
  return (
    <section className="space-y-4">
      <SectionTitle eyebrow="Live" title="Run your own benchmark">
        Pick two agents and play a fresh series on the server (default 6 x 7 board). Limited to 30 games to keep it responsive.
      </SectionTitle>
      <Card className="p-4 grid md:grid-cols-4 gap-5">
        <AgentPicker value={a} onChange={setA} label="Agent A" />
        <AgentPicker value={b} onChange={setB} label="Agent B" />
        <div className="space-y-3">
          <div className="label">Games</div>
          <input type="range" min="2" max="30" step="2" value={games} onChange={(e) => setGames(Number(e.target.value))} />
          <div className="text-sm tabular-nums">{games} games</div>
        </div>
        <div className="flex items-end"><button className="btn btn-primary w-full" onClick={run} disabled={running}>
          {running ? <Spinner label="Running..." /> : 'Run benchmark'}</button></div>
      </Card>
      <ErrorBanner message={error} onClose={() => setError(null)} />
      {res && (
        <div className="grid sm:grid-cols-3 lg:grid-cols-6 gap-2">
          <Stat label={`${res.agent_a} wins`} value={res.a_wins} sub={`${(res.a_win_rate * 100).toFixed(0)}%`} color={colorOfLabel(res.agent_a)} />
          <Stat label="Draws" value={res.draws} sub={`${(res.draw_rate * 100).toFixed(0)}%`} />
          <Stat label={`${res.agent_b} wins`} value={res.b_wins} sub={`${(res.b_win_rate * 100).toFixed(0)}%`} color={colorOfLabel(res.agent_b)} />
          <Stat label="Avg game length" value={`${fmtNum(res.avg_game_length)} plies`} />
          <Stat label={`${res.agent_a}`} value={`${fmtNum(res.a_stats.avg_time_ms)} ms`} sub={`${fmtNum(res.a_stats.avg_nodes)} nodes / move`} />
          <Stat label={`${res.agent_b}`} value={`${fmtNum(res.b_stats.avg_time_ms)} ms`} sub={`${fmtNum(res.b_stats.avg_nodes)} nodes / move`} />
        </div>
      )}
    </section>
  )
}

export default function Analytics() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  useEffect(() => { api.benchmarks().then(setData).catch((e) => setError(e.message)) }, [])
  const meta = data?.meta
  return (
    <div className="space-y-12">
      <div>
      <SectionTitle eyebrow="Analytics" title="Algorithm comparison dashboard">
        Every chart below is computed from tournaments and searches actually executed by the benchmarking framework (backend/benchmarks) - nothing is hand-entered.
      </SectionTitle>
      {error && (
        <ErrorBanner message={`${error}. Generate the data with: python -m backend.benchmarks.run_experiments`} />
      )}
      {!data && !error && <Spinner label="Loading benchmark results..." />}
      {meta && (
        <div className="flex flex-wrap gap-2 text-xs text-ink2">
          {[
            `${meta.config.rows}x${meta.config.cols}, connect ${meta.config.n}${meta.config.gravity ? ', gravity' : ''}`,
            `generated ${new Date(meta.generated_at).toLocaleString()}`,
            `Python ${meta.python} + NumPy ${meta.numpy}`, `${meta.cpu_count} CPU cores`, `${meta.wall_clock_seconds}s wall-clock`,
            `${Object.values(meta.games_per_pairing).join('/')} games per pairing (exp 1-4)`,
          ].map((t) => <span key={t} className="px-2.5 py-1 rounded-full bg-raised border border-line">{t}</span>)}
        </div>
      )}
      </div>
      {data && (
        <>
          <Exp1 d={data.exp1_round_robin} />
          <Exp2 d={data.exp2_minimax_depths} />
          <Exp3 d={data.exp3_equal_depth} />
          <Exp4 d={data.exp4_mcts} />
          <Memory rows={data.memory} />
          <ul className="text-xs text-muted list-disc pl-5 space-y-1">{meta.notes.map((n) => <li key={n}>{n}</li>)}</ul>
        </>
      )}
      <LiveBenchmark />
    </div>
  )
}
