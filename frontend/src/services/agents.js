// Agent metadata shared by the UI (mirrors backend/agents/factory.py).
// Colours follow the entity: each agent keeps one hue everywhere (dark-surface steps of a
// palette validated for colour-blind separation).
export const AGENT_COLORS = {
  random: '#3987e5',
  greedy: '#d95926',
  minimax: '#199e70',
  alphabeta: '#c98500',
  mcts: '#d55181',
}

export const AGENT_CATALOG = [
  { kind: 'random', label: 'Random', blurb: 'Uniformly random legal moves (baseline).' },
  { kind: 'greedy', label: 'Greedy', blurb: 'Wins or blocks at once, otherwise maximises a 1-move heuristic.' },
  { kind: 'minimax', label: 'Minimax', blurb: 'Depth-limited adversarial search.',
    param: { name: 'depth', min: 1, max: 5, default: 3, unit: 'plies' } },
  { kind: 'alphabeta', label: 'Alpha-Beta', blurb: 'Minimax with pruning: same moves, far fewer nodes.',
    param: { name: 'depth', min: 1, max: 7, default: 5, unit: 'plies' } },
  { kind: 'mcts', label: 'Monte Carlo (MCTS)', blurb: 'UCT tree search with random rollouts.',
    param: { name: 'simulations', options: [50, 100, 250, 500, 1000, 2000, 5000], default: 500, unit: 'sims' } },
]

export const DIFFICULTIES = {
  easy: { kind: 'random', label: 'Easy', detail: 'Random' },
  medium: { kind: 'greedy', label: 'Medium', detail: 'Greedy' },
  hard: { kind: 'alphabeta', depth: 4, label: 'Hard', detail: 'Alpha-Beta, depth 4' },
  expert: { kind: 'alphabeta', depth: 6, label: 'Expert', detail: 'Alpha-Beta, depth 6' },
}

export function defaultSpec(kind) {
  const entry = AGENT_CATALOG.find((a) => a.kind === kind)
  const spec = { kind }
  if (entry?.param) spec[entry.param.name] = entry.param.default
  return spec
}

export function agentLabel(spec) {
  if (!spec) return ''
  switch (spec.kind) {
    case 'random': return 'Random'
    case 'greedy': return 'Greedy'
    case 'minimax': return `Minimax (d=${spec.depth ?? 3})`
    case 'alphabeta': return `Alpha-Beta (d=${spec.depth ?? 4})`
    case 'mcts': return `MCTS (n=${spec.simulations ?? 500})`
    default: return spec.kind
  }
}

// Backend labels such as "Alpha-Beta (d=4)" -> agent kind, for colouring.
export function kindOfLabel(label = '') {
  const l = label.toLowerCase()
  if (l.includes('alpha')) return 'alphabeta'
  if (l.includes('minimax')) return 'minimax'
  if (l.includes('mcts')) return 'mcts'
  if (l.includes('greedy')) return 'greedy'
  return 'random'
}

export const colorOfLabel = (label) => AGENT_COLORS[kindOfLabel(label)]

export function moveLabel(move, config) {
  if (config.gravity) return `${Number(move) + 1}`
  const m = Number(move)
  return `${Math.floor(m / config.cols) + 1},${(m % config.cols) + 1}`
}

export function moveName(move, config) {
  return config.gravity ? `column ${Number(move) + 1}` : `cell (${moveLabel(move, config)})`
}

export const WIN_SCORE = 1_000_000
export function isForced(score) { return score != null && Math.abs(score) >= WIN_SCORE - 10_000 }
export function fmtNum(v, digits = 1) {
  if (v == null || Number.isNaN(v)) return '-'
  if (Math.abs(v) >= 1e6) return `${(v / 1e6).toFixed(1)}M`
  if (Math.abs(v) >= 1e4) return `${(v / 1e3).toFixed(0)}k`
  if (Math.abs(v) >= 1e3) return `${(v / 1e3).toFixed(1)}k`
  if (Math.abs(v) >= 100) return v.toFixed(0)
  if (Math.abs(v) >= 10) return v.toFixed(digits)
  return v.toFixed(Math.min(2, digits + 1))
}
