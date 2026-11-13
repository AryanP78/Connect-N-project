import { useEffect, useState } from 'react'
import Board from '../components/Board.jsx'
import InsightsPanel from '../components/InsightsPanel.jsx'
import { AgentPicker, Card, ConfigPanel, ErrorBanner, SectionTitle, Spinner, StatusBanner } from '../components/ui.jsx'
import { DEFAULT_CONFIG } from '../hooks/useGame.js'
import { api } from '../services/api.js'
import { fmtNum, moveName } from '../services/agents.js'

const COMPONENT_NAMES = {
  windows: 'Own open windows',
  opponent_windows: 'Opponent open windows',
  immediate_threats: 'Own immediate threats',
  opponent_immediate_threats: 'Opponent immediate threats',
  center: 'Centre preference',
}

function Breakdown({ title, data, n }) {
  const entries = Object.entries(data.components)
  const max = Math.max(1, ...entries.map(([, v]) => Math.abs(v)))
  return (
    <div className="rounded-xl bg-raised border border-line p-3">
      <div className="flex justify-between items-baseline">
        <div className="text-sm font-semibold">{title}</div>
        <div className="tabular-nums text-sm">{data.total > 0 ? '+' : ''}{fmtNum(data.total)}</div>
      </div>
      <div className="mt-2 space-y-1.5">
        {entries.map(([k, v]) => (
          <div key={k} className="text-xs">
            <div className="flex justify-between text-ink2"><span>{COMPONENT_NAMES[k]}</span><span className="tabular-nums">{v > 0 ? '+' : ''}{fmtNum(v)}</span></div>
            <div className="h-1.5 rounded bg-line relative overflow-hidden">
              <div className="absolute top-0 bottom-0" style={{
                left: v >= 0 ? '50%' : `${50 - (Math.abs(v) / max) * 50}%`, width: `${(Math.abs(v) / max) * 50}%`,
                background: v >= 0 ? '#3987e5' : '#d95926' }} />
              <div className="absolute left-1/2 top-0 bottom-0 w-px bg-muted/60" />
            </div>
          </div>
        ))}
      </div>
      <div className="text-[11px] text-muted mt-2">
        Open windows by tokens (of {n}) - own: {Object.entries(data.own_windows_by_tokens).map(([k, v]) => `${k}:${v}`).join('  ')}
        {' | '}opponent: {Object.entries(data.opponent_windows_by_tokens).map(([k, v]) => `${k}:${v}`).join('  ')}
      </div>
    </div>
  )
}

export default function Insights() {
  const [config, setConfig] = useState(DEFAULT_CONFIG)
  const [moves, setMoves] = useState([])
  const [agent, setAgent] = useState({ kind: 'alphabeta', depth: 5 })
  const [analysis, setAnalysis] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    const t = setTimeout(async () => {
      try {
        const res = await api.analyze(config, moves, 1, agent)
        if (!cancelled) { setAnalysis(res); setError(null) }
      } catch (e) {
        if (!cancelled) setError(e.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }, 200)
    return () => { cancelled = true; clearTimeout(t) }
  }, [config, moves, agent])

  const state = analysis?.state
  const decision = analysis?.decision
  const n = config.n

  return (
    <div className="space-y-5">
      <SectionTitle eyebrow="AI Insights" title="Position analyzer">
        Set up any position by playing moves for both sides. The selected agent analyses it live: its move, thinking time, search depth,
        nodes explored, a plain-language explanation and the heuristic evaluation that drives the decision.
      </SectionTitle>
      <div className="grid lg:grid-cols-[300px_minmax(0,1fr)_400px] gap-5">
        <Card className="p-4 space-y-5 h-fit">
          <AgentPicker value={agent} onChange={setAgent} label="Analysing agent" />
          <div>
            <div className="label mb-2">Board</div>
            <ConfigPanel config={config} onChange={(c) => { setConfig(c); setMoves([]) }} />
          </div>
        </Card>
        <div className="space-y-3">
          {state && <StatusBanner state={state} />}
          <Card className="p-3 sm:p-5">
            {state ? (
              <Board board={state.board} config={state.config} winningCells={state.winning_cells} lastCell={state.last_cell}
                legalMoves={state.legal_moves} currentPlayer={state.current_player} onMove={(m) => setMoves((x) => [...x, m])}
                highlightMoves={decision ? [decision.move] : []} />
            ) : <div className="h-64 grid place-items-center"><Spinner label="Analysing..." /></div>}
          </Card>
          <div className="flex flex-wrap gap-2 items-center">
            <button className="btn" onClick={() => setMoves((m) => m.slice(0, -1))} disabled={!moves.length}>Undo</button>
            <button className="btn" onClick={() => setMoves([])} disabled={!moves.length}>Clear</button>
            <button className="btn btn-primary" disabled={!decision || state?.is_over} onClick={() => setMoves((m) => [...m, decision.move])}>
              Play suggested move{decision ? ` (${moveName(decision.move, config)})` : ''}
            </button>
            {loading && <Spinner label="thinking..." />}
          </div>
          <ErrorBanner message={error} onClose={() => setError(null)} />
          <p className="text-xs text-muted">Click the board to place the next token for whoever is to move. The highlighted number is the agent's recommended move.</p>
        </div>
        <div className="space-y-4">
          <InsightsPanel decision={decision} config={config} title="Agent decision" />
          {analysis && (
            <Card className="p-4 space-y-3">
              <div className="label">Heuristic evaluation (shared by Greedy, Minimax and Alpha-Beta)</div>
              <Breakdown title="From Player 1's view (red)" data={analysis.evaluation.player_1} n={n} />
              <Breakdown title="From Player 2's view (yellow)" data={analysis.evaluation.player_2} n={n} />
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
