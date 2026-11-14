"""Common agent interface.

Every agent implements :meth:`Agent._decide`.  The public entry point is
:meth:`Agent.select_move`, which

1. refuses to act on a finished game,
2. hands the agent a *copy* of the game (so the caller's game is never mutated),
3. times the decision, and
4. verifies that the returned move is legal before returning it.

The result is a :class:`Decision` carrying the move plus the statistics used by the
benchmarking framework and returned by the API.
"""
from __future__ import annotations

import math
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from ..engine import ConnectNGame


class AgentError(RuntimeError):
    """Raised when an agent returns an illegal move or is asked to play a finished game."""


def _finite(value: Optional[float]) -> Optional[float]:
    """JSON cannot carry inf/nan; map them to None and round the rest."""
    if value is None or not math.isfinite(float(value)):
        return None
    return round(float(value), 4)


@dataclass
class Decision:
    move: int
    agent: str = ""
    time_ms: float = 0.0
    nodes: int = 0                  # positions evaluated/visited during the decision
    depth: int = 0                  # configured search depth (0 for non-search agents)
    max_depth: int = 0              # deepest ply actually reached
    score: Optional[float] = None   # agent's own value of the chosen move
    move_scores: Dict[int, float] = field(default_factory=dict)  # per-move value
    explanation: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "move": self.move,
            "agent": self.agent,
            "time_ms": round(self.time_ms, 3),
            "nodes": self.nodes,
            "depth": self.depth,
            "max_depth": self.max_depth,
            "score": _finite(self.score),
            "move_scores": {str(k): _finite(v) for k, v in self.move_scores.items()},
            "explanation": self.explanation,
            "extra": self.extra,
        }


class Agent(ABC):
    """Abstract game-playing agent."""

    kind: str = "agent"

    def __init__(self, name: Optional[str] = None):
        self.name = name or self.kind

    @abstractmethod
    def _decide(self, game: ConnectNGame) -> Decision:
        """Pick a move for ``game.current_player``.  ``game`` is a private copy."""

    def select_move(self, game: ConnectNGame) -> Decision:
        if game.is_over:
            raise AgentError("cannot select a move: the game is already over")
        working_copy = game.copy()
        start = time.perf_counter()
        decision = self._decide(working_copy)
        decision.time_ms = (time.perf_counter() - start) * 1000.0
        decision.agent = self.name
        if not game.is_legal(decision.move):
            raise AgentError(f"{self.name} returned illegal move {decision.move!r}")
        return decision

    def choose_move(self, game: ConnectNGame) -> int:
        """Shorthand returning only the chosen move."""
        return self.select_move(game).move

    def describe(self) -> Dict[str, Any]:
        return {"kind": self.kind, "name": self.name}

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.name}>"
