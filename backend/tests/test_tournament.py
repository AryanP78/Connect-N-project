"""Complete AI tournaments and the benchmarking framework."""
import random

import pytest

from backend.agents import RandomAgent, create_agent_from_spec
from backend.benchmarks import (
    measure_memory, play_game, random_opening, run_pairing, run_round_robin, spec_label,
)
from backend.engine import ConnectNGame, GameConfig

SPECS = [
    {"kind": "random"},
    {"kind": "greedy"},
    {"kind": "minimax", "depth": 2},
    {"kind": "alphabeta", "depth": 3},
    {"kind": "mcts", "simulations": 60},
]
SMALL = {"rows": 5, "cols": 5, "n": 4, "gravity": True}


def test_play_game_runs_to_completion_with_legal_moves():
    cfg = GameConfig()
    rec = play_game(RandomAgent(1), RandomAgent(2), cfg, a_first=True, record=True)
    replay = ConnectNGame.from_moves(cfg, rec.moves)   # every move validated again on replay
    assert replay.is_over
    assert rec.plies == len(rec.moves) == len(rec.decisions)
    assert (rec.winner_slot is None) == replay.is_draw
    if rec.winner_slot is not None:
        assert rec.winner_slot == (0 if replay.winner == 1 else 1)


def test_a_first_false_swaps_the_tokens():
    rec = play_game(RandomAgent(1), RandomAgent(2), GameConfig(), a_first=False, record=True)
    assert rec.decisions[0]["slot"] == 1  # agent B makes the first move


def test_random_opening_is_legal_and_seeded():
    cfg = GameConfig()
    a = random_opening(cfg, 4, random.Random(5))
    assert a == random_opening(cfg, 4, random.Random(5)) and len(a) == 4
    ConnectNGame.from_moves(cfg, a)


def test_pairing_totals_and_rates_add_up():
    r = run_pairing({"kind": "greedy"}, {"kind": "random"}, games=6, config=SMALL, seed=3)
    assert r["a_wins"] + r["b_wins"] + r["draws"] == 6
    assert r["a_win_rate"] + r["b_win_rate"] + r["draw_rate"] == pytest.approx(1.0)
    assert r["a_stats"]["decisions"] > 0 and r["b_stats"]["decisions"] > 0


def test_pairing_is_reproducible():
    a = run_pairing({"kind": "mcts", "simulations": 30}, {"kind": "greedy"}, games=4, config=SMALL, seed=9, keep_games=True)
    b = run_pairing({"kind": "mcts", "simulations": 30}, {"kind": "greedy"}, games=4, config=SMALL, seed=9, keep_games=True)
    assert [g["moves"] for g in a["game_log"]] == [g["moves"] for g in b["game_log"]]


def test_paired_games_share_openings_and_swap_sides():
    r = run_pairing({"kind": "greedy"}, {"kind": "greedy"}, games=4, config=SMALL, seed=2, keep_games=True)
    log = r["game_log"]
    assert log[0]["opening"] == log[1]["opening"] and log[2]["opening"] == log[3]["opening"]
    assert [g["a_first"] for g in log] == [True, False, True, False]


def test_search_agent_statistics_are_recorded():
    r = run_pairing({"kind": "alphabeta", "depth": 3}, {"kind": "minimax", "depth": 3}, games=2, config=SMALL)
    for key in ("a_stats", "b_stats"):
        s = r[key]
        assert s["avg_nodes"] > 1 and s["configured_depth"] == 3 and s["avg_time_ms"] > 0


def test_full_round_robin_of_all_five_agents():
    result = run_round_robin(SPECS, games_per_pair=2, config=SMALL, seed=1, opening_plies=2, workers=1)
    assert len(result["pairings"]) == 10                # C(5,2)
    assert [s["agent"] for s in result["standings"]] == [spec_label(s) for s in SPECS]
    for s in result["standings"]:
        assert s["games"] == 8                           # 4 opponents x 2 games
        assert s["wins"] + s["losses"] + s["draws"] == s["games"]
        assert s["win_rate"] + s["loss_rate"] + s["draw_rate"] == pytest.approx(1.0)
    # wins of one side are the losses of the other
    assert sum(s["wins"] for s in result["standings"]) == sum(s["losses"] for s in result["standings"])
    names = result["agents"]
    assert all(result["win_matrix"][a][a] is None for a in names)


def test_round_robin_in_parallel_matches_serial():
    serial = run_round_robin(SPECS[:3], games_per_pair=2, config=SMALL, seed=4, workers=1)
    parallel = run_round_robin(SPECS[:3], games_per_pair=2, config=SMALL, seed=4, workers=2)
    pick = lambda r: [(s["agent"], s["wins"], s["losses"], s["draws"]) for s in r["standings"]]
    assert pick(serial) == pick(parallel)


def test_strength_ordering_sanity():
    """Smarter agents must beat the random baseline in a real series."""
    for spec in ({"kind": "greedy"}, {"kind": "alphabeta", "depth": 3}, {"kind": "minimax", "depth": 3}):
        r = run_pairing(spec, {"kind": "random"}, games=10, config=SMALL, seed=11)
        assert r["a_wins"] >= 8, (spec, r["a_wins"])


def test_duplicate_labels_are_rejected():
    with pytest.raises(ValueError):
        run_round_robin([{"kind": "greedy"}, {"kind": "greedy"}], games_per_pair=2)


def test_memory_profile_reports_positive_peaks():
    m = measure_memory({"kind": "alphabeta", "depth": 3}, config=SMALL, plies=(0, 4))
    assert m["positions"] == 2 and m["max_peak_kb"] >= m["avg_peak_kb"] > 0
