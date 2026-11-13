"""Agent legality, tactics, Minimax correctness and Alpha-Beta equivalence."""
import pytest

from backend.agents import (
    AgentError, AlphaBetaAgent, GreedyAgent, MCTSAgent, MinimaxAgent, RandomAgent,
    agent_from_difficulty, create_agent,
)
from backend.engine import ConnectNGame, GameConfig
from backend.evaluation import WIN_SCORE, get_evaluator
from .conftest import random_position

ALL_AGENTS = [
    lambda s: RandomAgent(seed=s),
    lambda s: GreedyAgent(seed=s),
    lambda s: MinimaxAgent(depth=2, seed=s),
    lambda s: AlphaBetaAgent(depth=3, seed=s),
    lambda s: MCTSAgent(simulations=60, seed=s),
]
CONFIGS = [GameConfig(), GameConfig(5, 5, 4), GameConfig(4, 4, 3), GameConfig(4, 5, 3, gravity=False)]


# ------------------------------------------------------------------ legality
@pytest.mark.parametrize("make", ALL_AGENTS)
@pytest.mark.parametrize("config", CONFIGS, ids=lambda c: f"{c.rows}x{c.cols}n{c.n}{'g' if c.gravity else 'f'}")
def test_every_agent_returns_legal_moves_in_many_positions(make, config):
    for seed in range(6):
        game = random_position(config, plies=seed * 2, seed=seed)
        if game.is_over:
            continue
        agent = make(seed)
        decision = agent.select_move(game)
        assert game.is_legal(decision.move)
        assert decision.time_ms >= 0 and decision.nodes >= 1
        assert decision.agent == agent.name


def test_select_move_never_mutates_the_callers_game():
    game = random_position(GameConfig(), 8, 3)
    before = (game.board.copy(), game.current_player, game.history)
    for make in ALL_AGENTS:
        make(1).select_move(game)
    assert (game.board == before[0]).all() and game.current_player == before[1] and game.history == before[2]


def test_agents_refuse_finished_games():
    game = ConnectNGame.from_moves(None, [0, 1, 0, 1, 0, 1, 0])
    for make in ALL_AGENTS:
        with pytest.raises(AgentError):
            make(0).select_move(game)


def test_agent_only_move_when_one_column_left():
    cfg = GameConfig(2, 2, 2)
    game = ConnectNGame(cfg)
    game.play(0)
    game.play(0)
    for make in ALL_AGENTS:
        assert make(0).choose_move(game) == 1


# ------------------------------------------------------ immediate win / block
def p1_can_win_now():
    return ConnectNGame.from_moves(None, [0, 6, 1, 6, 2, 5])   # P1 to move, wins at column 3


def p1_must_block():
    return ConnectNGame.from_moves(None, [6, 0, 6, 1, 5, 2])   # P1 to move, P2 threatens column 3


@pytest.mark.parametrize("make", [
    lambda s: GreedyAgent(seed=s),
    lambda s: MinimaxAgent(depth=2),
    lambda s: AlphaBetaAgent(depth=2),
    lambda s: AlphaBetaAgent(depth=4),
])
def test_agents_take_an_immediate_win(make):
    game = p1_can_win_now()
    assert game.current_player == 1 and game.wins_for(3, 1)
    assert make(0).choose_move(game) == 3


@pytest.mark.parametrize("make", [
    lambda s: GreedyAgent(seed=s),
    lambda s: MinimaxAgent(depth=2),
    lambda s: AlphaBetaAgent(depth=2),
    lambda s: AlphaBetaAgent(depth=4),
])
def test_agents_block_an_immediate_loss(make):
    game = p1_must_block()
    assert game.current_player == 1 and game.wins_for(3, 2) and not game.wins_for(3, 1)
    assert make(0).choose_move(game) == 3


def both_sides_can_win():
    # P1 owns the bottom row 0-1-2 (wins at column 3); P2 owns three stacked tokens in column 6.
    return ConnectNGame.from_moves(None, [0, 6, 1, 6, 2, 6])


