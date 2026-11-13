"""Agent 5 - Monte Carlo Tree Search (UCT with random rollouts)."""
from __future__ import annotations

import math
import random
from typing import Dict, List, Optional

from ..engine import ConnectNGame
from .base import Agent, Decision


class _Node:
    __slots__ = ("move", "parent", "children", "untried", "visits", "wins", "mover")

    def __init__(self, move: Optional[int], parent: Optional["_Node"], mover: int, untried: List[int]):
        self.move = move
        self.parent = parent
        self.children: List["_Node"] = []
        self.untried = untried
        self.visits = 0
        self.wins = 0.0      # from the point of view of ``mover`` (the player who played ``move``)
        self.mover = mover


class MCTSAgent(Agent):
    """UCT Monte Carlo Tree Search with uniformly random rollouts.

    Each of the ``simulations`` iterations runs the four classic phases:
    selection (UCB1), expansion, a random playout to the end of the game, and
    back-propagation of the result.  The move with the most visits is played; each root
    move's estimated win probability (``wins / visits``) is reported as its score.

    ``nodes`` in the returned :class:`Decision` is the number of simulations; the number of
    random playout plies is available in ``extra["rollout_plies"]``.
    """

    kind = "mcts"

    def __init__(self, simulations: int = 500, exploration: float = math.sqrt(2),
                 seed: Optional[int] = None, name: Optional[str] = None):
        if simulations < 1:
            raise ValueError("simulations must be at least 1")
        super().__init__(name or f"MCTS (n={simulations})")
        self.simulations = simulations
        self.exploration = exploration
        self.seed = seed
        self._rng = random.Random(seed)

    def _select_child(self, node: _Node) -> _Node:
        log_parent = math.log(node.visits)
        c = self.exploration
        best, best_value = None, -1.0
        for child in node.children:
            value = child.wins / child.visits + c * math.sqrt(log_parent / child.visits)
            if value > best_value:
                best, best_value = child, value
        return best  # type: ignore[return-value]

    def _decide(self, game: ConnectNGame) -> Decision:
        rng = self._rng
        root_mover = 3 - game.current_player
        root = _Node(None, None, root_mover, game.legal_moves())
        base_moves = game.move_count
        rollout_plies = 0
        max_depth = 0

        for _ in range(self.simulations):
            node = root
            # 1. selection
            while not node.untried and node.children and not game.is_over:
                node = self._select_child(node)
                game.play(node.move)
            # 2. expansion
            if node.untried and not game.is_over:
                move = node.untried.pop(rng.randrange(len(node.untried)))
                mover = game.current_player
                game.play(move)
                child = _Node(move, node, mover, game.legal_moves())
                node.children.append(child)
                node = child
            depth = game.move_count - base_moves
            if depth > max_depth:
                max_depth = depth
            # 3. rollout
            while not game.is_over:
                game.play(rng.choice(game.legal_moves()))
                rollout_plies += 1
            winner = game.winner
            # 4. back-propagation
            while node is not None:
                node.visits += 1
                if winner == 0:
                    node.wins += 0.5
                elif winner == node.mover:
                    node.wins += 1.0
                node = node.parent
            game.undo_to(base_moves)

        best = max(root.children, key=lambda ch: (ch.visits, ch.wins / ch.visits))
        scores: Dict[int, float] = {ch.move: ch.wins / ch.visits for ch in root.children}
        visits = {str(ch.move): ch.visits for ch in root.children}
        win_prob = scores[best.move]
        return Decision(
            move=best.move, nodes=self.simulations, depth=0, max_depth=max_depth,
            score=win_prob, move_scores=scores,
            explanation=(f"Ran {self.simulations:,} random playouts. Move {best.move} was visited most "
                         f"({best.visits:,} times) with an estimated win probability of {win_prob:.0%}."),
            extra={"visits": visits, "rollout_plies": rollout_plies, "scores_are_win_probabilities": True},
        )

    def describe(self):
        return {"kind": self.kind, "name": self.name, "simulations": self.simulations, "seed": self.seed}
