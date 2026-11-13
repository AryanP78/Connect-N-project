"""Board initialisation, move validation, gravity, win detection (all directions), draws."""
import numpy as np
import pytest

from backend.engine import ConnectNGame, GameConfig, IllegalMoveError
from .conftest import find_drawn_sequence


# ---------------------------------------------------------------- configuration
def test_default_configuration_is_6x7_connect4_with_gravity():
    cfg = GameConfig()
    assert (cfg.rows, cfg.cols, cfg.n, cfg.gravity) == (6, 7, 4, True)


@pytest.mark.parametrize("kwargs", [
    dict(rows=0), dict(cols=0), dict(n=1), dict(rows=3, cols=3, n=4), dict(rows=99),
    dict(rows="6"), dict(n=True),
])
def test_invalid_configurations_are_rejected(kwargs):
    with pytest.raises(ValueError):
        GameConfig(**kwargs)


# --------------------------------------------------------------- initialisation
def test_board_initialisation():
    g = ConnectNGame()
    assert g.board.shape == (6, 7)
    assert not g.board.any()
    assert g.current_player == 1
    assert g.winner == 0 and not g.is_draw and not g.is_over
    assert g.legal_moves() == list(range(7))
    assert g.status == "in_progress"


def test_custom_board_size_and_first_player():
    g = ConnectNGame(GameConfig(rows=5, cols=9, n=5), first_player=2)
    assert g.board.shape == (5, 9)
    assert g.current_player == 2


# ----------------------------------------------------------- legal / illegal moves
def test_turns_alternate():
    g = ConnectNGame()
    g.play(0)
    assert g.current_player == 2
    g.play(1)
    assert g.current_player == 1
    assert g.board[5, 0] == 1 and g.board[5, 1] == 2


@pytest.mark.parametrize("bad", [-1, 7, 100, 1.5, "3", None, True])
def test_illegal_moves_are_rejected_and_do_not_change_state(bad):
    g = ConnectNGame()
    g.play(3)
    before = g.board.copy()
    with pytest.raises(IllegalMoveError):
        g.play(bad)
    assert (g.board == before).all()
    assert g.current_player == 2 and g.move_count == 1
    assert not g.is_legal(bad)


def test_full_column_is_illegal():
    g = ConnectNGame()
    for _ in range(6):
        g.play(0)  # alternating players -> no four in a column
        if g.is_over:
            break
    assert 0 not in g.legal_moves()
    assert not g.is_legal(0)
    with pytest.raises(IllegalMoveError):
        g.play(0)


def test_no_moves_after_game_over():
    g = ConnectNGame.from_moves(None, [0, 1, 0, 1, 0, 1, 0])
    assert g.winner == 1 and g.is_over
    assert g.legal_moves() == [] and not g.is_legal(3)
    with pytest.raises(IllegalMoveError):
        g.play(3)


def test_numpy_integers_are_accepted():
    g = ConnectNGame()
    g.play(np.int64(3))
    assert g.board[5, 3] == 1


# --------------------------------------------------------------------- gravity
def test_gravity_stacks_tokens_from_the_bottom():
    g = ConnectNGame()
    g.play(2); g.play(2); g.play(2)
    assert list(g.board[:, 2]) == [0, 0, 0, 1, 2, 1]


def test_free_placement_mode_allows_any_empty_cell():
    g = ConnectNGame(GameConfig(5, 5, 4, gravity=False))
    assert len(g.legal_moves()) == 25
    g.play(12)  # centre cell, nothing underneath
    assert g.board[2, 2] == 1
    assert 12 not in g.legal_moves() and len(g.legal_moves()) == 24
    with pytest.raises(IllegalMoveError):
        g.play(12)


# ------------------------------------------------------------ undo / copy / replay
def test_undo_restores_exact_previous_state():
    g = ConnectNGame()
    snapshots = []
    for m in [3, 3, 2, 4, 1, 1]:
        snapshots.append((g.board.copy(), g.current_player, g.legal_moves()))
        g.play(m)
    for board, player, legal in reversed(snapshots):
        g.undo()
        assert (g.board == board).all() and g.current_player == player and g.legal_moves() == legal


def test_undo_of_winning_move_clears_winner():
    g = ConnectNGame.from_moves(None, [0, 1, 0, 1, 0, 1, 0])
    g.undo()
    assert g.winner == 0 and g.winning_cells == [] and not g.is_over
    assert g.current_player == 1


def test_copy_is_independent():
    g = ConnectNGame()
    g.play(3)
    c = g.copy()
    c.play(4)
    assert g.move_count == 1 and c.move_count == 2
    assert (g.board != c.board).any()


def test_from_moves_validates_every_move():
    with pytest.raises(IllegalMoveError):
        ConnectNGame.from_moves(None, [0, 0, 0, 0, 0, 0, 0])  # 7th move into a full column


