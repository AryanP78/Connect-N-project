"""Render the measured benchmark results as Markdown tables.

Writes ``docs/benchmarks.md`` and refreshes the block between the
``<!-- BENCH:START -->`` / ``<!-- BENCH:END -->`` markers in ``README.md``.  All numbers are
read from ``docs/results/benchmarks.json``; nothing is typed by hand.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def fmt(v: float) -> str:
    if v >= 1000:
        return f"{v:,.0f}"
    if v >= 100:
        return f"{v:.0f}"
    if v >= 10:
        return f"{v:.1f}"
    return f"{v:.2f}"


def table(headers, rows) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def build(data) -> str:
    m = data["meta"]
    g = m["games_per_pairing"]
    parts = []
    parts.append(
        f"_Measured on {m['machine']} with {m['cpu_count']} CPU cores, Python {m['python']}, NumPy {m['numpy']}; "
        f"full run took {m['wall_clock_seconds']} s (generated {m['generated_at']}). "
        f"Board: {m['config']['rows']}x{m['config']['cols']}, connect {m['config']['n']}, gravity. "
        f"Games per pairing: {g['exp1']}/{g['exp2']}/{g['exp3']}/{g['exp4']} (experiments 1-4); "
        f"every pair of games shares a random {m['opening_plies']}-ply opening with sides swapped._"
    )

    e1 = data["exp1_round_robin"]
    rows = [[s["agent"], s["games"], s["wins"], s["losses"], s["draws"], f"{s['win_rate'] * 100:.1f}%",
             fmt(s["avg_time_ms"]), fmt(s["avg_nodes"]),
             f"{s['configured_depth']} / {s['avg_depth_reached']:.1f}" if s["configured_depth"] else "-"]
            for s in sorted(e1["standings"], key=lambda s: -s["win_rate"])]
    parts.append("#### Experiment 1 - Random vs Greedy vs Minimax vs Alpha-Beta (round robin)\n\n"
                 + table(["Agent", "Games", "Wins", "Losses", "Draws", "Win rate", "Avg time (ms)",
                          "Avg nodes", "Depth set / reached"], rows)
                 + "\n\n![Experiment 1](docs/results/exp1_round_robin.png)")

    e2 = data["exp2_minimax_depths"]
    wins = {s["configured_depth"]: s for s in e2["tournament"]["standings"]}
    rows = []
    for p in e2["cost_profile"]:
        d = p["spec"]["depth"]
        s = wins.get(d)
        rows.append([d, f"{s['win_rate'] * 100:.1f}% ({s['wins']}-{s['losses']}-{s['draws']})" if s else "n/a (cost only)",
                     fmt(p["avg_nodes"]), fmt(p["avg_time_ms"])])
    parts.append("#### Experiment 2 - Minimax at different search depths\n\n"
                 f"Win rate: round robin of depths 1-4 ({e2['tournament']['games_per_pair']} games per pairing, "
                 f"W-L-D in brackets). Cost: mean over {e2['sample_positions']} sampled positions.\n\n"
                 + table(["Depth", "Win rate vs other depths", "Avg nodes / decision", "Avg time (ms)"], rows)
                 + "\n\n![Experiment 2](docs/results/exp2_minimax_depths.png)")

    e3 = data["exp3_equal_depth"]
    rows = [[c["depth"], fmt(c["minimax_avg_nodes"]), fmt(c["alphabeta_avg_nodes"]), f"{c['node_reduction_pct']:.1f}%",
             fmt(c["minimax_avg_time_ms"]), fmt(c["alphabeta_avg_time_ms"]), f"{c['speedup']:.1f}x",
             f"{c['same_move_rate'] * 100:.0f}% / {c['same_score_rate'] * 100:.0f}%"] for c in e3["comparison"]]
    deeper = ", ".join(f"depth {p['spec']['depth']}: {fmt(p['avg_nodes'])} nodes, {fmt(p['avg_time_ms'])} ms"
                       for p in e3["alphabeta_deeper_profile"])
    matches = ", ".join(f"depth {m_['spec_a']['depth']}: {m_['a_wins']}-{m_['b_wins']}-{m_['draws']}"
                        for m_ in e3["matches"])
    parts.append("#### Experiment 3 - Minimax vs Alpha-Beta at equal depth\n\n"
                 + table(["Depth", "Minimax nodes", "Alpha-Beta nodes", "Node reduction", "Minimax ms",
                          "Alpha-Beta ms", "Speed-up", "Same move / same value"], rows)
                 + f"\n\nHead-to-head games (Minimax-AlphaBeta-draws): {matches}. Because both agents make identical "
                   f"decisions, side-swapped game pairs split evenly - this is evidence of equivalence, not strength. "
                   f"Alpha-Beta alone at greater depth: {deeper}.\n\n![Experiment 3](docs/results/exp3_equal_depth.png)")

    e4 = data["exp4_mcts"]
    rows = []
    for key, opp in e4["opponents"].items():
        for r in opp["results"]:
            rows.append([opp["label"], r["simulations"], f"{r['mcts_wins']}-{r['opponent_wins']}-{r['draws']}",
                         f"{r['mcts_win_rate'] * 100:.0f}%", fmt(r["avg_time_ms"])])
    parts.append("#### Experiment 4 - Monte Carlo at different simulation budgets\n\n"
                 + table(["Opponent", "Simulations", "MCTS W-L-D", "MCTS win rate", "Avg time (ms)"], rows)
                 + "\n\n![Experiment 4](docs/results/exp4_mcts.png)")

    rows = [[r["agent"], f"{r['avg_peak_kb']:.1f}", f"{r['max_peak_kb']:.1f}", r["positions"]] for r in data["memory"]]
    parts.append("#### Memory (peak Python-heap allocation per decision, tracemalloc)\n\n"
                 + table(["Agent", "Avg peak (KB)", "Max peak (KB)", "Positions"], rows))
    return "\n\n".join(parts)


def main() -> None:
    data = json.loads((ROOT / "docs" / "results" / "benchmarks.json").read_text())
    md = build(data)
    (ROOT / "docs" / "benchmarks.md").write_text(
        "# Benchmark results\n\nGenerated by `python -m backend.benchmarks.report` from "
        "`docs/results/benchmarks.json`. Raw CSV files and charts are in `docs/results/`.\n\n"
        + md.replace("docs/results/", "results/") + "\n")
    readme = ROOT / "README.md"
    if readme.exists():
        text = readme.read_text()
        new = re.sub(r"<!-- BENCH:START -->.*<!-- BENCH:END -->",
                     lambda _m: f"<!-- BENCH:START -->\n{md}\n<!-- BENCH:END -->", text, flags=re.S)
        readme.write_text(new)
    print("wrote docs/benchmarks.md and refreshed README block")


if __name__ == "__main__":
    main()
