"""The shared Connect-N game engine.

This module is deliberately free of any AI code: it only knows the rules.  Every
agent, the benchmark framework and the web API talk to the game exclusively through
:class:`ConnectNGame`.

Conventions
-----------
* Players are ``1`` and ``2``; ``0`` marks an empty cell.
* The board is stored flat (``rows * cols`` int8 NumPy array); row 0 is the **top**.
* A *move* is an ``int``: a column index in gravity mode, a flat cell index
  (``row * cols + col``) in free-placement mode.
* ``play`` validates every move before it touches the board, and ``undo`` restores the
  exact previous state, which lets search algorithms avoid copying the board.
"""
from __future__ import annotations

import numbers
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

from .config import GameConfig
from .geometry import DIRECTIONS, get_geometry

EMPTY, PLAYER_1, PLAYER_2 = 0, 1, 2


class IllegalMoveError(ValueError):
    """Raised when a move is not legal in the current position."""


def opponent(player: int) -> int:
    return 3 - player


class ConnectNGame:
    def __init__(self, config: Optional[GameConfig] = None, first_player: int = PLAYER_1):
        if first_player not in (PLAYER_1, PLAYER_2):
            raise ValueError("first_player must be 1 or 2")
        self.config = config or GameConfig()
        self.first_player = first_player
        self._geometry = get_geometry(self.config)
        self.reset()

    # ------------------------------------------------------------------ state
    def reset(self) -> "ConnectNGame":
        cfg = self.config
        self._cells = np.zeros(cfg.cells, dtype=np.int8)
        self._cells_view = self._cells.view()
        self._cells_view.flags.writeable = False
        self._heights: List[int] = [0] * cfg.cols
        self._history: List[int] = []        # moves, in order
        self._cell_history: List[int] = []   # flat cell of each move
        self.current_player: int = self.first_player
        self.winner: int = 0
        self.winning_cells: List[Tuple[int, int]] = []
        return self

    def copy(self) -> "ConnectNGame":
        clone = ConnectNGame.__new__(ConnectNGame)
        clone.config = self.config
        clone.first_player = self.first_player
        clone._geometry = self._geometry
        clone._cells = self._cells.copy()
        clone._cells_view = clone._cells.view()
        clone._cells_view.flags.writeable = False
        clone._heights = list(self._heights)
        clone._history = list(self._history)
        clone._cell_history = list(self._cell_history)
        clone.current_player = self.current_player
        clone.winner = self.winner
        clone.winning_cells = list(self.winning_cells)
        return clone

    @classmethod
    def from_moves(cls, config: Optional[GameConfig], moves: Iterable[int],
                   first_player: int = PLAYER_1) -> "ConnectNGame":
        """Rebuild a position by replaying a move list (every move is validated)."""
        game = cls(config, first_player)
        for move in moves:
            game.play(move)
        return game

    # --------------------------------------------------------------- accessors
    @property
    def cells(self) -> np.ndarray:
        """Read-only flat view of the board (always in sync with the game)."""
        return self._cells_view

    @property
    def board(self) -> np.ndarray:
        """A (rows, cols) copy of the board; row 0 is the top row."""
        return self._cells.reshape(self.config.rows, self.config.cols).copy()

    @property
    def history(self) -> List[int]:
        return list(self._history)

    @property
    def move_count(self) -> int:
        return len(self._history)

    @property
    def last_move(self) -> Optional[int]:
        return self._history[-1] if self._history else None

    @property
    def last_cell(self) -> Optional[Tuple[int, int]]:
        if not self._cell_history:
            return None
        return divmod(self._cell_history[-1], self.config.cols)

    @property
    def is_draw(self) -> bool:
        return self.winner == 0 and len(self._history) == self.config.cells

    @property
    def is_over(self) -> bool:
        return self.winner != 0 or len(self._history) == self.config.cells

    @property
    def status(self) -> str:
        if self.winner:
            return f"player_{self.winner}_wins"
        if self.is_draw:
            return "draw"
        return "in_progress"

    # ------------------------------------------------------------------ moves
    def _cell_for(self, move) -> int:
        """Translate a move to a flat cell index, raising IllegalMoveError if illegal."""
        if isinstance(move, bool) or not isinstance(move, numbers.Integral):
            raise IllegalMoveError(f"move must be an integer, got {move!r}")
        move = int(move)
        cfg = self.config
        if cfg.gravity:
            if not 0 <= move < cfg.cols:
                raise IllegalMoveError(f"column {move} is outside the board (0..{cfg.cols - 1})")
            height = self._heights[move]
            if height >= cfg.rows:
                raise IllegalMoveError(f"column {move} is full")
            return (cfg.rows - 1 - height) * cfg.cols + move
        if not 0 <= move < cfg.cells:
            raise IllegalMoveError(f"cell {move} is outside the board (0..{cfg.cells - 1})")
        if self._cells[move] != EMPTY:
            raise IllegalMoveError(f"cell {move} is already occupied")
        return move

    def is_legal(self, move) -> bool:
        if self.is_over:
            return False
        try:
            self._cell_for(move)
        except IllegalMoveError:
            return False
        return True

    def legal_moves(self) -> List[int]:
        """All legal moves in ascending order (empty once the game is over)."""
        if self.is_over:
            return []
        if self.config.gravity:
            rows = self.config.rows
            return [c for c, h in enumerate(self._heights) if h < rows]
        return np.flatnonzero(self._cells == EMPTY).tolist()

    def ordered_moves(self) -> List[int]:
        """Legal moves, most central first - the move ordering used by search agents."""
        if self.is_over:
            return []
        if self.config.gravity:
            rows, heights = self.config.rows, self._heights
            return [c for c in self._geometry.move_order if heights[c] < rows]
        cells = self._cells
        return [m for m in self._geometry.move_order if cells[m] == EMPTY]

    def play(self, move) -> "ConnectNGame":
        """Validate and play ``move`` for the current player."""
        if self.is_over:
            raise IllegalMoveError("the game is already over")
        cell = self._cell_for(move)
        player = self.current_player
        cfg = self.config
        self._cells[cell] = player
        if cfg.gravity:
            self._heights[cell % cfg.cols] += 1
        self._history.append(int(move))
        self._cell_history.append(cell)
        line = self._winning_line(cell, player)
        if line:
            self.winner = player
            self.winning_cells = line
        else:
            self.current_player = 3 - player
        return self

    def undo(self) -> int:
        """Take back the last move and return it."""
        if not self._history:
            raise IllegalMoveError("nothing to undo")
        move = self._history.pop()
        cell = self._cell_history.pop()
        player = int(self._cells[cell])
        self._cells[cell] = EMPTY
        if self.config.gravity:
            self._heights[cell % self.config.cols] -= 1
        self.current_player = player
        self.winner = 0
        self.winning_cells = []
        return move

    def undo_to(self, move_count: int) -> None:
        """Undo moves until exactly ``move_count`` moves remain."""
        while len(self._history) > move_count:
            self.undo()

    # --------------------------------------------------------------- win logic
    def _line_through(self, cell: int, player: int, dr: int, dc: int) -> List[int]:
        """Contiguous cells owned by ``player`` through ``cell`` along (dr, dc)."""
        cfg = self.config
        rows, cols, cells = cfg.rows, cfg.cols, self._cells
        r0, c0 = divmod(cell, cols)
        line = [cell]
        r, c = r0 + dr, c0 + dc
        while 0 <= r < rows and 0 <= c < cols and cells[r * cols + c] == player:
            line.append(r * cols + c)
            r, c = r + dr, c + dc
        r, c = r0 - dr, c0 - dc
        while 0 <= r < rows and 0 <= c < cols and cells[r * cols + c] == player:
            line.append(r * cols + c)
            r, c = r - dr, c - dc
        return line

    def _winning_line(self, cell: int, player: int) -> List[Tuple[int, int]]:
        """If ``player`` owns ``cell`` and it completes N-in-a-row, return the line's cells."""
        n, cols = self.config.n, self.config.cols
        for dr, dc in DIRECTIONS:
            line = self._line_through(cell, player, dr, dc)
            if len(line) >= n:
                return sorted(divmod(i, cols) for i in line)
        return []

    def wins_for(self, move, player: int) -> bool:
        """Would ``player`` win by playing ``move`` right now?  (No state is changed.)

        Used for immediate-win and block detection.  Works for either player,
        regardless of whose turn it is.
        """
        if self.is_over or player not in (PLAYER_1, PLAYER_2):
            return False
        try:
            cell = self._cell_for(move)
        except IllegalMoveError:
            return False
        self._cells[cell] = player
        try:
            return bool(self._winning_line(cell, player))
        finally:
            self._cells[cell] = EMPTY

    def winning_moves(self, player: int) -> List[int]:
        """Every legal move that would win immediately for ``player``."""
        return [m for m in self.legal_moves() if self.wins_for(m, player)]

    # ------------------------------------------------------------ presentation
    def to_dict(self) -> Dict:
        return {
            "config": self.config.to_dict(),
            "board": self.board.tolist(),
            "current_player": self.current_player,
            "first_player": self.first_player,
            "legal_moves": self.legal_moves(),
            "moves": self.history,
            "winner": self.winner,
            "is_draw": self.is_draw,
            "is_over": self.is_over,
            "status": self.status,
            "winning_cells": [list(c) for c in self.winning_cells],
            "last_cell": list(self.last_cell) if self.last_cell else None,
        }

    def render(self) -> str:
        symbols = {EMPTY: ".", PLAYER_1: "X", PLAYER_2: "O"}
        return "\n".join(" ".join(symbols[int(v)] for v in row) for row in self.board)

    def __repr__(self) -> str:
        return f"ConnectNGame({self.config}, moves={self._history}, status={self.status})"
