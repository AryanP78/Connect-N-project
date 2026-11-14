import { useMemo, useState } from 'react'

const S = 64      // cell size in SVG units
const PAD = 12
const P_COLOR = { 1: '#e66767', 2: '#eda100' }
const P_DARK = { 1: '#b83c3c', 2: '#b07a00' }

/**
 * Interactive SVG Connect-N board (row 0 is the top row).
 *  - gravity mode: clicking anywhere in a column drops a token; a ghost token previews the landing cell.
 *  - free mode: every empty cell is clickable.
 */
export default function Board({ board, config, winningCells = [], lastCell, legalMoves = [], onMove,
  disabled = false, currentPlayer = 1, showColumnNumbers = true, highlightMoves = [] }) {
  const { rows, cols, gravity } = config
  const [hover, setHover] = useState(null) // column (gravity) or "r,c" (free)
  const W = cols * S + PAD * 2
  const H = rows * S + PAD * 2 + (showColumnNumbers ? 22 : 0)
  const top = showColumnNumbers ? 22 : 0
  const legal = useMemo(() => new Set(legalMoves), [legalMoves])
  const win = useMemo(() => new Set(winningCells.map(([r, c]) => `${r},${c}`)), [winningCells])
  const hl = useMemo(() => new Set(highlightMoves), [highlightMoves])

  const landingRow = (c) => {
    for (let r = rows - 1; r >= 0; r--) if (board[r][c] === 0) return r
    return -1
  }
  const canPlay = (move) => !disabled && legal.has(move)
  const cx = (c) => PAD + c * S + S / 2
  const cy = (r) => top + PAD + r * S + S / 2

  const ghost = (() => {
    if (disabled || hover == null) return null
    if (gravity) {
      const r = landingRow(hover)
      return r >= 0 ? { r, c: hover } : null
    }
    const [r, c] = hover.split(',').map(Number)
    return board[r][c] === 0 ? { r, c } : null
  })()

  const cells = []
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const v = board[r][c]
      const isLast = lastCell && lastCell[0] === r && lastCell[1] === c
      const isWin = win.has(`${r},${c}`)
      cells.push(
        <g key={`${r}-${c}`}>
          <circle cx={cx(c)} cy={cy(r)} r={S * 0.4} fill="#0a1224" />
          {v !== 0 && (
            <g className={isLast ? (gravity ? 'disc-drop' : 'disc-pop') : undefined}
               style={isLast && gravity ? { '--from': `${-(r * S + S + PAD + top)}px` } : undefined}>
              <circle cx={cx(c)} cy={cy(r)} r={S * 0.4} fill={P_COLOR[v]} stroke={P_DARK[v]} strokeWidth="3" />
              {v === 1
                ? <circle cx={cx(c)} cy={cy(r)} r={S * 0.17} fill={P_DARK[v]} opacity=".55" />
                : <circle cx={cx(c)} cy={cy(r)} r={S * 0.2} fill="none" stroke={P_DARK[v]} strokeWidth="4" opacity=".6" />}
              {isLast && !isWin && <circle cx={cx(c)} cy={cy(r)} r={S * 0.4 + 2} fill="none" stroke="#fff" strokeOpacity=".5" strokeWidth="2" />}
              {isWin && <circle className="win-ring" cx={cx(c)} cy={cy(r)} r={S * 0.4 + 3} fill="none" stroke="#fff" strokeWidth="4" />}
            </g>
          )}
          {v === 0 && !gravity && canPlay(r * cols + c) && (
            <rect x={cx(c) - S / 2} y={cy(r) - S / 2} width={S} height={S} fill="transparent"
              style={{ cursor: 'pointer' }}
              onMouseEnter={() => setHover(`${r},${c}`)} onMouseLeave={() => setHover(null)}
              onClick={() => onMove?.(r * cols + c)} />
          )}
          {v === 0 && hl.has(gravity ? c : r * cols + c) && !gravity && (
            <circle cx={cx(c)} cy={cy(r)} r={S * 0.12} fill="#3987e5" />
          )}
        </g>,
      )
    }
  }

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full max-w-[620px] mx-auto select-none" role="img"
         aria-label={`Connect ${config.n} board, ${rows} rows by ${cols} columns`}>
      <rect x="0" y={top} width={W} height={H - top} rx="18" fill="#14213d" stroke="#243a66" strokeWidth="2" />
      {showColumnNumbers && Array.from({ length: cols }, (_, c) => (
        <text key={c} x={cx(c)} y={15} textAnchor="middle" fontSize="12" fill={hl.has(c) && gravity ? '#3987e5' : '#7d8aa6'}
              fontWeight={hl.has(c) && gravity ? 700 : 500}>{c + 1}</text>
      ))}
      {cells}
      {ghost && (
        <circle cx={cx(ghost.c)} cy={cy(ghost.r)} r={S * 0.4} fill={P_COLOR[currentPlayer]} opacity=".35" pointerEvents="none" />
      )}
      {gravity && Array.from({ length: cols }, (_, c) => (
        <rect key={`hit-${c}`} x={PAD + c * S} y={top} width={S} height={H - top}
          fill={hover === c && canPlay(c) ? '#ffffff0d' : 'transparent'}
          style={{ cursor: canPlay(c) ? 'pointer' : 'default' }}
          onMouseEnter={() => setHover(c)} onMouseLeave={() => setHover(null)}
          onClick={() => canPlay(c) && onMove?.(c)} />
      ))}
    </svg>
  )
}
