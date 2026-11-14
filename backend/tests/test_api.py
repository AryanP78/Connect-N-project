"""HTTP API: stateless game flow, validation, AI moves and arena series."""
import pytest
from fastapi.testclient import TestClient

from backend.api.main import app

client = TestClient(app)
CFG = {"rows": 6, "cols": 7, "n": 4, "gravity": True}


def test_health_and_catalog():
    assert client.get("/api/health").json() == {"status": "ok"}
    data = client.get("/api/agents").json()
    assert {a["kind"] for a in data["agents"]} == {"random", "greedy", "minimax", "alphabeta", "mcts"}
    assert set(data["difficulties"]) == {"easy", "medium", "hard", "expert"}


def test_new_game_and_move_flow():
    state = client.post("/api/game/new", json={"config": CFG}).json()
    assert len(state["board"]) == 6 and len(state["board"][0]) == 7
    assert state["current_player"] == 1 and state["legal_moves"] == list(range(7))
    state = client.post("/api/game/move", json={"config": CFG, "moves": [], "move": 3}).json()
    assert state["board"][5][3] == 1 and state["current_player"] == 2 and state["moves"] == [3]


def test_illegal_move_is_a_400():
    r = client.post("/api/game/move", json={"config": CFG, "moves": [], "move": 9})
    assert r.status_code == 400 and "outside" in r.json()["detail"]


def test_illegal_history_is_rejected():
    r = client.post("/api/game/state", json={"config": CFG, "moves": [0] * 8})
    assert r.status_code == 400


def test_invalid_configuration_is_rejected():
    r = client.post("/api/game/new", json={"config": {"rows": 3, "cols": 3, "n": 5}})
    assert r.status_code in (400, 422)


def test_move_after_game_over_is_rejected():
    r = client.post("/api/game/move", json={"config": CFG, "moves": [0, 1, 0, 1, 0, 1, 0], "move": 2})
    assert r.status_code == 400


def test_winner_is_reported_with_winning_cells():
    s = client.post("/api/game/state", json={"config": CFG, "moves": [0, 1, 0, 1, 0, 1, 0]}).json()
    assert s["winner"] == 1 and s["is_over"] and len(s["winning_cells"]) == 4


@pytest.mark.parametrize("difficulty", ["easy", "medium", "hard"])
def test_ai_move_by_difficulty(difficulty):
    r = client.post("/api/game/ai-move", json={"config": CFG, "moves": [3], "difficulty": difficulty}).json()
    d = r["decision"]
    assert d["move"] in range(7) and len(r["state"]["moves"]) == 2
    assert d["time_ms"] >= 0 and d["explanation"]


def test_ai_move_returns_decision_statistics_for_search_agents():
    r = client.post("/api/game/ai-move", json={"config": CFG, "moves": [3, 3],
                                                "agent": {"kind": "alphabeta", "depth": 4}}).json()
    d = r["decision"]
    assert d["depth"] == 4 and d["nodes"] > 0 and d["move_scores"] and "Alpha-Beta" in d["explanation"]


def test_ai_move_on_finished_game_is_rejected():
    r = client.post("/api/game/ai-move", json={"config": CFG, "moves": [0, 1, 0, 1, 0, 1, 0]})
    assert r.status_code == 400


def test_unknown_agent_and_difficulty_are_rejected():
    assert client.post("/api/game/ai-move", json={"config": CFG, "agent": {"kind": "nope"}}).status_code == 400
    assert client.post("/api/game/ai-move", json={"config": CFG, "difficulty": "godlike"}).status_code == 400


def test_search_depth_is_capped_on_huge_free_boards():
    cfg = {"rows": 12, "cols": 12, "n": 5, "gravity": False}
    r = client.post("/api/game/ai-move", json={"config": cfg, "agent": {"kind": "minimax", "depth": 5}})
    assert r.status_code == 200
    d = r.json()["decision"]
    assert d["depth"] < 5 and d["notes"]


def test_free_placement_game_over_the_api():
    cfg = {"rows": 5, "cols": 5, "n": 4, "gravity": False}
    r = client.post("/api/game/ai-move", json={"config": cfg, "moves": [12], "agent": {"kind": "greedy"}})
    assert r.status_code == 200 and len(r.json()["state"]["moves"]) == 2


def test_arena_series_is_consistent():
    r = client.post("/api/arena/series", json={
        "config": CFG, "games": 4, "seed": 1, "opening_plies": 2,
        "agent1": {"kind": "greedy"}, "agent2": {"kind": "random"},
    }).json()
    assert r["a_wins"] + r["b_wins"] + r["draws"] == 4
    assert len(r["game_log"]) == 4 and r["a_wins"] >= 3  # greedy should crush random


def test_benchmarks_endpoint_reports_missing_results_or_returns_json():
    r = client.get("/api/benchmarks")
    assert r.status_code in (200, 404)


def test_ai_scores_are_always_valid_json_even_for_immediate_wins():
    # P1 to move and can win at column 3: Greedy's score must serialise (no inf/nan)
    r = client.post("/api/game/ai-move", json={"config": CFG, "moves": [0, 6, 1, 6, 2, 5],
                                                "agent": {"kind": "greedy"}})
    assert r.status_code == 200
    d = r.json()["decision"]
    assert d["move"] == 3 and d["score"] is not None and d["score"] > 100_000
