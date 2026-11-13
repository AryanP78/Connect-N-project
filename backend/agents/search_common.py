"""Shared pieces of the Minimax and Alpha-Beta agents."""
from __future__ import annotations

from typing import Dict, List

from ..evaluation import WIN_SCORE

# Scores closer to +-WIN_SCORE than this are forced wins/losses (WIN_SCORE - ply).
FORCED_THRESHOLD = WIN_SCORE - 10_000
TIE_TOLERANCE = 1e-6


def explain_search(kind: str, depth: int, nodes: int, move: int, score: float,
                   move_scores: Dict[int, float], max_depth: int, exact_scores: bool) -> str:
    """Plain-language explanation of a Minimax/Alpha-Beta decision."""
    if score >= FORCED_THRESHOLD:
        plies = int(round(WIN_SCORE - score))
        verdict = f"found a forced win within {plies} plies"
    elif score <= -FORCED_THRESHOLD:
        plies = int(round(WIN_SCORE + score))
        verdict = f"every line loses (the opponent can force a win in {plies} plies); playing the move that delays it longest"
    else:
        verdict = f"best heuristic value after looking {depth} plies ahead is {score:.1f}"
    others = sorted(((m, s) for m, s in move_scores.items() if m != move), key=lambda t: -t[1])[:2]
    rel = "" if not others else (
        " Next best: " + ", ".join(
            f"{m} ({'<=' if not exact_scores else ''}{s:.1f})" for m, s in others) + ".")
    return (f"{kind} searched {nodes:,} positions to depth {depth} (deepest line reached {max_depth}); "
            f"{verdict}, so move {move}.{rel}")
