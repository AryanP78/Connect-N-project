import itertools
import random

import pytest

from backend.engine import ConnectNGame, GameConfig


@pytest.fixture
def default_game():
    return ConnectNGame()


def random_position(config: GameConfig, plies: int, seed: int) -> ConnectNGame:
    """A non-terminal position reached by random play (may be shorter if the game ends)."""
    rng = random.Random(seed)
    game = ConnectNGame(config)
    for _ in range(plies):
        moves = game.legal_moves()
        if not moves:
            break
        # avoid ending the game so agents always have a move to make
        safe = []
        for m in moves:
            game.play(m)
            if not game.is_over:
                safe.append(m)
            game.undo()
        if not safe:
            break
        game.play(rng.choice(safe))
    return game


def find_drawn_sequence(config: GameConfig):
    """Depth-first search for a move sequence that fills the board without a winner."""
    game = ConnectNGame(config)

    def dfs():
        if game.is_over:
            return game.is_draw
        for m in game.legal_moves():
            game.play(m)
            if dfs():
                return True
            game.undo()
        return False

    assert dfs()
    return game.history
