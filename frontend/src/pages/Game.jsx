import { useEffect, useRef, useState } from 'react'
import Board from '../components/Board.jsx'
import InsightsPanel from '../components/InsightsPanel.jsx'
import LiveMatch from '../components/LiveMatch.jsx'
import { AgentPicker, Card, ConfigPanel, ErrorBanner, SectionTitle, Spinner, StatusBanner, TokenDot } from '../components/ui.jsx'
import { DEFAULT_CONFIG, useGame } from '../hooks/useGame.js'
import { DIFFICULTIES, agentLabel, defaultSpec } from '../services/agents.js'

function HumanVsAI({ config, setConfig }) {
  const [level, setLevel] = useState('hard')
  const [humanFirst, setHumanFirst] = useState(true)
  const [custom, setCustom] = useState(null) // custom agent overrides the difficulty preset
  const game = useGame(config)
  const { state, busy, error, decisions } = game
  const human = humanFirst ? 1 : 2
  const aiPlayer = 3 - human
  const spec = custom ?? DIFFICULTIES[level]
  const specRef = useRef(spec)
  specRef.current = spec

  // AI plays whenever it is its turn (also its opening move when it goes first).
  useEffect(() => {
    if (state && !state.is_over && !busy && state.current_player === aiPlayer) {
      const t = setTimeout(() => game.aiMove(specRef.current), 250)
      return () => clearTimeout(t)
    }
    /* eslint-disable-next-line */
  }, [state, busy, aiPlayer])

  const restart = (cfg = config, first = humanFirst) => game.reset(cfg, first ? 1 : 2)
  const lastAI = [...decisions].reverse().find((d) => d.player === aiPlayer)?.decision
  const moveCount = state?.moves.length ?? 0

  return (
    <div className="grid lg:grid-cols-[300px_minmax(0,1fr)_380px] gap-5">
      <Card className="p-4 space-y-5 h-fit">
        <div>
          <div className="label mb-2">Difficulty</div>
          <div className="grid grid-cols-2 gap-2">
            {Object.entries(DIFFICULTIES).map(([key, d]) => (
              <button key={key} onClick={() => { setLevel(key); setCustom(null) }}
                className={`btn ${!custom && level === key ? 'btn-primary' : ''}`} title={d.detail}>{d.label}</button>
            ))}
          </div>
          <p className="text-xs text-muted mt-2">Opponent: {agentLabel(spec)}</p>
        </div>
        <details className="text-sm" open={!!custom}>
          <summary className="cursor-pointer text-ink2 hover:text-ink">Choose a specific opponent</summary>
          <div className="mt-3">
            <AgentPicker value={custom ?? defaultSpec(spec.kind === 'random' ? 'minimax' : spec.kind)}
                         onChange={(v) => setCustom(v)} label="Opponent" />
          </div>
        </details>
        <div>
          <div className="label mb-2">Who moves first?</div>
          <div className="flex rounded-lg overflow-hidden border border-line text-sm">
            {[[true, 'You'], [false, 'AI']].map(([v, n]) => (
              <button key={n} className={`flex-1 py-1.5 ${humanFirst === v ? 'bg-accent text-white' : 'bg-raised text-ink2'}`}
                onClick={() => { setHumanFirst(v); restart(config, v) }}>{n}</button>
            ))}
          </div>
        </div>
        <div>
          <div className="label mb-2">Board</div>
          <ConfigPanel config={config} onChange={(c) => { setConfig(c); restart(c) }} />
        </div>
      </Card>

      <div className="space-y-3">
        <StatusBanner state={state} humanPlayer={human} />
        <Card className="p-3 sm:p-5">
          {state && (
            <Board board={state.board} config={state.config} winningCells={state.winning_cells} lastCell={state.last_cell}
              legalMoves={state.legal_moves} currentPlayer={state.current_player}
              disabled={busy || state.is_over || state.current_player !== human} onMove={(m) => game.play(m)} />
          )}
        </Card>
        <div className="flex flex-wrap items-center gap-2">
          <button className="btn btn-primary" onClick={() => restart()}>New game</button>
          <button className="btn" onClick={() => game.undo(state.current_player === human ? 2 : 1)}
                  disabled={busy || moveCount < (humanFirst ? 2 : 3)}>Undo</button>
          {busy && <Spinner label="AI is thinking..." />}
          <div className="ml-auto text-sm text-ink2 flex gap-4">
            <span><TokenDot player={human} /> You</span><span><TokenDot player={aiPlayer} /> AI</span>
          </div>
        </div>
        <ErrorBanner message={error} onClose={() => game.setError(null)} />
        <p className="text-xs text-muted">
          {config.gravity ? 'Click a column to drop your token.' : 'Free placement: click any empty cell.'} Connect {config.n} in a row - horizontally, vertically or diagonally - to win.
        </p>
      </div>
      <InsightsPanel decision={lastAI} config={config} title="AI Insights" />
    </div>
  )
}

function AIvsAI({ config, setConfig }) {
  const [a, setA] = useState({ kind: 'alphabeta', depth: 4 })
  const [b, setB] = useState({ kind: 'mcts', simulations: 500 })
  return (
    <div className="space-y-5">
      <Card className="p-4 grid md:grid-cols-3 gap-5">
        <AgentPicker value={a} onChange={setA} label="Player 1 (red)" />
        <AgentPicker value={b} onChange={setB} label="Player 2 (yellow)" />
        <div><div className="label mb-2">Board</div><ConfigPanel config={config} onChange={setConfig} /></div>
      </Card>
      <LiveMatch config={config} specs={[a, b]} autoAlternate={false} />
    </div>
  )
}

export default function Game() {
  const [mode, setMode] = useState('human')
  const [config, setConfig] = useState(DEFAULT_CONFIG)
  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-3 mb-5">
        <SectionTitle eyebrow="Play" title="Connect-N game">
          Every move - yours and the AI's - is validated by the shared game engine.
        </SectionTitle>
        <div className="flex rounded-lg overflow-hidden border border-line text-sm" role="tablist" aria-label="Game mode">
          {[['human', 'Human vs AI'], ['ai', 'AI vs AI']].map(([k, n]) => (
            <button key={k} role="tab" aria-selected={mode === k} onClick={() => setMode(k)}
              className={`px-4 py-2 ${mode === k ? 'bg-accent text-white' : 'bg-raised text-ink2 hover:text-ink'}`}>{n}</button>
          ))}
        </div>
      </div>
      {mode === 'human' ? <HumanVsAI config={config} setConfig={setConfig} /> : <AIvsAI config={config} setConfig={setConfig} />}
    </div>
  )
}
