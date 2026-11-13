"""Agent 1 - Random baseline."""
from __future__ import annotations

import random
from typing import Optional

from ..engine import ConnectNGame
from .base import Agent, Decision


class RandomAgent(Agent):
    kind = "random"

    def __init__(self, seed: Optional[int] = None, name: Optional[str] = None):
        super().__init__(name or "Random")
        self.seed = seed
        self._rng = random.Random(seed)

    def _decide(self, game: ConnectNGame) -> Decision:
        moves = game.legal_moves()
        move = self._rng.choice(moves)
        return Decision(
            move=move,
            nodes=1,
            explanation=f"Picked move {move} uniformly at random from {len(moves)} legal moves (baseline agent).",
        )

    def describe(self):
        return {"kind": self.kind, "name": self.name, "seed": self.seed}
