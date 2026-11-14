import { useEffect, useRef, useState } from 'react'
import { useGame } from '../hooks/useGame.js'
import { agentLabel } from '../services/agents.js'
import Board from './Board.jsx'
import { Card, ErrorBanner, Spinner, StatusBanner, TokenDot } from './ui.jsx'

/**
 * Watch two AI agents play each other, one engine-validated move at a time.
 * `specs` = [agent for player 1, agent for player 2]. Reports each finished game via onFinish.
 */
export default function LiveMatch({ config, specs, onFinish, autoAlternate = true, resetKey = 0 }) {
  const game = useGame(config)
  const { state, busy, error } = game
  const [playing, setPlaying] = useState(false)
  const [delay, setDelay] = useState(450)
  const [swapped, setSwapped] = useState(false)
  const reported = useRef(false)

  // Agents for the two *tokens*: when swapped, specs[1] plays token 1.
  const tokenSpec = (token) => (swapped ? specs[token === 1 ? 1 : 0] : specs[token === 1 ? 0 : 1])
  const slotOfToken = (token) => (swapped ? (token === 1 ? 1 : 0) : (token === 1 ? 0 : 1))

  useEffect(() => { setPlaying(false); setSwapped(false); reported.current = false; game.reset(config, 1)
    /* eslint-disable-next-line */ }, [resetKey, config.rows, config.cols, config.n, config.gravity])

  useEffect(() => {
    if (!state || state.is_over || !playing || busy) return
    const t = setTimeout(() => game.aiMove(tokenSpec(state.current_player)), delay)
    return () => clearTimeout(t)
    /* eslint-disable-next-line */
  }, [state, playing, busy, delay])

  useEffect(() => {
    if (state?.is_over && !reported.current) {
      reported.current = true
      setPlaying(false)
      const winnerSlot = state.winner ? slotOfToken(state.winner) : null
      onFinish?.({ winnerSlot, plies: state.moves.length })
    }
    /* eslint-disable-next-line */
  }, [state?.is_over])

  const newGame = async (swap = swapped) => {
    reported.current = false
    setPlaying(false)
    setSwapped(swap)
    await game.reset(config, 1)
  }
  const nextGame = () => newGame(autoAlternate ? !swapped : swapped)

  const names = { 1: agentLabel(tokenSpec(1)), 2: agentLabel(tokenSpec(2)) }

  return (
    <div>
      <div className="space-y-3">
        <StatusBanner state={state} names={names} />
        <Card className="p-3 sm:p-5">
          {state && (
            <Board board={state.board} config={state.config} winningCells={state.winning_cells}
                   lastCell={state.last_cell} legalMoves={state.legal_moves} disabled currentPlayer={state.current_player} />
          )}
        </Card>
        <div className="flex flex-wrap items-center gap-2">
          <button className="btn btn-primary" onClick={() => setPlaying((p) => !p)} disabled={!state || state.is_over}>
            {playing ? 'Pause' : state?.moves.length ? 'Resume' : 'Start match'}
          </button>
          <button className="btn" onClick={() => game.aiMove(tokenSpec(state.current_player))} disabled={!state || state.is_over || busy || playing}>Step</button>
          <button className="btn" onClick={nextGame}>{state?.is_over ? 'Next game' : 'Restart'}</button>
          <label className="ml-auto flex items-center gap-2 text-xs text-ink2">
            Speed
            <input type="range" min="0" max="1500" step="50" value={1500 - delay} className="w-28"
                   onChange={(e) => setDelay(1500 - Number(e.target.value))} aria-label="Playback speed" />
          </label>
          {busy && <Spinner label="thinking..." />}
        </div>
        <ErrorBanner message={error} onClose={() => game.setError(null)} />
        <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-ink2">
          <span><TokenDot player={1} /> <b className="text-ink">{names[1]}</b> (moves first)</span>
          <span><TokenDot player={2} /> <b className="text-ink">{names[2]}</b></span>
        </div>
      </div>
    </div>
  )
}
