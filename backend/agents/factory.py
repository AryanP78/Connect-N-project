"""Agent registry: build agents from plain dictionaries (used by the API and benchmarks)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..evaluation import HeuristicWeights
from .alphabeta_agent import AlphaBetaAgent
from .base import Agent
from .greedy_agent import GreedyAgent
from .mcts_agent import MCTSAgent
from .minimax_agent import MinimaxAgent
from .random_agent import RandomAgent

AGENT_KINDS = ("random", "greedy", "minimax", "alphabeta", "mcts")

AGENT_CATALOG: List[Dict[str, Any]] = [
    {"kind": "random", "label": "Random", "params": [],
     "description": "Uniformly random legal moves - the baseline."},
    {"kind": "greedy", "label": "Greedy", "params": [],
     "description": "Wins or blocks immediately, otherwise maximises a one-move heuristic."},
    {"kind": "minimax", "label": "Minimax", "params": [{"name": "depth", "min": 1, "max": 5, "default": 3}],
     "description": "Depth-limited adversarial search with heuristic evaluation."},
    {"kind": "alphabeta", "label": "Alpha-Beta", "params": [{"name": "depth", "min": 1, "max": 7, "default": 5}],
     "description": "Minimax with alpha-beta pruning - same decisions, far fewer nodes."},
    {"kind": "mcts", "label": "Monte Carlo (MCTS)",
     "params": [{"name": "simulations", "min": 10, "max": 5000, "default": 500}],
     "description": "UCT tree search with random rollouts; estimates win probabilities."},
]

# Human-vs-AI difficulty levels
DIFFICULTY_PRESETS: Dict[str, Dict[str, Any]] = {
    "easy": {"kind": "random"},
    "medium": {"kind": "greedy"},
    "hard": {"kind": "alphabeta", "depth": 4},
    "expert": {"kind": "alphabeta", "depth": 6},
}


def create_agent(kind: str, depth: Optional[int] = None, simulations: Optional[int] = None,
                 seed: Optional[int] = None, weights: Optional[HeuristicWeights] = None,
                 randomize_ties: bool = False, name: Optional[str] = None) -> Agent:
    kind = kind.lower()
    if kind == "random":
        return RandomAgent(seed=seed, name=name)
    if kind == "greedy":
        return GreedyAgent(seed=seed, weights=weights, name=name)
    if kind == "minimax":
        return MinimaxAgent(depth=depth or 3, weights=weights, seed=seed,
                            randomize_ties=randomize_ties, name=name)
    if kind in ("alphabeta", "alpha-beta", "alpha_beta"):
        return AlphaBetaAgent(depth=depth or 4, weights=weights, seed=seed,
                              randomize_ties=randomize_ties, name=name)
    if kind in ("mcts", "montecarlo", "monte_carlo"):
        return MCTSAgent(simulations=simulations or 500, seed=seed, name=name)
    raise ValueError(f"unknown agent kind {kind!r}; choose one of {AGENT_KINDS}")


def create_agent_from_spec(spec: Dict[str, Any]) -> Agent:
    """Build an agent from ``{"kind": ..., "depth": ..., "simulations": ..., "seed": ...}``."""
    spec = dict(spec)
    kind = spec.pop("kind")
    return create_agent(
        kind, depth=spec.get("depth"), simulations=spec.get("simulations"), seed=spec.get("seed"),
        randomize_ties=bool(spec.get("randomize_ties", False)), name=spec.get("name"),
    )


def agent_from_difficulty(level: str, seed: Optional[int] = None) -> Agent:
    try:
        preset = DIFFICULTY_PRESETS[level.lower()]
    except KeyError:
        raise ValueError(f"unknown difficulty {level!r}; choose one of {list(DIFFICULTY_PRESETS)}")
    return create_agent(preset["kind"], depth=preset.get("depth"), seed=seed)
