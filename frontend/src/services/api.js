// Thin client for the FastAPI backend. The server is stateless: every call carries the
// configuration and the move list, and the engine validates the whole history.
const BASE = import.meta.env.VITE_API_URL ?? ''

async function request(path, body) {
  const res = await fetch(BASE + path, {
    method: body === undefined ? 'GET' : 'POST',
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const data = await res.json()
      detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
    } catch { /* keep status text */ }
    throw new Error(detail)
  }
  return res.json()
}

export const api = {
  health: () => request('/api/health'),
  newGame: (config, first_player = 1) => request('/api/game/new', { config, first_player }),
  state: (config, moves, first_player) => request('/api/game/state', { config, moves, first_player }),
  move: (config, moves, first_player, move) => request('/api/game/move', { config, moves, first_player, move }),
  aiMove: (config, moves, first_player, agent) =>
    request('/api/game/ai-move', { config, moves, first_player, agent }),
  series: (payload) => request('/api/arena/series', payload),
  benchmarks: () => request('/api/benchmarks'),
}
