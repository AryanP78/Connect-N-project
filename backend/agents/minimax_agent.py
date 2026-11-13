"""Agent 3 - depth-limited Minimax."""
from __future__ import annotations

import random
from typing import Dict, List, Optional

from ..engine import ConnectNGame
from ..evaluation import WIN_SCORE, Evaluator, HeuristicWeights, get_evaluator
from .base import Agent, Decision
from .search_common import TIE_TOLERANCE, explain_search


class MinimaxAgent(Agent):
    """Plain depth-limited Minimax (no pruning).

    Values are always expressed from the point of view of the player to move at the
    root (``me``).  A win found at ply ``p`` scores ``WIN_SCORE - p`` (sooner is better);
    a loss scores ``-(WIN_SCORE - p)`` (later is better).  At the depth limit the shared
    heuristic evaluation is used.
    """

    kind = "minimax"

    def __init__(self, depth: int = 4, weights: Optional[HeuristicWeights] = None,
                 seed: Optional[int] = None, randomize_ties: bool = False,
                 name: Optional[str] = None):
        if depth < 1:
            raise ValueError("depth must be at least 1")
        super().__init__(name or f"Minimax (d={depth})")
        self.depth = depth
        self.weights = weights
        self.seed = seed
        self.randomize_ties = randomize_ties
        self._rng = random.Random(seed)
        self._nodes = 0
        self._max_ply = 0

    # ---------------------------------------------------------------- search
    def _search(self, game: ConnectNGame, depth: int, ply: int, me: int, ev: Evaluator) -> float:
        self._nodes += 1
        if ply > self._max_ply:
            self._max_ply = ply
        if game.winner:
            return (WIN_SCORE - ply) if game.winner == me else -(WIN_SCORE - ply)
        if game.is_draw:
            return 0.0
        if depth == 0:
            return ev.evaluate_cells(game.cells, me)

        if game.current_player == me:
            best = -float("inf")
            for move in game.ordered_moves():
                game.play(move)
                value = self._search(game, depth - 1, ply + 1, me, ev)
                game.undo()
                if value > best:
                    best = value
            return best
        best = float("inf")
        for move in game.ordered_moves():
            game.play(move)
            value = self._search(game, depth - 1, ply + 1, me, ev)
            game.undo()
            if value < best:
                best = value
        return best

    def _decide(self, game: ConnectNGame) -> Decision:
        me = game.current_player
        ev = get_evaluator(game.config, self.weights)
        self._nodes, self._max_ply = 0, 0
        best_value = -float("inf")
        best_moves: List[int] = []
        scores: Dict[int, float] = {}
        for move in game.ordered_moves():
            game.play(move)
            value = self._search(game, self.depth - 1, 1, me, ev)
            game.undo()
            scores[move] = value
            if value > best_value + TIE_TOLERANCE:
                best_value, best_moves = value, [move]
            elif self.randomize_ties and value >= best_value - TIE_TOLERANCE:
                best_moves.append(move)
        move = self._rng.choice(best_moves) if self.randomize_ties else best_moves[0]
        return Decision(
            move=move, nodes=self._nodes, depth=self.depth, max_depth=self._max_ply,
            score=scores[move], move_scores=scores,
            explanation=explain_search("Minimax", self.depth, self._nodes, move, scores[move],
                                       scores, self._max_ply, exact_scores=True),
            extra={"scores_are_exact": True},
        )

    def describe(self):
        return {"kind": self.kind, "name": self.name, "depth": self.depth, "seed": self.seed}
