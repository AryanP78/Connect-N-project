"""Heuristic evaluation: terminal override, bounds, sensible ordering, configurable weights."""
import numpy as np

from backend.engine import ConnectNGame, GameConfig
from backend.evaluation import (
    MAX_HEURISTIC, WIN_SCORE, Evaluator, HeuristicWeights, evaluate, get_evaluator,
)
from .conftest import random_position


def test_empty_board_is_neutral():
    assert evaluate(ConnectNGame(), 1) == 0.0


def test_terminal_win_and_loss_override_heuristic():
    g = ConnectNGame.from_moves(None, [0, 1, 0, 1, 0, 1, 0])
    assert evaluate(g, 1) == WIN_SCORE
    assert evaluate(g, 2) == -WIN_SCORE


def test_draw_scores_zero():
    cfg = GameConfig(3, 3, 3, gravity=False)
    g = ConnectNGame.from_moves(cfg, [0, 1, 2, 4, 3, 5, 7, 6, 8])
    assert evaluate(g, 1) == 0.0 and evaluate(g, 2) == 0.0


def test_heuristic_never_reaches_terminal_scores():
    for seed in range(40):
        g = random_position(GameConfig(), plies=seed % 30, seed=seed)
        for p in (1, 2):
            assert abs(evaluate(g, p)) <= MAX_HEURISTIC < WIN_SCORE


def test_centre_column_preferred_over_edge():
    centre = ConnectNGame.from_moves(None, [3])
    edge = ConnectNGame.from_moves(None, [0])
    assert evaluate(centre, 1) > evaluate(edge, 1)


def test_more_consecutive_tokens_score_higher():
    two = ConnectNGame.from_moves(None, [2, 6, 3, 6])      # P1 has 2 adjacent (opp tokens far away)
    three = ConnectNGame.from_moves(None, [2, 6, 3, 6, 4, 5])  # P1 has 3 adjacent
    assert evaluate(three, 1) > evaluate(two, 1)


def test_blocked_window_is_not_counted():
    open_two = ConnectNGame.from_moves(None, [2, 6, 3, 6])
    # same stones but the right side is capped by an opponent token in the window
    capped = ConnectNGame.from_moves(None, [2, 1, 3, 4])
    b_open = get_evaluator(open_two.config).breakdown(open_two.cells, 1)["own_windows_by_tokens"][2]
    b_capped = get_evaluator(capped.config).breakdown(capped.cells, 1)["own_windows_by_tokens"][2]
    assert b_open > b_capped


def test_immediate_threat_is_counted_and_rewarded():
    g = ConnectNGame.from_moves(None, [0, 6, 1, 6, 2, 5])  # P1 threatens column 3 right now
    b = get_evaluator(g.config).breakdown(g.cells, 1)
    assert b["own_immediate_threats"] == 1
    assert b["components"]["immediate_threats"] > 0
    assert get_evaluator(g.config).breakdown(g.cells, 2)["opponent_immediate_threats"] == 1


def test_threat_above_an_empty_cell_is_not_immediate_under_gravity():
    # P1 holds (row4, cols 0-2); the completing cell (row4, col3) sits above the empty (row5, col3).
    g = ConnectNGame.from_moves(None, [6, 0, 0, 1, 1, 2, 2])
    b = get_evaluator(g.config).breakdown(g.cells, 1)
    assert b["own_windows_by_tokens"][3] >= 1      # the 3-window exists ...
    assert b["own_immediate_threats"] == 0         # ... but cannot be played yet
    assert b["opponent_immediate_threats"] == 1    # while P2's bottom-row three can (column 3)


def test_free_placement_threat_is_always_immediate():
    cfg = GameConfig(6, 7, 4, gravity=False)
    g = ConnectNGame.from_moves(cfg, [4 * 7 + 0, 0, 4 * 7 + 1, 1, 4 * 7 + 2, 2])
    assert get_evaluator(g.config).breakdown(g.cells, 1)["own_immediate_threats"] >= 1


def test_weights_are_configurable():
    g = ConnectNGame.from_moves(None, [3, 2])
    base = evaluate(g, 1)
    no_centre = evaluate(g, 1, HeuristicWeights(center=0.0))
    big_centre = evaluate(g, 1, HeuristicWeights(center=30.0))
    assert no_centre != base != big_centre
    assert big_centre > base  # P1 sits in the centre, P2 does not


def test_vectorised_matches_breakdown_total():
    ev = Evaluator(GameConfig())
    for seed in range(25):
        g = random_position(GameConfig(), 12, seed)
        for p in (1, 2):
            assert abs(ev.evaluate_cells(g.cells, p) - ev.breakdown(g.cells, p)["total"]) < 1e-9


def test_works_on_other_board_sizes_and_n():
    for cfg in (GameConfig(5, 5, 4), GameConfig(4, 4, 3), GameConfig(8, 8, 5), GameConfig(4, 6, 4, gravity=False)):
        g = random_position(cfg, 6, 1)
        assert np.isfinite(evaluate(g, g.current_player))
