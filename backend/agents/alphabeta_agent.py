"""Agent 4 - Minimax with Alpha-Beta pruning."""
from __future__ import annotations

import random
from typing import Dict, List, Optional

from ..engine import ConnectNGame
from ..evaluation import WIN_SCORE, Evaluator, HeuristicWeights, get_evaluator
from .base import Agent, Decision
from .search_common import TIE_TOLERANCE, explain_search


class AlphaBetaAgent(Agent):
    """Depth-limited Minimax with alpha-beta pruning (fail-soft).

    It uses exactly the same heuristic, terminal scoring and move ordering as
    :class:`MinimaxAgent`, so at equal depth it chooses the *same move* with the *same
    value* while exploring (far) fewer nodes.  The values reported for non-chosen moves are
    upper bounds rather than exact values (that is what pruning buys).
    """

    kind = "alphabeta"

    def __init__(self, depth: int = 4, weights: Optional[HeuristicWeights] = None,
                 seed: Optional[int] = None, randomize_ties: bool = False,
                 name: Optional[str] = None):
        if depth < 1:
            raise ValueError("depth must be at least 1")
        super().__init__(name or f"Alpha-Beta (d={depth})")
        self.depth = depth
        self.weights = weights
        self.seed = seed
        self.randomize_ties = randomize_ties
        self._rng = random.Random(seed)
        self._nodes = 0
        self._max_ply = 0
        self._cutoffs = 0

    def _search(self, game: ConnectNGame, depth: int, ply: int, alpha: float, beta: float,
                me: int, ev: Evaluator) -> float:
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
            value = -float("inf")
            for move in game.ordered_moves():
                game.play(move)
                child = self._search(game, depth - 1, ply + 1, alpha, beta, me, ev)
                game.undo()
                if child > value:
                    value = child
                if value > alpha:
                    alpha = value
                if alpha >= beta:
                    self._cutoffs += 1
                    break
            return value
        value = float("inf")
        for move in game.ordered_moves():
            game.play(move)
            child = self._search(game, depth - 1, ply + 1, alpha, beta, me, ev)
            game.undo()
            if child < value:
                value = child
            if value < beta:
                beta = value
            if alpha >= beta:
                self._cutoffs += 1
                break
        return value

    def _decide(self, game: ConnectNGame) -> Decision:
        me = game.current_player
        ev = get_evaluator(game.config, self.weights)
        self._nodes, self._max_ply, self._cutoffs = 0, 0, 0
        best_value = -float("inf")
        best_moves: List[int] = []
        scores: Dict[int, float] = {}
        # With random tie-breaking the root window is widened slightly so tied moves return
        # their exact value instead of being cut off as "not better".
        slack = TIE_TOLERANCE if self.randomize_ties else 0.0
        for move in game.ordered_moves():
            alpha = best_value - slack
            game.play(move)
            value = self._search(game, self.depth - 1, 1, alpha, float("inf"), me, ev)
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
            explanation=explain_search("Alpha-Beta", self.depth, self._nodes, move, scores[move],
                                       scores, self._max_ply, exact_scores=False)
            + f" Pruning cut {self._cutoffs:,} branches.",
            extra={"scores_are_exact": False, "cutoffs": self._cutoffs},
        )

    def describe(self):
        return {"kind": self.kind, "name": self.name, "depth": self.depth, "seed": self.seed}
