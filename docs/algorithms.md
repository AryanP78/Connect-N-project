# Algorithms

All search agents share the evaluator in `backend/evaluation/heuristic.py`, the same terminal scoring and the same centre-first move ordering.

## Heuristic evaluation

For player *P* and every window *w* of N consecutive cells (horizontal, vertical, both diagonals):

```
if w contains no opponent token and k of P's tokens:   +growth^(k-1)
if w contains no P token and k opponent tokens:        -opp_factor * growth^(k-1)
+ immediate_threat      * (#distinct empty cells that complete a P window AND are playable now)
- opp_immediate_threat  * (#same for the opponent)         <- the blocking incentive
+ center * (sum of centre-closeness of P's tokens - same for the opponent)
```

Default weights: `growth = 6`, `opp_factor = 1.15`, `immediate_threat = 40`, `opp_immediate_threat = 60`, `center = 3` (`HeuristicWeights`). In gravity mode a threat is "playable" only if the cell is on the bottom row or the cell below it is occupied; in free placement every empty cell is playable.

**Terminal override:** a won position is `+WIN_SCORE` (1,000,000), a lost one `-WIN_SCORE`, a draw `0`; heuristic values are clipped to `+-100,000`. Search agents use `WIN_SCORE - ply` so that sooner wins and later losses are preferred.

The evaluator is vectorised: one fancy-index `cells[windows]` produces an (windows x N) matrix, token counts and window values follow from `sum` / table lookup (about 40 microseconds per call on the default board).

## Random
Chooses `random.choice(legal_moves)`.

## Greedy
```
for m in ordered_moves: if wins_for(m, me): return m           # take the win
for m in ordered_moves: if wins_for(m, opp): return m          # block
score(m) = heuristic(position after m) - 500000 * [opponent has an immediate winning reply]
return random choice among the best-scoring moves
```

## Minimax (depth-limited)
```
search(depth, ply):
    if won:  return +-(WIN - ply)        # from the root player's perspective
    if draw: return 0
    if depth == 0: return heuristic(root player)
    if root player to move: return max over children
    else:                   return min over children
```
Moves are generated centre-first and applied with `play` / `undo` on one board. The root keeps the first move with a strictly better value (ties within 1e-6 are ties), unless `randomize_ties` is enabled.

## Alpha-Beta
Same recursion with `alpha` (best the root player can force) and `beta` (best the opponent can force); a node returns as soon as `alpha >= beta` (fail-soft). Because it uses the same evaluation, ordering and tie rule, it returns the **same move and value** as Minimax at equal depth; only the work differs. Values reported for non-chosen root moves are upper bounds (tests assert this). The number of cut-offs is recorded.

Why it is exact: a cut-off only discards subtrees that cannot change the minimax value at the root; the root window `(best, +inf)` guarantees that any child that could beat the current best returns its exact value, and any other child returns a value `<= best`.

## Monte Carlo Tree Search (UCT)
```
repeat `simulations` times:
    node = root
    while node fully expanded and not terminal: node = argmax wins/visits + c*sqrt(ln(parent.visits)/visits)
    if not terminal: expand one random untried move
    play uniformly random moves until the game ends
    back-propagate: +1 for the player who made the move into each node if they won, +0.5 for a draw
play the most-visited child; report wins/visits of every root move as its win probability
```
`nodes` in the decision is the number of simulations; random-playout plies are in `extra["rollout_plies"]`.

## Complexity (measured)
Minimax cost grows by roughly the branching factor per ply (about 6-7x per ply in experiment 2); Alpha-Beta with centre-first ordering explores far fewer nodes at the same depth (experiment 3). Exact figures are in [benchmarks.md](benchmarks.md).