def test_winning_is_preferred_over_blocking():
    game = both_sides_can_win()
    assert game.current_player == 1 and game.wins_for(3, 1) and game.wins_for(6, 2)
    assert GreedyAgent(0).choose_move(game) == 3
    assert MinimaxAgent(depth=3).choose_move(game) == 3
    assert AlphaBetaAgent(depth=3).choose_move(game) == 3


def test_greedy_explanations_mention_the_reason():
    assert "win" in GreedyAgent(0).select_move(p1_can_win_now()).explanation.lower()
    assert "block" in GreedyAgent(0).select_move(p1_must_block()).explanation.lower()


def test_greedy_avoids_moves_that_hand_the_opponent_an_immediate_win():
    # n=3. P1 owns (bottom,c0), (row4,c1), (bottom,c2).  If P2 plays on top of column 2 the cell
    # (row3,c2) completes P1's rising diagonal; if P2 plays on top of column 0, (row3,c0)
    # completes the falling diagonal.  Columns 0 and 2 are therefore poisoned for P2.
    game = ConnectNGame.from_moves(GameConfig(6, 7, 3), [0, 1, 1, 3, 2])  # P2 to move
    assert game.current_player == 2
    assert game.winning_moves(1) == [] and game.winning_moves(2) == []   # no win/block shortcut
    for poisoned in (0, 2):
        child = game.copy().play(poisoned)
        assert child.winning_moves(1) == [poisoned]
    decision = GreedyAgent(0).select_move(game)
    assert decision.extra["unsafe_moves"] == [0, 2]
    assert decision.move not in (0, 2)


# ---------------------------------------------------------- Minimax correctness
def reference_minimax(game: ConnectNGame, depth: int, me: int, ev, ply: int = 0) -> float:
    """Independent, copy-based minimax used as an oracle (no undo, no ordering tricks)."""
    if game.winner:
        return (WIN_SCORE - ply) if game.winner == me else -(WIN_SCORE - ply)
    if game.is_draw:
        return 0.0
    if depth == 0:
        return ev.evaluate_cells(game.cells, me)
    values = []
    for move in game.legal_moves():
        child = game.copy()
        child.play(move)
        values.append(reference_minimax(child, depth - 1, me, ev, ply + 1))
    return max(values) if game.current_player == me else min(values)


@pytest.mark.parametrize("config", [GameConfig(4, 4, 3), GameConfig(5, 5, 4), GameConfig(3, 4, 3, gravity=False)],
                         ids=["4x4n3", "5x5n4", "3x4n3free"])
@pytest.mark.parametrize("depth", [1, 2, 3])
def test_minimax_values_match_independent_reference(config, depth):
    for seed in range(4):
        game = random_position(config, plies=2 + seed, seed=seed)
        if game.is_over:
            continue
        me = game.current_player
        ev = get_evaluator(config)
        decision = MinimaxAgent(depth=depth).select_move(game)
        for move, value in decision.move_scores.items():
            child = game.copy()
            child.play(move)
            assert value == pytest.approx(reference_minimax(child, depth - 1, me, ev, 1))
        assert decision.score == pytest.approx(max(decision.move_scores.values()))


def test_minimax_finds_forced_win_in_three_plies():
    game = ConnectNGame.from_moves(None, [3, 3, 2, 2])  # P1 plays 1 or 4 -> open three, unstoppable
    d3 = MinimaxAgent(depth=3).select_move(game)
    assert d3.move in (1, 4)
    assert d3.score == WIN_SCORE - 3
    d2 = MinimaxAgent(depth=2).select_move(game)
    assert d2.score < WIN_SCORE - 100  # not visible at depth 2


def test_minimax_sees_a_forced_loss_and_still_returns_a_legal_move():
    # P2 to move with an unstoppable open three against it
    game = ConnectNGame.from_moves(None, [3, 3, 2, 2, 4])
    d = MinimaxAgent(depth=3).select_move(game)
    assert game.is_legal(d.move)
    assert d.score <= -(WIN_SCORE - 10)
    assert "loses" in d.explanation or "lose" in d.explanation


def test_minimax_prefers_faster_wins():
    game = p1_can_win_now()
    d = MinimaxAgent(depth=4).select_move(game)
    assert d.move == 3 and d.score == WIN_SCORE - 1


