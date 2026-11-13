"""Agent 2 - Greedy (one-ply tactical + pattern agent)."""
from __future__ import annotations

import random
from typing import Optional

from ..engine import ConnectNGame
from ..evaluation import WIN_SCORE, HeuristicWeights, get_evaluator
from .base import Agent, Decision

UNSAFE_PENALTY = 500_000.0


class GreedyAgent(Agent):
    """Priorities, in order:

    1. play an immediate winning move;
    2. block the opponent's immediate winning move;
    3. otherwise score every move by the heuristic of the resulting position (consecutive
       token patterns, open windows, centre preference) and play the best one, avoiding
       moves that hand the opponent an immediate win.

    Ties are broken uniformly at random (seeded) so games vary.
    """

    kind = "greedy"

    def __init__(self, seed: Optional[int] = None, weights: Optional[HeuristicWeights] = None,
                 name: Optional[str] = None):
        super().__init__(name or "Greedy")
        self.seed = seed
        self.weights = weights
        self._rng = random.Random(seed)

    def _decide(self, game: ConnectNGame) -> Decision:
        me = game.current_player
        opp = 3 - me
        moves = game.ordered_moves()
        evaluated = 0

        for move in moves:
            evaluated += 1
            if game.wins_for(move, me):
                return Decision(
                    move=move, nodes=evaluated, score=WIN_SCORE,
                    explanation=f"Immediate win: move {move} completes {game.config.n} in a row.",
                )

        for move in moves:
            evaluated += 1
            if game.wins_for(move, opp):
                return Decision(
                    move=move, nodes=evaluated,
                    explanation=f"Forced block: the opponent would win with move {move}, so I take it.",
                )

        evaluator = get_evaluator(game.config, self.weights)
        scores = {}
        unsafe = set()
        for move in moves:
            game.play(move)
            evaluated += 1
            score = evaluator.evaluate_cells(game.cells, me)
            # does this move let the opponent win straight away?
            for reply in game.legal_moves():
                evaluated += 1
                if game.wins_for(reply, opp):
                    score -= UNSAFE_PENALTY
                    unsafe.add(move)
                    break
            game.undo()
            scores[move] = score

        best = max(scores.values())
        candidates = [m for m in moves if scores[m] == best]
        move = self._rng.choice(candidates)
        if move in unsafe:
            why = "every move loses to an immediate reply; picking the least bad one"
        else:
            why = (f"best heuristic value {scores[move]:.1f} among {len(moves)} moves "
                   "(open windows + threats + centre preference), and it leaves no immediate loss")
        return Decision(
            move=move, nodes=evaluated, score=scores[move], move_scores=scores,
            explanation=f"No win or block available; {why}.",
            extra={"unsafe_moves": sorted(unsafe)},
        )

    def describe(self):
        return {"kind": self.kind, "name": self.name, "seed": self.seed}
