"""Run the four required experiments (plus a memory profile) and save the *measured* results.

Usage (from the repository root)::

    python -m backend.benchmarks.run_experiments            # full run (~10-15 minutes)
    python -m backend.benchmarks.run_experiments --quick    # smoke run (~1 minute)

Outputs (in ``docs/results/``): ``benchmarks.json`` (consumed by the dashboard), one CSV per
table, and PNG charts.  Nothing in these files is hand-written - every number comes from
games or searches executed by this script.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import statistics
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

from ..agents import create_agent_from_spec
from ..engine import GameConfig
from .tournament import (
    _pairing_worker, measure_memory, run_round_robin, sample_positions, spec_label,
)

RESULTS_DIR = Path(__file__).resolve().parents[2] / "docs" / "results"
CONFIG = GameConfig().to_dict()          # 6 x 7, N = 4, gravity


# ------------------------------------------------------------ search cost profile
def profile_search(positions, spec: Dict[str, Any]) -> Dict[str, Any]:
    """Run one agent on every sample position and record cost + decision."""
    agent = create_agent_from_spec(spec)
    rows = []
    for pos in positions:
        d = agent.select_move(pos)
        rows.append({"move": d.move, "score": d.score, "nodes": d.nodes,
                     "time_ms": d.time_ms, "max_depth": d.max_depth})
    return {
        "agent": spec_label(spec), "spec": spec, "positions": len(rows),
        "avg_nodes": statistics.fmean(r["nodes"] for r in rows),
        "median_nodes": statistics.median(r["nodes"] for r in rows),
        "avg_time_ms": statistics.fmean(r["time_ms"] for r in rows),
        "median_time_ms": statistics.median(r["time_ms"] for r in rows),
        "avg_depth_reached": statistics.fmean(r["max_depth"] for r in rows),
        "rows": rows,
    }


def build_positions(quick: bool):
    config = GameConfig.from_dict(CONFIG)
    plies = list(range(2, 30, 3 if quick else 2))
    seeds = (0,) if quick else (0, 1, 2)
    positions = []
    for seed in seeds:
        positions.extend(sample_positions(config, plies, seed=seed))
    return positions


def run_pairing_batch(jobs, workers: int):
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(_pairing_worker, jobs))


# ---------------------------------------------------------------------- main
def main(quick: bool = False, workers: int = 2, out_dir: Path = RESULTS_DIR) -> Dict[str, Any]:
    started = time.time()
    out_dir.mkdir(parents=True, exist_ok=True)
    g_main = 8 if quick else 40       # games per pairing, experiment 1
    g_depth = 6 if quick else 30      # experiment 2
    g_eq = 6 if quick else 30         # experiment 3
    g_mcts = 6 if quick else 30       # experiment 4
    seed = 2026
    results: Dict[str, Any] = {}

    def stamp(msg):
        print(f"[{time.time() - started:6.0f}s] {msg}", flush=True)

    # ---- Experiment 1: Random vs Greedy vs Minimax vs Alpha-Beta --------------
    stamp("Experiment 1: Random / Greedy / Minimax / Alpha-Beta round robin")
    exp1_specs = [{"kind": "random"}, {"kind": "greedy"},
                  {"kind": "minimax", "depth": 3}, {"kind": "alphabeta", "depth": 5}]
    results["exp1_round_robin"] = run_round_robin(
        exp1_specs, g_main, CONFIG, seed=seed, opening_plies=4, workers=workers)

    # ---- Experiment 2: Minimax at different depths ----------------------------
    stamp("Experiment 2: Minimax depth 1-4 round robin + cost profile")
    depth_specs = [{"kind": "minimax", "depth": d} for d in (1, 2, 3, 4)]
    exp2_tournament = run_round_robin(depth_specs, g_depth, CONFIG, seed=seed + 1,
                                      opening_plies=4, workers=workers)
    positions = build_positions(quick)
    stamp(f"  cost profile on {len(positions)} sampled positions")
    max_mm = 4 if quick else 5
    exp2_profile = [profile_search(positions, {"kind": "minimax", "depth": d}) for d in range(1, max_mm + 1)]
    results["exp2_minimax_depths"] = {"tournament": exp2_tournament,
                                      "cost_profile": exp2_profile,
                                      "sample_positions": len(positions)}

    # ---- Experiment 3: Minimax vs Alpha-Beta at equal depth -------------------
    stamp("Experiment 3: Minimax vs Alpha-Beta, equal depth")
    eq_depths = (2, 3, 4)
    jobs = [({"kind": "minimax", "depth": d}, {"kind": "alphabeta", "depth": d}, g_eq, CONFIG,
             seed + 2 + d, 4) for d in eq_depths]
    matches = run_pairing_batch(jobs, workers)
    stamp("  equal-depth decision comparison on sampled positions")
    comparison = []
    ab_profiles = {}
    for d in range(1, max_mm + 1):
        mm = exp2_profile[d - 1]
        ab = profile_search(positions, {"kind": "alphabeta", "depth": d})
        ab_profiles[d] = ab
        same_move = sum(a["move"] == b["move"] for a, b in zip(mm["rows"], ab["rows"]))
        same_score = sum(abs(a["score"] - b["score"]) < 1e-6 for a, b in zip(mm["rows"], ab["rows"]))
        comparison.append({
            "depth": d, "positions": len(positions),
            "minimax_avg_nodes": mm["avg_nodes"], "alphabeta_avg_nodes": ab["avg_nodes"],
            "minimax_avg_time_ms": mm["avg_time_ms"], "alphabeta_avg_time_ms": ab["avg_time_ms"],
            "node_reduction_pct": 100.0 * (1 - ab["avg_nodes"] / mm["avg_nodes"]),
            "speedup": mm["avg_time_ms"] / ab["avg_time_ms"],
            "same_move_rate": same_move / len(positions),
            "same_score_rate": same_score / len(positions),
        })
    # Alpha-Beta alone can go deeper for the same budget
    deeper = []
    for d in range(max_mm + 1, (7 if quick else 8)):
        deeper.append(profile_search(positions, {"kind": "alphabeta", "depth": d}))
    results["exp3_equal_depth"] = {
        "matches": matches, "comparison": comparison,
        "alphabeta_deeper_profile": [{k: v for k, v in p.items() if k != "rows"} for p in deeper],
        "alphabeta_profile": [{k: v for k, v in ab_profiles[d].items() if k != "rows"} for d in ab_profiles],
    }
    for p in exp2_profile:
        p.pop("rows", None)

    # ---- Experiment 4: Monte Carlo at different simulation budgets ------------
    stamp("Experiment 4: MCTS simulation budgets")
    budgets = (50, 100, 250, 500) if quick else (50, 100, 250, 500, 1000, 2000)
    opponents = {"greedy": {"kind": "greedy"}, "alphabeta_d3": {"kind": "alphabeta", "depth": 3}}
    jobs, keys = [], []
    for opp_key, opp in opponents.items():
        for n in budgets:
            jobs.append(({"kind": "mcts", "simulations": n}, opp, g_mcts, CONFIG,
                         seed + 100 + n, 4))
            keys.append((opp_key, n))
    mcts_pairings = run_pairing_batch(jobs, workers)
    exp4: Dict[str, Any] = {"budgets": list(budgets), "opponents": {}}
    for (opp_key, n), p in zip(keys, mcts_pairings):
        exp4["opponents"].setdefault(opp_key, {"label": spec_label(opponents[opp_key]), "results": []})
        exp4["opponents"][opp_key]["results"].append({
            "simulations": n, "games": p["games"], "mcts_wins": p["a_wins"],
            "opponent_wins": p["b_wins"], "draws": p["draws"],
            "mcts_win_rate": p["a_win_rate"], "opponent_win_rate": p["b_win_rate"],
            "draw_rate": p["draw_rate"],
            "avg_time_ms": p["a_stats"]["avg_time_ms"], "max_time_ms": p["a_stats"]["max_time_ms"],
        })
    results["exp4_mcts"] = exp4

    # ---- Memory profile --------------------------------------------------------
    stamp("Memory profile (tracemalloc peak per decision)")
    mem_specs = [{"kind": "random"}, {"kind": "greedy"}, {"kind": "minimax", "depth": 4},
                 {"kind": "alphabeta", "depth": 4}, {"kind": "alphabeta", "depth": 6},
                 {"kind": "mcts", "simulations": 1000}]
    results["memory"] = [measure_memory(s, CONFIG, plies=(0, 6, 12, 18, 24), seed=seed) for s in mem_specs]

    results["meta"] = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "quick_run": quick, "config": CONFIG, "seed": seed,
        "python": platform.python_version(), "numpy": np.__version__,
        "machine": platform.machine(), "cpu_count": os.cpu_count(),
        "games_per_pairing": {"exp1": g_main, "exp2": g_depth, "exp3": g_eq, "exp4": g_mcts},
        "opening_plies": 4,
        "sample_positions": len(positions),
        "wall_clock_seconds": round(time.time() - started, 1),
        "notes": [
            "Games are played in pairs sharing a random 4-ply opening with sides swapped.",
            "Decision times are wall-clock per move on the machine above (pure Python + NumPy); "
            "two worker processes ran games in parallel.",
            "Cost profiles use positions reached by random play, not strong play.",
            "'Nodes' = positions visited by the search (for MCTS: simulations).",
        ],
    }
    write_outputs(results, out_dir)
    stamp(f"Done. Results written to {out_dir}")
    return results


# --------------------------------------------------------------------- output
def _csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def write_outputs(results: Dict[str, Any], out_dir: Path) -> None:
    (out_dir / "benchmarks.json").write_text(json.dumps(results, indent=1))
    keep = ("agent", "games", "wins", "losses", "draws", "win_rate", "loss_rate", "draw_rate",
            "avg_time_ms", "avg_nodes", "avg_depth_reached", "configured_depth")
    _csv(out_dir / "exp1_standings.csv",
         [{k: s[k] for k in keep} for s in results["exp1_round_robin"]["standings"]])
    _csv(out_dir / "exp2_depth_standings.csv",
         [{k: s[k] for k in keep} for s in results["exp2_minimax_depths"]["tournament"]["standings"]])
    _csv(out_dir / "exp2_depth_cost.csv",
         [{k: p[k] for k in ("agent", "positions", "avg_nodes", "median_nodes", "avg_time_ms", "median_time_ms",
                             "avg_depth_reached")} for p in results["exp2_minimax_depths"]["cost_profile"]])
    _csv(out_dir / "exp3_equal_depth.csv", results["exp3_equal_depth"]["comparison"])
    rows = []
    for opp in results["exp4_mcts"]["opponents"].values():
        for r in opp["results"]:
            rows.append({"opponent": opp["label"], **r})
    _csv(out_dir / "exp4_mcts.csv", rows)
    _csv(out_dir / "memory.csv", results["memory"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true", help="small smoke run")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--out", type=Path, default=RESULTS_DIR)
    args = parser.parse_args()
    main(quick=args.quick, workers=args.workers, out_dir=args.out)
    from .charts import render_all
    render_all(args.out)
