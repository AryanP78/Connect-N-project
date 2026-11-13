"""Pre-computed board geometry shared by the engine and the heuristic.

For a given :class:`GameConfig` the geometry holds every "window" (a run of ``n``
consecutive cells in one of the four line directions), a centre-preference map,
and a canonical centre-first move ordering.  It is computed once per
configuration and cached, so search code never rebuilds it.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Tuple

import numpy as np

from .config import GameConfig

# (d_row, d_col): horizontal, vertical, diagonal "\" and diagonal "/".
DIRECTIONS: Tuple[Tuple[int, int], ...] = ((0, 1), (1, 0), (1, 1), (1, -1))


@dataclass(frozen=True, eq=False)
class Geometry:
    config: GameConfig
    windows: np.ndarray       # (W, n) int32 - flat cell indices of every window
    center: np.ndarray        # (rows*cols,) float64 in [0, 1] - closeness to centre
    support: np.ndarray       # (rows*cols,) int32 - cell directly underneath (row+1), clipped
    is_bottom: np.ndarray     # (rows*cols,) bool - cell is on the bottom row
    move_order: Tuple[int, ...]  # all possible moves, most central first


def _build_windows(rows: int, cols: int, n: int) -> np.ndarray:
    windows = []
    for r in range(rows):
        for c in range(cols):
            for dr, dc in DIRECTIONS:
                end_r, end_c = r + dr * (n - 1), c + dc * (n - 1)
                if 0 <= end_r < rows and 0 <= end_c < cols:
                    windows.append([(r + dr * i) * cols + (c + dc * i) for i in range(n)])
    if not windows:
        return np.zeros((0, n), dtype=np.int32)
    return np.asarray(windows, dtype=np.int32)


@lru_cache(maxsize=128)
def get_geometry(config: GameConfig) -> Geometry:
    rows, cols = config.rows, config.cols
    windows = _build_windows(rows, cols, config.n)

    mid_r, mid_c = (rows - 1) / 2.0, (cols - 1) / 2.0
    center = np.zeros(rows * cols, dtype=np.float64)
    for r in range(rows):
        for c in range(cols):
            col_term = 1.0 - abs(c - mid_c) / max(mid_c, 0.5)
            if config.gravity:
                center[r * cols + c] = col_term
            else:  # free placement: both axes matter
                row_term = 1.0 - abs(r - mid_r) / max(mid_r, 0.5)
                center[r * cols + c] = 0.5 * (col_term + row_term)

    support = np.zeros(rows * cols, dtype=np.int32)
    is_bottom = np.zeros(rows * cols, dtype=bool)
    for r in range(rows):
        for c in range(cols):
            idx = r * cols + c
            if r == rows - 1:
                is_bottom[idx] = True
            else:
                support[idx] = (r + 1) * cols + c

    if config.gravity:
        move_order = tuple(sorted(range(cols), key=lambda c: (abs(c - mid_c), c)))
    else:
        move_order = tuple(sorted(
            range(rows * cols),
            key=lambda i: ((i // cols - mid_r) ** 2 + (i % cols - mid_c) ** 2, i),
        ))
    return Geometry(config, windows, center, support, is_bottom, move_order)
