"""Reusable heuristic evaluation for Connect-N positions.

The evaluator scores a position from one player's point of view by scanning every
*window* (a run of ``n`` consecutive cells; see :mod:`backend.engine.geometry`):

* A window that contains only the player's tokens (plus empties) is an **open
  window** worth ``growth ** (k - 1)`` where ``k`` is the number of tokens in it.
  Windows with ``k = n - 1`` are the classic "three in a row" threats.
* The same is subtracted for the opponent's open windows (scaled by ``opp_factor``
  so defence is valued slightly above attack).
* **Immediate threats** - empty cells that complete a window *and* are playable right
  now - earn an extra bonus (own) or penalty (opponent): they are the blocking
  opportunities.
* A **centre preference** rewards tokens close to the middle, where they take part in
  the most windows.

Terminal states always override the heuristic: a win scores ``+WIN_SCORE``, a loss
``-WIN_SCORE`` and a draw ``0``.  Heuristic values are clipped to
``+-MAX_HEURISTIC`` which is far below ``WIN_SCORE``, so a heuristic score can never
be mistaken for (or outrank) a real win.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, List, Optional

import numpy as np

from ..engine import ConnectNGame, GameConfig, get_geometry

WIN_SCORE = 1_000_000.0
MAX_HEURISTIC = WIN_SCORE / 10.0


@dataclass(frozen=True)
class HeuristicWeights:
    """Tunable weights of the evaluation function."""

    growth: float = 6.0                 # value of a k-token open window = growth ** (k - 1)
    opp_factor: float = 1.15            # opponent windows are weighted a bit more (defence)
    immediate_threat: float = 40.0      # bonus per own playable winning cell
    opp_immediate_threat: float = 60.0  # penalty per opponent playable winning cell
    center: float = 3.0                 # per-token centre-closeness weight

    def to_dict(self) -> Dict[str, float]:
        return asdict(self)


DEFAULT_WEIGHTS = HeuristicWeights()


class Evaluator:
    """Fast, vectorised evaluator bound to one board configuration."""

    def __init__(self, config: GameConfig, weights: Optional[HeuristicWeights] = None):
        self.config = config
        self.weights = weights or DEFAULT_WEIGHTS
        self.geometry = get_geometry(config)
        n = config.n
        # value of a window holding k tokens of one colour and none of the other
        self._window_value = np.zeros(n + 1, dtype=np.float64)
        for k in range(1, n):
            self._window_value[k] = self.weights.growth ** (k - 1)

    # ------------------------------------------------------------------ core
    def _playable(self, cells: np.ndarray) -> np.ndarray:
        empty = cells == 0
        if not self.config.gravity:
            return empty
        geo = self.geometry
        return empty & (geo.is_bottom | (cells[geo.support] != 0))

    def _threat_cells(self, vals: np.ndarray, own: np.ndarray, other: np.ndarray,
                      windows: np.ndarray, cells: np.ndarray, player_count: np.ndarray,
                      playable: np.ndarray) -> int:
        """Number of distinct playable cells that would complete a window for a player."""
        n = self.config.n
        mask = (player_count == n - 1) & (other == 0)
        if not mask.any():
            return 0
        sel_windows = windows[mask]
        sel_empty = (vals[mask] == 0)
        completing = sel_windows[np.arange(len(sel_windows)), sel_empty.argmax(axis=1)]
        marker = np.zeros(cells.shape[0], dtype=bool)
        marker[completing] = True
        return int((marker & playable).sum())

    def breakdown(self, cells: np.ndarray, player: int) -> Dict[str, object]:
        """Detailed (and explainable) feature breakdown from ``player``'s perspective."""
        w, geo, n = self.weights, self.geometry, self.config.n
        other_player = 3 - player
        windows = geo.windows
        vals = cells[windows] if len(windows) else np.zeros((0, n), dtype=np.int8)
        mine = (vals == player).sum(axis=1)
        theirs = (vals == other_player).sum(axis=1)

        my_open = theirs == 0
        their_open = mine == 0
        my_counts = np.bincount(mine[my_open], minlength=n + 1)
        their_counts = np.bincount(theirs[their_open], minlength=n + 1)

        window_score = float((self._window_value[mine] * my_open).sum())
        opp_window_score = float((self._window_value[theirs] * their_open).sum())

        playable = self._playable(cells)
        my_threats = self._threat_cells(vals, mine, theirs, windows, cells, mine, playable)
        opp_threats = self._threat_cells(vals, theirs, mine, windows, cells, theirs, playable)

        centre_mine = float(geo.center[cells == player].sum())
        centre_theirs = float(geo.center[cells == other_player].sum())

        components = {
            "windows": window_score,
            "opponent_windows": -w.opp_factor * opp_window_score,
            "immediate_threats": w.immediate_threat * my_threats,
            "opponent_immediate_threats": -w.opp_immediate_threat * opp_threats,
            "center": w.center * (centre_mine - centre_theirs),
        }
        total = float(np.clip(sum(components.values()), -MAX_HEURISTIC, MAX_HEURISTIC))
        return {
            "total": total,
            "components": components,
            "own_windows_by_tokens": {int(k): int(my_counts[k]) for k in range(1, n)},
            "opponent_windows_by_tokens": {int(k): int(their_counts[k]) for k in range(1, n)},
            "own_immediate_threats": my_threats,
            "opponent_immediate_threats": opp_threats,
        }

    def evaluate_cells(self, cells: np.ndarray, player: int) -> float:
        """Heuristic score of a (non-terminal) board for ``player``.  Hot path for search."""
        w, geo, n = self.weights, self.geometry, self.config.n
        windows = geo.windows
        vals = cells[windows] if len(windows) else np.zeros((0, n), dtype=np.int8)
        other_player = 3 - player
        mine = (vals == player).sum(axis=1)
        theirs = (vals == other_player).sum(axis=1)
        wv = self._window_value
        score = float((wv[mine] * (theirs == 0)).sum()) - w.opp_factor * float((wv[theirs] * (mine == 0)).sum())

        playable = self._playable(cells)
        my_t = self._threat_cells(vals, mine, theirs, windows, cells, mine, playable)
        opp_t = self._threat_cells(vals, theirs, mine, windows, cells, theirs, playable)
        score += w.immediate_threat * my_t - w.opp_immediate_threat * opp_t

        score += w.center * float(geo.center[cells == player].sum() - geo.center[cells == other_player].sum())
        return float(np.clip(score, -MAX_HEURISTIC, MAX_HEURISTIC))

    # -------------------------------------------------------------- public API
    def evaluate(self, game: ConnectNGame, player: int) -> float:
        """Score ``game`` for ``player``; terminal states override the heuristic."""
        if game.winner:
            return WIN_SCORE if game.winner == player else -WIN_SCORE
        if game.is_draw:
            return 0.0
        return self.evaluate_cells(game.cells, player)


_EVALUATORS: Dict[tuple, Evaluator] = {}


def get_evaluator(config: GameConfig, weights: Optional[HeuristicWeights] = None) -> Evaluator:
    key = (config, weights or DEFAULT_WEIGHTS)
    ev = _EVALUATORS.get(key)
    if ev is None:
        ev = _EVALUATORS[key] = Evaluator(config, weights)
    return ev


def evaluate(game: ConnectNGame, player: int, weights: Optional[HeuristicWeights] = None) -> float:
    """Convenience wrapper: score ``game`` for ``player``."""
    return get_evaluator(game.config, weights).evaluate(game, player)