# ----------------------------------------------------------- winning directions
def test_horizontal_win():
    g = ConnectNGame.from_moves(None, [0, 0, 1, 1, 2, 2, 3])
    assert g.winner == 1
    assert g.winning_cells == [(5, 0), (5, 1), (5, 2), (5, 3)]


def test_vertical_win():
    g = ConnectNGame.from_moves(None, [0, 1, 0, 1, 0, 1, 0])
    assert g.winner == 1
    assert g.winning_cells == [(2, 0), (3, 0), (4, 0), (5, 0)]


def test_diagonal_rising_win():
    g = ConnectNGame.from_moves(None, [0, 1, 1, 2, 3, 2, 2, 3, 6, 3, 3])
    assert g.winner == 1
    assert g.winning_cells == [(2, 3), (3, 2), (4, 1), (5, 0)]


def test_diagonal_falling_win():
    g = ConnectNGame.from_moves(None, [6, 5, 5, 4, 3, 4, 4, 3, 0, 3, 3])
    assert g.winner == 1
    assert g.winning_cells == [(2, 3), (3, 4), (4, 5), (5, 6)]


def test_player_two_can_win():
    g = ConnectNGame.from_moves(None, [0, 1, 0, 1, 0, 1, 6, 1])
    assert g.winner == 2 and g.status == "player_2_wins"


@pytest.mark.parametrize("direction", [(0, 1), (1, 0), (1, 1), (1, -1)])
@pytest.mark.parametrize("n", [3, 4, 5])
def test_all_directions_in_free_placement_for_various_n(direction, n):
    dr, dc = direction
    cfg = GameConfig(rows=7, cols=7, n=n, gravity=False)
    start_r, start_c = (0, 0) if dc >= 0 else (0, 6)
    line = [(start_r + dr * i) * 7 + (start_c + dc * i) for i in range(n)]
    # player 2 wastes moves in a far-away row where it can never line up n tokens
    far = [6 * 7 + c for c in range(7) if (6 * 7 + c) not in line]
    g = ConnectNGame(cfg)
    for i, cell in enumerate(line):
        g.play(cell)
        if i < n - 1:
            assert g.winner == 0
            g.play(far[i * 2 % len(far)] if far[i * 2 % len(far)] not in g.history else
                   next(f for f in far if f not in g.history))
    assert g.winner == 1


def test_win_requires_exactly_configured_n():
    g = ConnectNGame(GameConfig(6, 7, n=3))
    for m in [0, 0, 1, 1]:
        g.play(m)
    assert g.winner == 0
    g.play(2)
    assert g.winner == 1  # three in a row is enough when n=3


def test_win_in_the_middle_of_a_longer_line_is_detected():
    # fill bottom row so that the last stone joins two groups: X X . X X -> X X X X X
    g = ConnectNGame.from_moves(GameConfig(6, 7, n=4), [0, 0, 1, 1, 3, 3, 4, 4])
    assert g.winner == 0
    g.play(2)
    assert g.winner == 1 and len(g.winning_cells) == 5


# ------------------------------------------------------------------------ draw
def test_draw_detection_free_placement_3x3():
    cfg = GameConfig(3, 3, 3, gravity=False)
    g = ConnectNGame.from_moves(cfg, [0, 1, 2, 4, 3, 5, 7, 6, 8])
    assert g.winner == 0 and g.is_draw and g.is_over and g.status == "draw"
    assert g.legal_moves() == []


def test_draw_detection_gravity():
    cfg = GameConfig(3, 3, 3, gravity=True)
    g = ConnectNGame.from_moves(cfg, find_drawn_sequence(cfg))
    assert g.is_draw and g.winner == 0 and g.move_count == 9


def test_no_draw_before_board_is_full():
    g = ConnectNGame()
    g.play(0)
    assert not g.is_draw


# ------------------------------------------------------------- win / block checks
def test_wins_for_detects_immediate_wins_without_changing_state():
    g = ConnectNGame.from_moves(None, [0, 6, 1, 6, 2])  # P1 threatens column 3 (and nothing else)
    before = g.board.copy()
    assert g.wins_for(3, 1)
    assert not g.wins_for(4, 1)
    assert g.winning_moves(1) == [3]
    assert (g.board == before).all() and g.current_player == 2


def test_wins_for_works_for_the_opponent():
    g = ConnectNGame.from_moves(None, [0, 6, 1, 6, 2, 5])  # P1 to move; P2 has 2 in col 6 + 5
    assert g.wins_for(3, 1)
    assert g.winning_moves(2) == []
    g2 = ConnectNGame.from_moves(None, [0, 3, 1, 4, 6, 5])  # P2 threatens column 2 and 6
    assert 2 in g2.winning_moves(2)
