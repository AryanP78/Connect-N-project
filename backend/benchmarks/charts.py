"""Render PNG charts from ``benchmarks.json`` (measured data only).

Colour follows the entity, never its rank: each agent keeps one categorical hue across
every figure.  The hues come from a palette validated for colour-blind separation; three
of the light-mode hues fall below 3:1 contrast on the page, so every mark carries a direct
value label (no information is colour-only).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
AGENT_COLORS = {"random": "#2a78d6", "greedy": "#eb6834", "minimax": "#1baf7a",
                "alphabeta": "#eda100", "mcts": "#e87ba4"}
# Outcomes use the reserved status hues (good / critical) so they never collide with an agent colour.
OUTCOME = {"Wins": "#0ca30c", "Draws": "#c9c8c0", "Losses": "#d03b3b"}


def _kind(label: str) -> str:
    low = label.lower()
    for key, name in (("alpha", "alphabeta"), ("minimax", "minimax"), ("mcts", "mcts"),
                      ("greedy", "greedy"), ("random", "random")):
        if key in low:
            return name
    return "random"


def _style(ax):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=9, length=0)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def _fig(w, h, title, subtitle=None):
    fig = plt.figure(figsize=(w, h), facecolor=SURFACE)
    fig.text(0.012, 0.975, title, ha="left", va="top", fontsize=13, fontweight="bold", color=INK)
    if subtitle:
        fig.text(0.012, 0.925, subtitle, ha="left", va="top", fontsize=9, color=INK2)
    return fig


def _tick(v: float, _pos=None) -> str:
    return f"{v / 1000:g}k" if v >= 1000 else f"{v:g}"


def _fmt(v: float) -> str:
    if v >= 10000:
        return f"{v / 1000:.0f}k"
    if v >= 1000:
        return f"{v / 1000:.1f}k"
    if v >= 100:
        return f"{v:.0f}"
    if v >= 10:
        return f"{v:.1f}"
    if v >= 1:
        return f"{v:.2f}"
    return f"{v:.3f}"


def exp1(data, out: Path):
    rr = data["exp1_round_robin"]
    st = sorted(rr["standings"], key=lambda s: (s["win_rate"], -s["loss_rate"]))
    labels = [s["agent"] for s in st]
    games = st[0]["games"]
    fig = _fig(13, 4.6, "Experiment 1 - Random vs Greedy vs Minimax vs Alpha-Beta",
               f"Round robin on 6x7, N=4. Each agent played {games} games ({rr['games_per_pair']} per opponent), "
               "paired openings, sides swapped.")
    gs = fig.add_gridspec(1, 3, left=0.14, right=0.985, top=0.80, bottom=0.12, wspace=0.55,
                          width_ratios=[1.35, 1, 1])
    ax = fig.add_subplot(gs[0])
    _style(ax)
    left = [0.0] * len(st)
    for name, key in (("Wins", "win_rate"), ("Draws", "draw_rate"), ("Losses", "loss_rate")):
        vals = [s[key] * 100 for s in st]
        ax.barh(labels, vals, left=left, color=OUTCOME[name], edgecolor=SURFACE, linewidth=2,
                height=0.62, label=name)
        for i, v in enumerate(vals):
            if v >= 7:
                ax.text(left[i] + v / 2, i, f"{v:.0f}%", ha="center", va="center", fontsize=9,
                        color=INK if name == "Draws" else "#ffffff", fontweight="bold")
        left = [l + v for l, v in zip(left, vals)]
    ax.set_xlim(0, 100)
    ax.set_xlabel("% of games", color=INK2, fontsize=9)
    ax.set_title("Outcomes", loc="left", fontsize=10, color=INK, fontweight="bold")
    ax.legend(ncol=3, fontsize=8, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.17),
              labelcolor=INK2)
    for idx, (key, title, unit) in enumerate((("avg_time_ms", "Avg decision time", "ms"),
                                              ("avg_nodes", "Avg nodes per decision", ""))):
        ax2 = fig.add_subplot(gs[idx + 1])
        _style(ax2)
        vals = [s[key] for s in st]
        ax2.barh(labels, vals, color=[AGENT_COLORS[_kind(l)] for l in labels], height=0.62)
        ax2.set_xscale("log")
        ax2.set_yticklabels([])
        ax2.set_xlim(min(vals) / 3, max(vals) * 12)
        ax2.minorticks_off()
        for i, v in enumerate(vals):
            ax2.text(v * 1.18, i, f"{_fmt(v)} {unit}".strip(), va="center", fontsize=9, color=INK)
        ax2.set_title(title + " (log)", loc="left", fontsize=10, color=INK, fontweight="bold")
        ax2.xaxis.set_major_formatter(FuncFormatter(_tick))
    fig.savefig(out, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def exp2(data, out: Path):
    e = data["exp2_minimax_depths"]
    st = sorted(e["tournament"]["standings"], key=lambda s: s["configured_depth"])
    prof = e["cost_profile"]
    fig = _fig(13, 4.2, "Experiment 2 - Minimax at different search depths",
               f"Win rate: round robin of depths 1-4 ({e['tournament']['games_per_pair']} games per pairing). "
               f"Cost: {e['sample_positions']} sampled positions.")
    gs = fig.add_gridspec(1, 3, left=0.06, right=0.985, top=0.80, bottom=0.14, wspace=0.28)
    c = AGENT_COLORS["minimax"]
    ax = fig.add_subplot(gs[0])
    _style(ax)
    ax.grid(axis="y", color=GRID)
    ax.grid(axis="x", visible=False)
    xs = [s["configured_depth"] for s in st]
    vals = [s["win_rate"] * 100 for s in st]
    ax.bar(xs, vals, color=c, width=0.6)
    for x, v in zip(xs, vals):
        ax.text(x, v + 1.5, f"{v:.0f}%", ha="center", fontsize=9, color=INK)
    ax.set_xticks(xs)
    ax.set_ylim(0, 105)
    ax.set_xlabel("search depth (plies)", color=INK2, fontsize=9)
    ax.set_title("Win rate vs other depths", loc="left", fontsize=10, color=INK, fontweight="bold")
    for idx, (key, title) in enumerate((("avg_nodes", "Avg nodes per decision (log)"),
                                        ("avg_time_ms", "Avg decision time, ms (log)"))):
        ax2 = fig.add_subplot(gs[idx + 1])
        _style(ax2)
        ax2.grid(axis="y", color=GRID)
        ax2.grid(axis="x", visible=False)
        px = [p["spec"]["depth"] for p in prof]
        py = [p[key] for p in prof]
        ax2.plot(px, py, color=c, linewidth=2, marker="o", markersize=7, markeredgecolor=SURFACE,
                 markeredgewidth=2)
        for x, y in zip(px, py):
            ax2.text(x, y * 1.45, _fmt(y), ha="center", fontsize=9, color=INK)
        ax2.set_yscale("log")
        ax2.minorticks_off()
        ax2.set_ylim(min(py) / 2.5, max(py) * 5)
        ax2.set_xticks(px)
        ax2.set_xlabel("search depth (plies)", color=INK2, fontsize=9)
        ax2.set_title(title, loc="left", fontsize=10, color=INK, fontweight="bold")
        ax2.yaxis.set_major_formatter(FuncFormatter(_tick))
    fig.savefig(out, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def exp3(data, out: Path):
    e = data["exp3_equal_depth"]
    comp = e["comparison"]
    depths = [r["depth"] for r in comp]
    same = min(r["same_move_rate"] for r in comp) * 100
    same_s = min(r["same_score_rate"] for r in comp) * 100
    fig = _fig(13, 4.4, "Experiment 3 - Minimax vs Alpha-Beta at equal depth",
               f"Same heuristic, same move ordering. Identical chosen move in at least {same:.0f}% of "
               f"{comp[0]['positions']} sampled positions (identical value in at least {same_s:.0f}%).")
    gs = fig.add_gridspec(1, 2, left=0.06, right=0.985, top=0.78, bottom=0.17, wspace=0.18,
                          width_ratios=[1.5, 1])
    ax = fig.add_subplot(gs[0])
    _style(ax)
    ax.grid(axis="y", color=GRID)
    ax.grid(axis="x", visible=False)
    w = 0.36
    for off, key, name, color in ((-w / 2, "minimax_avg_nodes", "Minimax", AGENT_COLORS["minimax"]),
                                  (w / 2, "alphabeta_avg_nodes", "Alpha-Beta", AGENT_COLORS["alphabeta"])):
        vals = [r[key] for r in comp]
        ax.bar([d + off for d in depths], vals, width=w - 0.04, color=color, label=name)
        for d, v in zip(depths, vals):
            ax.text(d + off, v * 1.12, _fmt(v), ha="center", fontsize=8.5, color=INK)
    ax.set_yscale("log")
    ax.minorticks_off()
    ax.set_ylim(top=max(r["minimax_avg_nodes"] for r in comp) * 6)
    ax.set_xticks(depths)
    ax.set_xlabel("search depth (plies)", color=INK2, fontsize=9)
    ax.set_title("Avg nodes explored per decision (log)", loc="left", fontsize=10, color=INK, fontweight="bold")
    ax.legend(frameon=False, fontsize=9, loc="upper left", labelcolor=INK2)
    ax.yaxis.set_major_formatter(FuncFormatter(_tick))
    ax2 = fig.add_subplot(gs[1])
    _style(ax2)
    ax2.grid(axis="y", color=GRID)
    ax2.grid(axis="x", visible=False)
    sp = [r["speedup"] for r in comp]
    ax2.bar(depths, sp, width=0.55, color=AGENT_COLORS["alphabeta"])
    for d, r in zip(depths, comp):
        ax2.text(d, r["speedup"] + max(sp) * 0.02, f"{r['speedup']:.1f}x\n(-{r['node_reduction_pct']:.0f}% nodes)",
                 ha="center", fontsize=8.5, color=INK)
    ax2.set_ylim(0, max(sp) * 1.25)
    ax2.set_xticks(depths)
    ax2.set_xlabel("search depth (plies)", color=INK2, fontsize=9)
    ax2.set_title("Wall-clock speed-up of Alpha-Beta", loc="left", fontsize=10, color=INK, fontweight="bold")
    fig.savefig(out, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def exp4(data, out: Path):
    e = data["exp4_mcts"]
    n_games = next(iter(e["opponents"].values()))["results"][0]["games"]
    fig = _fig(13, 4.2, "Experiment 4 - Monte Carlo (MCTS) at different simulation budgets",
               f"Win rate of MCTS against two fixed opponents, {n_games} games each (draws are not wins). "
               "Random rollouts, UCT exploration sqrt(2).")
    gs = fig.add_gridspec(1, 2, left=0.06, right=0.93, top=0.78, bottom=0.17, wspace=0.22, width_ratios=[1.4, 1])
    ax = fig.add_subplot(gs[0])
    _style(ax)
    ax.grid(axis="y", color=GRID)
    ax.grid(axis="x", visible=False)
    colors = {"greedy": AGENT_COLORS["greedy"], "alphabeta_d3": AGENT_COLORS["alphabeta"]}
    series = {k: [r["mcts_win_rate"] * 100 for r in o["results"]] for k, o in e["opponents"].items()}
    for key, opp in e["opponents"].items():
        xs = [r["simulations"] for r in opp["results"]]
        ys = series[key]
        ax.plot(xs, ys, color=colors[key], linewidth=2, marker="o", markersize=7,
                markeredgecolor=SURFACE, markeredgewidth=2)
        others = [v for k, v in series.items() if k != key]
        for i, (x, y) in enumerate(zip(xs, ys)):
            above = all(y >= o[i] for o in others)       # higher series labels above, lower below
            ax.text(x, y + (4.5 if above else -9.5), f"{y:.0f}", ha="center", fontsize=8.5, color=INK)
        ax.text(xs[-1] * 1.14, ys[-1], f"vs {opp['label']}", va="center", fontsize=9, color=INK)
    ax.set_xscale("log")
    ax.set_xticks(e["budgets"])
    ax.get_xaxis().set_major_formatter(FuncFormatter(lambda x, _: f"{x:.0f}"))
    ax.minorticks_off()
    ax.set_xlim(e["budgets"][0] / 1.3, e["budgets"][-1] * 3.3)
    ax.set_ylim(-14, 112)
    ax.set_yticks([0, 20, 40, 60, 80, 100])
    ax.set_xlabel("simulations per move", color=INK2, fontsize=9)
    ax.set_ylabel("MCTS win rate, %", color=INK2, fontsize=9)
    ax.set_title("Strength vs budget", loc="left", fontsize=10, color=INK, fontweight="bold")
    ax2 = fig.add_subplot(gs[1])
    _style(ax2)
    ax2.grid(axis="y", color=GRID)
    ax2.grid(axis="x", visible=False)
    first = next(iter(e["opponents"].values()))["results"]
    xs = list(range(len(first)))
    ts = [r["avg_time_ms"] for r in first]
    ax2.bar(xs, ts, color=AGENT_COLORS["mcts"], width=0.6)
    for x, t in zip(xs, ts):
        ax2.text(x, t + max(ts) * 0.02, _fmt(t), ha="center", fontsize=8.5, color=INK)
    ax2.set_xticks(xs)
    ax2.set_xticklabels([str(r["simulations"]) for r in first])
    ax2.set_ylim(0, max(ts) * 1.15)
    ax2.set_xlabel("simulations per move", color=INK2, fontsize=9)
    ax2.set_title("Avg decision time, ms", loc="left", fontsize=10, color=INK, fontweight="bold")
    fig.savefig(out, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def memory(data, out: Path):
    rows = data["memory"]
    rows = sorted(rows, key=lambda r: r["avg_peak_kb"])
    fig = _fig(8.5, 3.6, "Peak memory per decision",
               "Python-heap peak (tracemalloc) during one move, averaged over sampled positions.")
    ax = fig.add_axes([0.2, 0.14, 0.76, 0.62])
    _style(ax)
    vals = [r["avg_peak_kb"] for r in rows]
    ax.barh([r["agent"] for r in rows], vals, color=[AGENT_COLORS[_kind(r["agent"])] for r in rows], height=0.6)
    for i, v in enumerate(vals):
        ax.text(v + max(vals) * 0.01, i, f"{v:.1f} KB", va="center", fontsize=9, color=INK)
    ax.set_xlim(0, max(vals) * 1.18)
    ax.set_xlabel("KB", color=INK2, fontsize=9)
    fig.savefig(out, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def render_all(results_dir: Path) -> None:
    data = json.loads((Path(results_dir) / "benchmarks.json").read_text())
    for name, fn in (("exp1_round_robin.png", exp1), ("exp2_minimax_depths.png", exp2),
                     ("exp3_equal_depth.png", exp3), ("exp4_mcts.png", exp4), ("memory.png", memory)):
        fn(data, Path(results_dir) / name)
        print("wrote", name)


if __name__ == "__main__":
    import sys
    render_all(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / "docs" / "results")
