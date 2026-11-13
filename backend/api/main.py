"""FastAPI application: a thin, stateless HTTP layer over the engine, agents and benchmarks.

The server keeps **no game sessions**.  Every request carries the configuration and the
move list; the engine replays and validates it, so a client can never put the board into
an illegal state and the API scales trivially.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ..agents import (
    AGENT_CATALOG, DIFFICULTY_PRESETS, AgentError, Decision, agent_from_difficulty,
    create_agent_from_spec,
)
from ..benchmarks import run_pairing
from ..engine import ConnectNGame, GameConfig, IllegalMoveError
from ..evaluation import DEFAULT_WEIGHTS, explain_position
from .schemas import (
    AIMoveRequest, AnalyzeRequest, ConfigModel, GameStateRequest, MoveRequest, NewGameRequest,
    SeriesRequest,
)

ROOT = Path(__file__).resolve().parents[2]
RESULTS_FILE = ROOT / "docs" / "results" / "benchmarks.json"
FRONTEND_DIST = ROOT / "frontend" / "dist"

# Safety budgets (nodes) so a request on a huge board cannot hang the server.
SEARCH_NODE_BUDGET = {"minimax": 250_000, "alphabeta": 2_500_000}

app = FastAPI(title="Connect-N AI", version="1.0.0",
              description="Game engine, AI agents and benchmarks for Connect-N.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"], allow_headers=["*"],
)


# ------------------------------------------------------------------- helpers
def build_game(req: GameStateRequest) -> ConnectNGame:
    try:
        config = GameConfig(**req.config.model_dump())
        return ConnectNGame.from_moves(config, req.moves, req.first_player)
    except IllegalMoveError as exc:
        raise HTTPException(400, f"illegal move history: {exc}")
    except ValueError as exc:
        raise HTTPException(400, str(exc))


def cap_search_depth(spec: Dict[str, Any], game: ConnectNGame) -> Optional[str]:
    """Reduce an over-ambitious search depth so the request finishes in reasonable time."""
    kind = spec.get("kind", "").lower().replace("-", "").replace("_", "")
    if kind not in SEARCH_NODE_BUDGET or not spec.get("depth"):
        return None
    branching = max(len(game.legal_moves()), 2)
    budget = SEARCH_NODE_BUDGET[kind]
    depth = spec["depth"]
    capped = depth
    while capped > 1 and branching ** capped > budget:
        capped -= 1
    if capped != depth:
        spec["depth"] = capped
        return (f"Search depth reduced from {depth} to {capped} for this board "
                f"({branching} legal moves) to keep the response time reasonable.")
    return None


def resolve_agent_spec(agent, difficulty: Optional[str]) -> Dict[str, Any]:
    if agent is not None:
        return agent.model_dump(exclude_none=True)
    level = difficulty or "hard"
    if level not in DIFFICULTY_PRESETS:
        raise HTTPException(400, f"unknown difficulty {level!r}; choose one of {list(DIFFICULTY_PRESETS)}")
    return dict(DIFFICULTY_PRESETS[level])


def run_agent(spec: Dict[str, Any], game: ConnectNGame):
    notes = []
    note = cap_search_depth(spec, game)
    if note:
        notes.append(note)
    try:
        agent = create_agent_from_spec(spec)
        decision: Decision = agent.select_move(game)
    except (ValueError, AgentError) as exc:
        raise HTTPException(400, str(exc))
    out = decision.to_dict()
    out["agent_spec"] = agent.describe()
    out["notes"] = notes
    return out


# ---------------------------------------------------------------- endpoints
@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/agents")
def agents():
    return {
        "agents": AGENT_CATALOG,
        "difficulties": DIFFICULTY_PRESETS,
        "default_config": GameConfig().to_dict(),
        "heuristic_weights": DEFAULT_WEIGHTS.to_dict(),
    }


@app.post("/api/game/new")
def new_game(req: NewGameRequest):
    return build_game(GameStateRequest(**req.model_dump())).to_dict()


@app.post("/api/game/state")
def game_state(req: GameStateRequest):
    return build_game(req).to_dict()


@app.post("/api/game/move")
def play_move(req: MoveRequest):
    game = build_game(req)
    try:
        game.play(req.move)
    except IllegalMoveError as exc:
        raise HTTPException(400, str(exc))
    return game.to_dict()


@app.post("/api/game/ai-move")
def ai_move(req: AIMoveRequest):
    game = build_game(req)
    if game.is_over:
        raise HTTPException(400, "the game is already over")
    decision = run_agent(resolve_agent_spec(req.agent, req.difficulty), game)
    game.play(decision["move"])
    return {"state": game.to_dict(), "decision": decision}


@app.post("/api/game/analyze")
def analyze(req: AnalyzeRequest):
    """Evaluate the current position without playing: heuristic breakdown + best move."""
    game = build_game(req)
    response: Dict[str, Any] = {
        "state": game.to_dict(),
        "evaluation": {
            "player_1": explain_position(game, 1),
            "player_2": explain_position(game, 2),
        },
        "decision": None,
    }
    if not game.is_over:
        spec = resolve_agent_spec(req.agent, "hard")
        response["decision"] = run_agent(spec, game)
    return response


@app.post("/api/arena/series")
def arena_series(req: SeriesRequest):
    """Play a short series between two agents (used by the AI Arena scoreboard)."""
    config = GameConfig(**req.config.model_dump())
    probe = ConnectNGame(config)
    specs = []
    notes = []
    for model in (req.agent1, req.agent2):
        spec = model.model_dump(exclude_none=True)
        note = cap_search_depth(spec, probe)
        if note:
            notes.append(note)
        specs.append(spec)
    try:
        result = run_pairing(specs[0], specs[1], games=req.games, config=config.to_dict(),
                             seed=req.seed, opening_plies=req.opening_plies, keep_games=True)
    except (ValueError, AgentError) as exc:
        raise HTTPException(400, str(exc))
    result["notes"] = notes
    return result


@app.get("/api/benchmarks")
def benchmarks():
    if not RESULTS_FILE.exists():
        raise HTTPException(404, "No benchmark results yet. Run: python -m backend.benchmarks.run_experiments")
    return json.loads(RESULTS_FILE.read_text())


# ---- serve the built React app (production / single-command demo) -------------
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404)
        candidate = (FRONTEND_DIST / path).resolve()
        if path and FRONTEND_DIST in candidate.parents and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
