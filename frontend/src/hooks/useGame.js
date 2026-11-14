import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../services/api.js'

export const DEFAULT_CONFIG = { rows: 6, cols: 7, n: 4, gravity: true }

/**
 * Game state backed by the stateless API.
 */
export function useGame(initialConfig = DEFAULT_CONFIG) {
  const [config, setConfig] = useState(initialConfig)
  const [firstPlayer, setFirstPlayer] = useState(1)
  const [state, setState] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const busyRef = useRef(false)
  const epoch = useRef(0) // bumped on reset so late responses from an old game are ignored

  const guarded = useCallback(async (fn) => {
    if (busyRef.current) return null
    busyRef.current = true
    setBusy(true)
    setError(null)
    const mine = epoch.current
    try {
      const out = await fn()
      return mine === epoch.current ? out : null
    } catch (e) {
      if (mine === epoch.current) setError(e.message)
      return null
    } finally {
      if (mine === epoch.current) { busyRef.current = false; setBusy(false) }
    }
  }, [])

  const reset = useCallback(async (cfg = config, first = firstPlayer) => {
    epoch.current += 1
    busyRef.current = false
    setBusy(false)
    setError(null)
    setConfig(cfg)
    setFirstPlayer(first)
    try {
      setState(await api.newGame(cfg, first))
    } catch (e) {
      setError(e.message)
    }
  }, [config, firstPlayer])

  useEffect(() => { reset(initialConfig, 1) /* eslint-disable-next-line */ }, [])

  const play = useCallback((move) => guarded(async () => {
    const next = await api.move(config, state.moves, firstPlayer, move)
    setState(next)
    return next
  }), [config, state, firstPlayer, guarded])

  const aiMove = useCallback((spec) => guarded(async () => {
    const res = await api.aiMove(config, state.moves, firstPlayer, spec)
    setState(res.state)
    return res
  }), [config, state, firstPlayer, guarded])

  const undo = useCallback((count = 1) => guarded(async () => {
    const moves = state.moves.slice(0, Math.max(0, state.moves.length - count))
    const next = await api.state(config, moves, firstPlayer)
    setState(next)
    return next
  }), [config, state, firstPlayer, guarded])

  return { config, firstPlayer, state, busy, error, setError, reset, play, aiMove, undo }
}
