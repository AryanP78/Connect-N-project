"""Automated match / tournament framework.

Fairness measures
-----------------
* Games come in **pairs** that share the same random opening but swap which agent plays
  first, so first-move advantage and opening luck cancel out.
* Agents are rebuilt for every game from a spec dictionary with a deterministic seed,
  making every experiment reproducible.
* Every decision is recorded (time, nodes, depth) so the dashboard is computed from what
  actually happened - nothing is estimated.
"""
from __future__ import annotations

import itertools
import random
import tracemalloc
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from ..agents import Agent, create_agent_from_spec
from ..engine import ConnectNGame, GameConfig

Spec = Dict[str, Any]


def spec_label(spec: Spec) -> str:
    """Human readable label for an agent spec."""
    if spec.get("name"):
        return spec["name"]
    kind = spec["kind"]
    if kind == "random":
        return "Random"
    if kind == "greedy":
        return "Greedy"
    if kind == "minimax":
        return f"Minimax (d={spec.get('depth', 3)})"
    if kind == "alphabeta":
        return f"Alpha-Beta (d={spec.get('depth', 4)})"
    if kind == "mcts":
        return f"MCTS (n={spec.get('simulations', 500)})"
    return kind


@dataclass
class AgentStats:
    """Running totals of one agent's decisions."""

    decisions: int = 0
    time_ms: float = 0.0
    nodes: int = 0
    max_depth: int = 0           # sum of deepest ply reached per decision
    configured_depth: int = 0
    max_time_ms: float = 0.0

    def add(self, decision) -> None:
        self.decisions += 1
        self.time_ms += decision.time_ms
        self.nodes += decision.nodes
        self.max_depth += decision.max_depth
        self.configured_depth = max(self.configured_depth, decision.depth)
        self.max_time_ms = max(self.max_time_ms, decision.time_ms)

    def merge(self, other: "AgentStats") -> None:
        self.decisions += other.decisions
        self.time_ms += other.time_ms
        self.nodes += other.nodes
        self.max_depth += other.max_depth
        self.configured_depth = max(self.configured_depth, other.configured_depth)
        self.max_time_ms = max(self.max_time_ms, other.max_time_ms)

    def summary(self) -> Dict[str, float]:
        d = max(self.decisions, 1)
        return {
            "decisions": self.decisions,
            "avg_time_ms": self.time_ms / d,
            "max_time_ms": self.max_time_ms,
            "avg_nodes": self.nodes / d,
            "total_nodes": self.nodes,
            "avg_depth_reached": self.max_depth / d,
            "configured_depth": self.configured_depth,
        }


@dataclass
class GameRecord:
    moves: List[int]
    winner_slot: Optional[int]      # 0 -> agent A, 1 -> agent B, None -> draw
    a_first: bool
    plies: int
    opening: List[int]
    stats: List[AgentStats] = field(default_factory=lambda: [AgentStats(), AgentStats()])
    decisions: List[Dict[str, Any]] = field(default_factory=list)  # only when recording


def random_opening(config: GameConfig, plies: int, rng: random.Random) -> List[int]:
    """``plies`` random legal moves that do not end the game."""
    game = ConnectNGame(config)
    opening: List[int] = []
    for _ in range(plies):
        candidates = []
        for move in game.legal_moves():
            game.play(move)
            ended = game.is_over
            game.undo()
            if not ended:
                candidates.append(move)
        if not candidates:
            break
        move = rng.choice(candidates)
        game.play(move)
        opening.append(move)
    return opening


def play_game(agent_a: Agent, agent_b: Agent, config: GameConfig, a_first: bool = True,
              opening: Optional[Sequence[int]] = None, record: bool = False) -> GameRecord:
    """Play one full game.  Agent A plays token 1 iff ``a_first``."""
    game = ConnectNGame(config)
    for move in opening or ():
        game.play(move)
    slot_by_token = {1: 0, 2: 1} if a_first else {1: 1, 2: 0}
    agents = (agent_a, agent_b)
    stats = [AgentStats(), AgentStats()]
    decisions: List[Dict[str, Any]] = []
    while not game.is_over:
        slot = slot_by_token[game.current_player]
        decision = agents[slot].select_move(game)
        stats[slot].add(decision)
        if record:
            decisions.append({"ply": game.move_count, "slot": slot, **decision.to_dict()})
        game.play(decision.move)
    winner_slot = slot_by_token[game.winner] if game.winner else None
    return GameRecord(game.history, winner_slot, a_first, game.move_count,
                      list(opening or ()), stats, decisions)


