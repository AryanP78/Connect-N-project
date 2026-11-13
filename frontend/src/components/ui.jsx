import { AGENT_COLORS, AGENT_CATALOG, defaultSpec, kindOfLabel } from '../services/agents.js'

export function Card({ className = '', children, ...rest }) {
  return <div className={`card ${className}`} {...rest}>{children}</div>
}

export function SectionTitle({ eyebrow, title, children }) {
  return (
    <div className="mb-5">
      {eyebrow && <div className="label mb-1">{eyebrow}</div>}
      <h2 className="text-xl sm:text-2xl font-semibold tracking-tight">{title}</h2>
      {children && <p className="text-ink2 text-sm mt-1 max-w-3xl">{children}</p>}
    </div>
  )
}

export function Stat({ label, value, sub, color }) {
  return (
    <div className="rounded-xl bg-raised border border-line px-3 py-2.5 min-w-0">
      <div className="label">{label}</div>
      <div className="text-lg font-semibold tabular-nums truncate" style={color ? { color } : undefined}>{value}</div>
      {sub && <div className="text-[11px] text-muted truncate">{sub}</div>}
    </div>
  )
}

export function Dot({ color, className = '' }) {
  return <span className={`inline-block w-2.5 h-2.5 rounded-full ${className}`} style={{ background: color }} />
}

export function TokenDot({ player, size = 14 }) {
  const color = player === 1 ? '#e66767' : '#eda100'
  return <span className="inline-block rounded-full align-middle" style={{ width: size, height: size, background: color }} />
}

export function Spinner({ label }) {
  return (
    <span className="inline-flex items-center gap-2 text-ink2 text-sm">
      <span className="w-3.5 h-3.5 rounded-full border-2 border-muted border-t-accent animate-spin" />
      {label}
    </span>
  )
}

export function ErrorBanner({ message, onClose }) {
  if (!message) return null
  return (
    <div role="alert" className="rounded-lg border border-bad/60 bg-bad/10 text-sm text-ink px-3 py-2 flex justify-between gap-3">
      <span>{message}</span>
      {onClose && <button className="text-muted hover:text-ink" onClick={onClose} aria-label="Dismiss">x</button>}
    </div>
  )
}

/** Agent chooser: kind + its parameter (search depth or simulation budget). */
export function AgentPicker({ value, onChange, label }) {
  const entry = AGENT_CATALOG.find((a) => a.kind === value.kind)
  const param = entry?.param
  return (
    <div className="space-y-2">
      {label && <div className="label flex items-center gap-2"><Dot color={AGENT_COLORS[value.kind]} />{label}</div>}
      <select className="field" value={value.kind} onChange={(e) => onChange(defaultSpec(e.target.value))}
              aria-label={`${label ?? 'Agent'} type`}>
        {AGENT_CATALOG.map((a) => <option key={a.kind} value={a.kind}>{a.label}</option>)}
      </select>
      {param && !param.options && (
        <div>
          <div className="flex justify-between text-xs text-ink2">
            <span>Search depth</span><span className="tabular-nums">{value[param.name]} {param.unit}</span>
          </div>
          <input type="range" min={param.min} max={param.max} value={value[param.name]}
                 onChange={(e) => onChange({ ...value, [param.name]: Number(e.target.value) })} />
        </div>
      )}
      {param?.options && (
        <div>
          <div className="text-xs text-ink2 mb-1">Simulations per move</div>
          <select className="field" value={value[param.name]}
                  onChange={(e) => onChange({ ...value, [param.name]: Number(e.target.value) })}>
            {param.options.map((o) => <option key={o} value={o}>{o.toLocaleString()}</option>)}
          </select>
        </div>
      )}
      <p className="text-xs text-muted">{entry?.blurb}</p>
    </div>
  )
}

/** Board size / N / rule-set selector. */
export function ConfigPanel({ config, onChange, disabled }) {
  const set = (patch) => {
    const next = { ...config, ...patch }
    next.n = Math.min(next.n, Math.max(next.rows, next.cols))
    onChange(next)
  }
  const Num = ({ label, k, min, max }) => (
    <label className="block">
      <div className="flex justify-between text-xs text-ink2"><span>{label}</span><span className="tabular-nums">{config[k]}</span></div>
      <input type="range" min={min} max={max} value={config[k]} disabled={disabled}
             onChange={(e) => set({ [k]: Number(e.target.value) })} />
    </label>
  )
  return (
    <div className="space-y-3">
      <Num label="Rows" k="rows" min={3} max={10} />
      <Num label="Columns" k="cols" min={3} max={10} />
      <Num label="Connect N (to win)" k="n" min={3} max={Math.max(config.rows, config.cols, 3)} />
      <div className="flex rounded-lg overflow-hidden border border-line text-sm" role="group" aria-label="Rule set">
        {[[true, 'Gravity'], [false, 'Free placement']].map(([g, name]) => (
          <button key={name} disabled={disabled} onClick={() => set({ gravity: g })}
            className={`flex-1 py-1.5 ${config.gravity === g ? 'bg-accent text-white' : 'bg-raised text-ink2 hover:text-ink'}`}>
            {name}
          </button>
        ))}
      </div>
      {!config.gravity && config.rows * config.cols > 49 && (
        <p className="text-xs text-muted">Large free-placement boards have many moves; search depth is automatically limited.</p>
      )}
    </div>
  )
}

export function StatusBanner({ state, humanPlayer, names = {} }) {
  if (!state) return null
  const name = (p) => names[p] ?? `Player ${p}`
  let text, tone
  if (state.winner) {
    text = humanPlayer ? (state.winner === humanPlayer ? 'You win!' : 'The AI wins') : `${name(state.winner)} wins`
    tone = humanPlayer && state.winner !== humanPlayer ? 'bad' : 'good'
  } else if (state.is_draw) {
    text = 'Draw - the board is full'; tone = 'neutral'
  } else {
    text = humanPlayer ? (state.current_player === humanPlayer ? 'Your turn' : 'AI is thinking') : `${name(state.current_player)} to move`
    tone = 'turn'
  }
  const cls = { good: 'border-good/60 bg-good/10', bad: 'border-bad/60 bg-bad/10', neutral: 'border-line bg-raised', turn: 'border-line bg-raised' }[tone]
  return (
    <div className={`rounded-xl border px-4 py-2.5 flex items-center gap-3 ${cls}`} role="status" aria-live="polite">
      {!state.is_over && <TokenDot player={state.current_player} size={16} />}
      {state.winner ? <TokenDot player={state.winner} size={16} /> : null}
      <span className="font-semibold">{text}</span>
      <span className="ml-auto text-xs text-muted tabular-nums">move {state.moves.length}</span>
    </div>
  )
}

export { kindOfLabel }
