import { Link } from 'react-router-dom'
import { AGENT_CATALOG, AGENT_COLORS } from '../services/agents.js'
import { Card, Dot } from '../components/ui.jsx'

// Decorative hero position (static, rendered with the same disc colours as the board).
const HERO = ['.......', '.......', '...2...', '..212..', '..1211.', '.12121.']

function HeroBoard() {
  const S = 44
  return (
    <svg viewBox={`0 0 ${7 * S + 20} ${6 * S + 20}`} className="w-full max-w-md" aria-hidden="true">
      <rect width={7 * S + 20} height={6 * S + 20} rx="18" fill="#14213d" stroke="#243a66" strokeWidth="2" />
      {HERO.map((row, r) => [...row].map((v, c) => (
        <circle key={`${r}${c}`} cx={10 + c * S + S / 2} cy={10 + r * S + S / 2} r={S * 0.38}
          fill={v === '1' ? '#e66767' : v === '2' ? '#eda100' : '#0a1224'} />
      )))}
    </svg>
  )
}

const FEATURES = [
  { to: '/play', title: 'Play Game', text: 'Challenge the AI on any board size, with four difficulty levels - or pit two agents against each other.', cta: 'Start playing' },
  { to: '/arena', title: 'AI Arena', text: 'Pick any two agents, watch them play move by move, and keep score across a series of games.', cta: 'Enter the arena' },
  { to: '/analytics', title: 'Algorithm Comparison', text: 'Win rates, decision time, nodes explored and search depth - measured from real tournaments.', cta: 'See the results' },
]

export default function Home() {
  return (
    <div className="space-y-12">
      <section className="grid md:grid-cols-2 gap-8 items-center">
        <div className="space-y-5">
          <div className="label">University AI project</div>
          <h1 className="text-4xl sm:text-5xl font-bold tracking-tight leading-[1.05]">
            Connect-N <span className="text-accent">AI</span>
          </h1>
          <p className="text-ink2 text-lg max-w-xl">
            An intelligent game-playing platform: one shared game engine, five AI agents - Random, Greedy,
            Minimax, Alpha-Beta Pruning and Monte Carlo Tree Search - one benchmarking framework and this interactive application.
          </p>
          <div className="flex flex-wrap gap-3">
            <Link to="/play" className="btn btn-primary">Play vs AI</Link>
            <Link to="/arena" className="btn">Watch AI vs AI</Link>
            <Link to="/analytics" className="btn">Algorithm comparison</Link>
          </div>
          <p className="text-xs text-muted">Default rules: 6 x 7 board, connect 4, gravity. Rows, columns, N and free-placement mode are configurable.</p>
        </div>
        <div className="flex justify-center md:justify-end"><HeroBoard /></div>
      </section>

      <section className="grid md:grid-cols-3 gap-4">
        {FEATURES.map((f) => (
          <Link key={f.to} to={f.to} className="group">
            <Card className="p-5 h-full transition-colors group-hover:border-accent/60">
              <h3 className="font-semibold text-lg">{f.title}</h3>
              <p className="text-sm text-ink2 mt-2">{f.text}</p>
              <div className="mt-4 text-sm text-accent font-medium">{f.cta} &rarr;</div>
            </Card>
          </Link>
        ))}
      </section>

      <section>
        <div className="label mb-3">The five agents</div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-3">
          {AGENT_CATALOG.map((a) => (
            <Card key={a.kind} className="p-4">
              <div className="flex items-center gap-2 font-semibold"><Dot color={AGENT_COLORS[a.kind]} />{a.label}</div>
              <p className="text-xs text-ink2 mt-2">{a.blurb}</p>
            </Card>
          ))}
        </div>
      </section>
    </div>
  )
}