def run_pairing(spec_a: Spec, spec_b: Spec, games: int = 20, config: Optional[Dict] = None,
                seed: int = 0, opening_plies: int = 4, keep_games: bool = False) -> Dict[str, Any]:
    """Play ``games`` games between two agent specs and aggregate the results.

    ``games`` should be even so that both agents get the first move equally often.
    """
    cfg = GameConfig.from_dict(config or {})
    wins = [0, 0]
    draws = 0
    first_move_wins = {"first": 0, "second": 0}
    totals = [AgentStats(), AgentStats()]
    plies_total = 0
    game_log: List[Dict[str, Any]] = []
    for g in range(games):
        pair_index = g // 2
        opening = random_opening(cfg, opening_plies, random.Random(seed * 100_003 + pair_index))
        a = create_agent_from_spec({**spec_a, "seed": seed * 7919 + g * 2})
        b = create_agent_from_spec({**spec_b, "seed": seed * 7919 + g * 2 + 1})
        record = play_game(a, b, cfg, a_first=(g % 2 == 0), opening=opening)
        totals[0].merge(record.stats[0])
        totals[1].merge(record.stats[1])
        plies_total += record.plies
        if record.winner_slot is None:
            draws += 1
        else:
            wins[record.winner_slot] += 1
            token = 1 if (record.winner_slot == 0) == record.a_first else 2
            first_player_token = 1  # token 1 always moves first from the empty board
            first_move_wins["first" if token == first_player_token else "second"] += 1
        if keep_games:
            game_log.append({"moves": record.moves, "winner_slot": record.winner_slot,
                             "a_first": record.a_first, "opening": record.opening})
    n = max(games, 1)
    result = {
        "agent_a": spec_label(spec_a), "agent_b": spec_label(spec_b),
        "spec_a": spec_a, "spec_b": spec_b,
        "config": cfg.to_dict(), "games": games, "opening_plies": opening_plies, "seed": seed,
        "a_wins": wins[0], "b_wins": wins[1], "draws": draws,
        "a_win_rate": wins[0] / n, "b_win_rate": wins[1] / n, "draw_rate": draws / n,
        "avg_game_length": plies_total / n,
        "first_player_wins": first_move_wins,
        "a_stats": totals[0].summary(), "b_stats": totals[1].summary(),
    }
    if keep_games:
        result["game_log"] = game_log
    return result


def _pairing_worker(args) -> Dict[str, Any]:
    spec_a, spec_b, games, config, seed, opening_plies = args
    return run_pairing(spec_a, spec_b, games, config, seed, opening_plies)


def run_round_robin(specs: Sequence[Spec], games_per_pair: int = 20, config: Optional[Dict] = None,
                    seed: int = 0, opening_plies: int = 4, workers: int = 1) -> Dict[str, Any]:
    """Every agent plays every other agent ``games_per_pair`` times."""
    labels = [spec_label(s) for s in specs]
    if len(set(labels)) != len(labels):
        raise ValueError("agent labels must be unique within a tournament")
    jobs = [(specs[i], specs[j], games_per_pair, config, seed + 17 * (i * len(specs) + j), opening_plies)
            for i, j in itertools.combinations(range(len(specs)), 2)]
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            pairings = list(pool.map(_pairing_worker, jobs))
    else:
        pairings = [_pairing_worker(job) for job in jobs]

    # per-agent aggregate across all of its games
    table: Dict[str, Dict[str, Any]] = {
        label: {"agent": label, "spec": spec, "games": 0, "wins": 0, "losses": 0, "draws": 0,
                "_stats": AgentStats()}
        for label, spec in zip(labels, specs)
    }
    matrix: Dict[str, Dict[str, Optional[float]]] = {a: {b: None for b in labels} for a in labels}
    for p in pairings:
        a, b = p["agent_a"], p["agent_b"]
        for me, you, w, l in ((a, b, p["a_wins"], p["b_wins"]), (b, a, p["b_wins"], p["a_wins"])):
            row = table[me]
            row["games"] += p["games"]
            row["wins"] += w
            row["losses"] += l
            row["draws"] += p["draws"]
            matrix[me][you] = w / max(p["games"], 1)
        for label, key in ((a, "a_stats"), (b, "b_stats")):
            s = p[key]
            agg: AgentStats = table[label]["_stats"]
            agg.decisions += int(s["decisions"])
            agg.time_ms += s["avg_time_ms"] * s["decisions"]
            agg.nodes += int(s["total_nodes"])
            agg.max_depth += s["avg_depth_reached"] * s["decisions"]
            agg.configured_depth = max(agg.configured_depth, int(s["configured_depth"]))
            agg.max_time_ms = max(agg.max_time_ms, s["max_time_ms"])
    standings = []
    for label in labels:
        row = table[label]
        n = max(row["games"], 1)
        stats = row.pop("_stats").summary()
        row.update({
            "win_rate": row["wins"] / n, "loss_rate": row["losses"] / n, "draw_rate": row["draws"] / n,
            **stats,
        })
        standings.append(row)
    return {"config": GameConfig.from_dict(config or {}).to_dict(), "games_per_pair": games_per_pair,
            "opening_plies": opening_plies, "seed": seed, "agents": labels,
            "standings": standings, "win_matrix": matrix, "pairings": pairings}


# ----------------------------------------------------------------- memory profile
def sample_positions(config: GameConfig, plies: Sequence[int], seed: int = 0) -> List[ConnectNGame]:
    """Random (non-terminal) positions reached after the given number of plies."""
    rng = random.Random(seed)
    positions = []
    for target in plies:
        game = ConnectNGame(config)
        while game.move_count < target and not game.is_over:
            game.play(rng.choice(game.legal_moves()))
        if not game.is_over:
            positions.append(game)
    return positions


def measure_memory(spec: Spec, config: Optional[Dict] = None, plies: Sequence[int] = (0, 6, 12, 18),
                   seed: int = 0) -> Dict[str, Any]:
    """Peak Python-heap allocation (via tracemalloc) of one decision, over sample positions."""
    cfg = GameConfig.from_dict(config or {})
    positions = sample_positions(cfg, plies, seed)
    peaks: List[float] = []
    for i, position in enumerate(positions):
        agent = create_agent_from_spec({**spec, "seed": seed + i})
        tracemalloc.start()
        tracemalloc.reset_peak()
        base, _ = tracemalloc.get_traced_memory()
        agent.select_move(position)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        peaks.append((peak - base) / 1024.0)
    return {"agent": spec_label(spec), "positions": len(peaks),
            "avg_peak_kb": sum(peaks) / max(len(peaks), 1), "max_peak_kb": max(peaks) if peaks else 0.0}
