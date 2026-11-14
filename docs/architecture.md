# Architecture

## Design goal

> One shared game engine + multiple AI agents + one benchmarking framework + one interactive application.

The rules live in exactly one place. Everything else - agents, the benchmark runner, the web API and the UI - consumes the engine and none of them re-implements a rule.

## Layers

| Layer | Package | Responsibility | Depends on |
|---|---|---|---|
| Engine | `backend/engine` | Board state, move validation, gravity / free placement, win + draw detection, undo | NumPy |
| Evaluation | `backend/evaluation` | Vectorised heuristic, explainable breakdown, terminal override | engine |
| Agents | `backend/agents` | Common `Agent` interface and five implementations, factory, difficulty presets | engine, evaluation |
| Benchmarks | `backend/benchmarks` | Tournaments, experiments, charts, report generator | engine, agents |
| API | `backend/api` | Stateless FastAPI layer; serves the built UI | all of the above |
| UI | `frontend/src` | React pages and components | API only |

Dependencies point downwards only: the engine knows nothing about agents, and agents know nothing about HTTP.

## The engine

* `GameConfig(rows, cols, n, gravity)` - frozen, validated (1-12 per side, `2 <= n <= max(rows, cols)`).
* `ConnectNGame` stores the board as a flat `int8` NumPy array (row 0 = top), per-column heights (gravity) and a move history.
  * A **move** is a column index (gravity) or a flat cell index (free placement).
  * `play(move)` validates *before* mutating: integer type (bools and floats rejected), range, full column / occupied cell, game already over. It raises `IllegalMoveError` and leaves the state unchanged.
  * `undo()` restores the previous state exactly; `copy()`, `from_moves()` replay a history with validation.
  * Win detection looks only at the four lines through the last token, O(N).
  * `wins_for(move, player)` answers "would this win?" for either player without changing the state - the basis of immediate-win and block detection.
* `geometry.py` pre-computes (and caches per configuration) every N-cell window, a centre-closeness map, "supported by" indices for playability and the centre-first move ordering.

## The agent interface

```python
class Agent(ABC):
    def _decide(self, game) -> Decision: ...     # implemented by each agent, receives a private copy
    def select_move(self, game) -> Decision:     # public: copy, time, legality check
    def choose_move(self, game) -> int:          # convenience
```

`Decision` carries `move`, `time_ms`, `nodes`, `depth`, `max_depth`, `score`, `move_scores`, an `explanation` string and agent-specific `extra` data (cut-offs, visit counts, ...). It is what the API returns and what the tournament framework aggregates.

## The API (stateless)

| Endpoint | Purpose |
|---|---|
| `GET /api/agents` | agent catalogue, difficulty presets, heuristic weights |
| `POST /api/game/new` / `state` / `move` | create, replay or advance a game |
| `POST /api/game/ai-move` | let an agent (or a difficulty preset) play; returns the new state and the `Decision` |
| `POST /api/arena/series` | play a short side-swapped series (<= 30 games) |
| `GET /api/benchmarks` | the stored experiment results |

Every request includes `config`, `moves` and `first_player`; the engine rebuilds the position and validates it. Search depth is reduced automatically when `branching ** depth` would exceed a node budget (reported in `decision.notes`).

## The benchmarking framework

`tournament.py` provides `play_game`, `run_pairing` and `run_round_robin`:

* games are played in **pairs with a shared random opening and swapped sides**;
* agents are rebuilt per game from `{kind, depth, simulations, seed}` specs, so runs are reproducible and can be parallelised with a process pool (a test asserts serial == parallel);
* each decision's time, nodes and depth are accumulated per agent;
* `measure_memory` uses `tracemalloc` on sampled positions.

`run_experiments.py` runs the four experiments + memory profile and writes JSON / CSV / PNG; `report.py` renders the Markdown tables.

## The frontend

React 19 + Vite + Tailwind CSS 4 + Recharts. `useGame` wraps the stateless API (move list in, state out) and guards against stale responses after a reset. `Board` is an SVG component with hover previews, drop animation and a winning-line highlight; `LiveMatch` drives AI-vs-AI playback with pause / step / speed controls. Agent colours are fixed per agent across every chart (a palette validated for colour-blind separation), values are labelled directly on marks, and the layout is responsive down to phone width.