def test_depth_is_configurable_and_reported():
    game = ConnectNGame()
    for depth in (1, 2, 3):
        d = MinimaxAgent(depth=depth).select_move(game)
        assert d.depth == depth and d.max_depth == depth
    with pytest.raises(ValueError):
        MinimaxAgent(depth=0)


# ------------------------------------------------- Alpha-Beta == Minimax (equal depth)
EQUIVALENCE_CASES = [
    (cfg, depth)
    for cfg in (GameConfig(), GameConfig(5, 5, 4), GameConfig(4, 4, 3), GameConfig(4, 5, 3, gravity=False))
    for depth in ((1, 2, 3, 4) if cfg.gravity else (1, 2, 3))   # plain minimax is too slow on free boards at d=4
]


@pytest.mark.parametrize("config,depth", EQUIVALENCE_CASES,
                         ids=[f"{c.rows}x{c.cols}n{c.n}{'g' if c.gravity else 'f'}-d{d}" for c, d in EQUIVALENCE_CASES])
def test_alpha_beta_matches_minimax_exactly(config, depth):
    for seed in range(5):
        game = random_position(config, plies=seed * 3, seed=seed)
        if game.is_over:
            continue
        mm = MinimaxAgent(depth=depth).select_move(game)
        ab = AlphaBetaAgent(depth=depth).select_move(game)
        assert ab.move == mm.move
        assert ab.score == pytest.approx(mm.score)
        assert ab.nodes <= mm.nodes
        # scores for non-chosen moves are upper bounds on the true minimax value
        for move, bound in ab.move_scores.items():
            assert bound >= mm.move_scores[move] - 1e-9 or move == ab.move


def test_alpha_beta_prunes_substantially_at_depth_5():
    game = random_position(GameConfig(), 8, 11)
    mm = MinimaxAgent(depth=5).select_move(game)
    ab = AlphaBetaAgent(depth=5).select_move(game)
    assert ab.move == mm.move
    assert ab.nodes < mm.nodes / 3


def test_alpha_beta_random_tie_break_stays_within_best_moves():
    game = ConnectNGame()
    best = MinimaxAgent(depth=3).select_move(game)
    top = {m for m, v in best.move_scores.items() if abs(v - best.score) < 1e-6}
    seen = set()
    for seed in range(12):
        d = AlphaBetaAgent(depth=3, seed=seed, randomize_ties=True).select_move(game)
        assert d.move in top
        seen.add(d.move)
    assert seen <= top


# ----------------------------------------------------------------------- MCTS
def test_mcts_reports_win_probabilities_and_takes_obvious_win():
    d = MCTSAgent(simulations=400, seed=1).select_move(p1_can_win_now())
    assert d.move == 3
    assert all(0.0 <= v <= 1.0 for v in d.move_scores.values())
    assert d.nodes == 400 and d.extra["rollout_plies"] >= 0


def test_mcts_more_simulations_do_not_break_legality():
    game = random_position(GameConfig(), 10, 5)
    for sims in (1, 10, 200):
        d = MCTSAgent(simulations=sims, seed=0).select_move(game)
        assert game.is_legal(d.move)


def test_mcts_is_reproducible_with_a_seed():
    game = random_position(GameConfig(), 6, 2)
    a = MCTSAgent(simulations=100, seed=42).select_move(game)
    b = MCTSAgent(simulations=100, seed=42).select_move(game)
    assert a.move == b.move and a.move_scores == b.move_scores


# --------------------------------------------------------------------- factory
def test_factory_and_difficulty_presets():
    assert create_agent("random").kind == "random"
    assert create_agent("alphabeta", depth=3).depth == 3
    assert create_agent("mcts", simulations=77).simulations == 77
    with pytest.raises(ValueError):
        create_agent("nonsense")
    kinds = [agent_from_difficulty(level).kind for level in ("easy", "medium", "hard", "expert")]
    assert kinds == ["random", "greedy", "alphabeta", "alphabeta"]
    with pytest.raises(ValueError):
        agent_from_difficulty("impossible")
