# KFChess — UI Layer Plan

Status: design decisions locked in for movement/collision, input, animation ownership, and coordinate mapping. Architecture/folder structure still open (see bottom).

This document exists so nothing decided in planning gets lost or re-decided differently by an implementer (human or Claude Code). It is **not** a build order — it's a decision record. A separate task-by-task build plan should be derived from this once the architecture section is finalized.

---

## 1. Scope of this phase

- Building the UI layer (OpenCV-based) on top of the already-complete, fully-tested engine/domain layer.
- Two players sharing one machine for now — a networked server is a **future** phase, not in scope here.
- Promotion UI (piece reaching the last rank) is explicitly **deferred** — not part of this phase.

---

## 2. Real-time movement & collision model (ENGINE change, not just UI)

This is a **behavior change to the engine**, not a rendering detail. The engine currently resolves a move as one atomic `PendingMove(from, to)` scheduled at click time and settled as a single event. This must change to:

- A multi-cell move advances **cell by cell**, not as one atomic jump from A to B.
- After each single-cell step, the piece's **source square updates** to the cell it just reached (that cell becomes its new "home" going forward).
- Before advancing into the *next* cell, the engine re-checks that cell's occupancy — not just once at click time.
- **Does not apply to the knight** — it jumps directly, no path to check.
- Pawn's double-step move follows the exact same cell-by-cell rule — no special-casing.

### What happens when the next cell is occupied

| Occupant of next cell | Result |
|---|---|
| Friendly (own color) piece | Piece **stops permanently** at its current square. No capture. Does **not** auto-resume toward the original destination — needs a fresh player selection to continue from there. |
| Enemy piece (grounded) | Piece **captures** it and stops there (consistent with the existing `SlidePattern` semantics — just re-evaluated per step instead of once for the whole path). |
| Enemy piece (airborne, i.e. mid-jump) | *See airborne rule below — landing-instant occupancy is what matters, not simple "presence".* |

### Rest-state rule after a stopped move

- Enters `LONG_REST` if the piece moved **at least one cell** before stopping.
- Stays `IDLE` (no rest) if it was blocked on the **very first step** and never moved at all — this only happens if the path became blocked *between click time and the first step* (the initial click-time legality check already rejects moves whose final destination is blocked by a friendly piece at click time).

### Airborne / jump capture rule

- A piece goes airborne when it jumps (in place — jumping does not relocate a piece, it's a vertical action on the same square).
- **While airborne, its origin square is vacated** on the board — other pieces can move through or stop on that square as if it were empty.
- An airborne piece captures **only** whatever occupies its square at the **exact instant it lands** — not continuously while it's in the air. A piece that passes through or momentarily sits on that square *before* the landing instant is safe.
- This rule is **general**: it applies to any piece present on the landing square at landing time, regardless of how that piece got there (mid-path stop, already resting there, etc.) — not just to some other piece's own move destination.
- **Known gap in current engine code**: `_land_due_jumps()` in `game_engine.py` currently always succeeds and starts `SHORT_REST` — it does not check occupancy of the landing square at all. This needs to be added. The existing `AIRBORNE_CAPTURE` check in `RealTimeArbiter` only covers the reverse direction (a *mover* discovering its destination is airborne) — that logic needs to extend to per-step checks too, given the cell-by-cell model above.

---

## 3. Selection & input model (click semantics)

- Two-click model: first click **selects** a piece, second click is the **target**.
- **Player identity**: claimed dynamically, no login. Whichever color a player clicks *first* becomes their color for that session. This does not exist in the current code (`Controller.click()` just forwards to `engine.click()` with no identity concept) — it's a new layer to build.
- Clicking an empty square or an opponent's piece as a first click → **no selection** (nothing happens).
- Clicking the *same* square twice (i.e., clicking the already-selected piece again) → triggers an **in-place jump**.
- Clicking a **different** piece of your own color while something is already selected → **switches** selection to the new piece (does not attempt a move).
- Clicking an invalid target square (second click) → **cancels** the current selection.
- Clicking a piece that is currently busy (not `IDLE`) → **not registered as a selection at all** (as if nothing was clicked).
- "Currently selected piece" is **UI-owned state** — it has no meaning inside the engine/domain, it's purely what the player is currently pointing at.

---

## 4. Time model

- The engine is currently pull-based: a `ManualClock` only advances when something calls `wait(ms)` externally. No thread/timer/loop exists anywhere in the codebase today.
- Decision: keep the engine as-is (its `now()`/`advance()` seam is already correctly designed for this). Add a **driver layer** outside the engine.
- The driver is built against an **abstract time-source interface** (not hardcoded to any concrete clock), so a future networked/synced clock can be swapped in later without touching the engine or the driver's own loop logic.
- The concrete local implementation is a **real wall-clock** (`time.time()`-based), measured independently every frame — **not** derived from `cv2.waitKey()`'s return timing. This avoids the game clock silently "freezing" whenever rendering hiccups (window resize, GC pause, etc.) — real elapsed time is always measured directly, decoupled from render cadence.

---

## 5. Animation / sprite system

### What already exists
- `assets/board.png` — 822×828px, ~103px per cell, effectively no margin (checkerboard starts at pixel (0,0), aside from a ~1-2px stray edge artifact). **This is a placeholder/test asset** (width and height differ by 6px, so it isn't perfectly divisible into square cells) — final board asset may replace it later; treat `cell_size_px` as a config value, not something computed from this specific file.
- `assets/pieces/<colorkind>/states/{IDLE,MOVE,JUMP,LONG_REST,SHORT_REST}/` — each has numbered sprite-frame images plus a `config.json` with `physics.speed_m_per_sec`, `physics.next_state_when_finished`, `graphics.frames_per_sec`, `graphics.is_loop`.
- No `CAPTURED` folder exists — intentional (no animation needed), but the mapping mechanism below must make adding one later trivial.

### Decisions
- **State ownership split**: the *logical* state machine (which state a piece is in, and what it transitions to when) is owned entirely by the engine/domain — it already exists there (`PieceState` enum, `LONG_REST`/`SHORT_REST` durations, etc.). The UI is a **read-only observer** of that state — it does not decide transitions, it only asks "what state is this piece in right now, and since when?" and picks a sprite set accordingly.
- **`next_state_when_finished` in the sprite config.json is dead weight** — it duplicates transition logic that the engine already owns exclusively. The UI must **ignore this field**; it should probably be removed from the sprite config files entirely to avoid a false second source of truth. If a transition-table config is wanted for readability/extensibility, it belongs in a **domain-owned** config file, separate from the animation/sprite config.
- **Folder-name ↔ engine-state-name mapping is not 1:1** (`MOVE`↔`MOVING`, `JUMP`↔`AIRBORNE`) and must be an **explicit, data-driven mapping** (not string-equality assumption), so that adding e.g. `CAPTURED` later is just a config addition, no code change.
- **Animation frame selection is stateless and time-based**, not a blocking loop: each render tick, for each piece, compute `elapsed = now - state_entered_at`, then `frame_index = int(elapsed * fps) % num_frames` (looped) or clamped (non-looped, e.g. jump). This works for arbitrarily many pieces animating independently within a single non-blocking render loop — no per-piece threads or blocking `while` loops.
- Requires the engine to expose `state_entered_at` (or equivalent) per piece so the UI can compute this.
- **Meters→pixels conversion**: `cell_size_meters` is an arbitrary but fixed config value (recommended: `1 meter per cell`, since it's just a unit for speed math, not a real-world measurement). `px_per_meter = cell_size_px / cell_size_meters`, then `speed_px_per_sec = speed_m_per_sec * px_per_meter`.

### Continuous position during a move (glide, not teleport)
Because moves are now cell-by-cell (see §2), each visual "leg" of a move is a simple two-cell glide over a fixed duration (`move_duration_per_cell_ms`), rather than needing complex multi-cell interpolation. The UI needs the current step's start cell, target cell, and start time to compute `progress = (now - step_start_time) / step_duration` and interpolate pixel position — this is a natural consequence of the cell-by-cell engine change, not a separate mechanism.

---

## 6. Coordinate mapping & board sizing

- The board image will **not** be auto-measured at runtime. Image size and margins (0 if none) are **config values**; `cell_size_px` and pixel offsets are computed from those config values, not measured from the image file.
- Measured placeholder image: 822×828px, ~103px/cell, ~0 margin. Recommend rounding to a single `cell_size_px = 103` config value (accept the ~6px slack) until a final square asset replaces it.
- `BoardMapper` (pixel → cell) already exists but currently has **no margin/offset support** — needs extending.
- Screen → window → image pixel scaling (if window is resizable) is a related concern not yet fully decided (see open items below).

---

## 7. Explicitly deferred / out of scope for this phase

- Promotion UI (dialog/menu for pawn promotion choice) — `Controller.choose_promotion()` already exists in the engine-facing API, but no UI is planned for it yet.
- Networked/multi-machine play — architecture should not *block* this later (hence the abstract time-source decision), but no networking code is being built now.
- Score / move-history display — agreed to use an **Observer pattern**, decoupled from the core move-resolution path (must never block or slow down piece movement resolution); exact display format not yet designed.

---

## 8. Known gaps / TODOs surfaced during planning

- `_land_due_jumps()` needs an occupancy check at landing time (see §2, airborne rule).
- `RealTimeArbiter`'s airborne-capture check needs to extend from "final destination only" to "every intermediate step".
- `Controller` needs a new player-identity/claiming layer — doesn't exist today.
- `BoardMapper` needs margin/offset support — doesn't exist today.
- `image_view.py` (PPM-based) and the rest of the `view`/`input`/`io` placeholder files are stand-ins and will be replaced with real OpenCV-based implementations.
- Sprite config.json files should have `next_state_when_finished` removed/ignored.

---

## 9. Architecture — folder structure & design patterns

### Convention

The project uses **flat top-level packages under `kungfu_chess/`**, one per concern, with no umbrella nesting (e.g. no single `domain/` or `ui/` folder grouping several concerns together) — this was the structure required by the lecturer for the logic phase, and the decision is to **keep following the same convention** for the UI layer rather than introduce a new nested wrapper. Existing packages: `engine/`, `model/`, `rules/`, `realtime/`, `input/`, `view/`, `io/`, `texttests/`, `tests/{unit,integration}`, plus `app.py` at the root.

### Actual current structure (as confirmed against the real repo tree)

```
kungfu_chess/
  app.py                  # existing CLI entry point (script_runner-based), stays as-is
  engine/                 # existing — game_engine.py
  model/                  # existing — board.py, game_state.py, piece.py, position.py
  rules/                  # existing — piece_rules.py, rule_engine.py
  realtime/               # existing — motion.py, real_time_arbiter.py
  io/                     # existing — board_parser.py, board_printer.py (text↔Board)
  texttests/              # existing — script_parser.py, script_runner.py
  tests/{unit,integration}

  config/                 # NEW top-level package
    board_config.py          # board image size, margins, cell_size_px, cell_size_meters
    sprite_state_mapping.py  # folder-name ↔ PieceState mapping (MOVE↔MOVING, JUMP↔AIRBORNE...), data-driven so CAPTURED can be added later without code changes

  input/                  # existing — extended:
    board_mapper.py         # + margin/offset support (currently flat cell_size_px only)
    controller.py           # existing facade — extended with the click-semantics from §3
    player_session.py       # NEW — color-claiming ("who clicked first") logic

  view/                   # existing — extended:
    renderer.py              # existing — pure geometry (GameState → CellView), largely unchanged
    opencv_view.py           # NEW — replaces image_view.py (which was a stdlib PPM placeholder)
    sprite_registry.py       # NEW — loads sprite frames + config.json; owns the folder-name↔PieceState mapping
    animation_clock.py       # NEW — stateless: (state, state_entered_at, now) → frame index

  driver/                 # NEW top-level package
    time_source.py           # abstract time-source interface + concrete WallClock (time.time()-based)
    game_loop.py              # main loop: poll input → time_source.now() → engine.wait(dt) → render

  observers/               # NEW top-level package
    move_log_observer.py     # score / move-history, decoupled from the core move-resolution path

app_ui.py                 # NEW — UI entry point (separate from the existing app.py CLI/test entry point)
```

### Design patterns in play

| Pattern | Where |
|---|---|
| Strategy | `StepPattern` / `SlidePattern` / `PawnDoubleStepPattern` (existing) |
| State | `PieceState` enum + engine-owned transitions; UI is a **read-only observer** of this state, never a decider |
| Observer | `observers/move_log_observer.py` — score/move-list updates, decoupled from move resolution so it can never slow down or block gameplay |
| Adapter | `BoardMapper` — translates between pixel-space and cell-space |
| Facade | `Controller` — the **only** door from UI code into the engine; nothing else in `input/`/`view/`/`driver/` talks to `engine`/`model`/`rules`/`realtime` directly |
| Dependency Injection | `TimeSource` is injected into `game_loop.py` (not hardcoded), so a future network-synced clock implementation can be swapped in without touching the loop's own logic; no singletons/globals anywhere in the new packages |

### Key discipline for future swappability

The person wants it to stay easy to swap out the graphics library (or the whole UI) later, without maintaining two separate repos or a hard split. This is achieved by discipline, not by physical separation: **`input/`, `view/`, and `driver/` may only reach the logic layer through `Controller` (facade) and `GameState` snapshots** — never by importing engine/model/rules internals directly (e.g. never importing `PieceState` directly into `view/` code; it must come through whatever the snapshot/Controller exposes). As long as that boundary holds, replacing OpenCV with another library only touches files inside `input/`, `view/`, and `driver/`.

---

## 10. Build order

This is **not** meant to be handed to an implementer as one giant task. Each numbered step below is scoped to be its own prompt/session, with its own tests, before moving to the next — consistent with the 100%-coverage, no-surprises discipline already used for the logic layer.

1. **Engine changes** (§2, §5's `state_entered_at` requirement) — cell-by-cell movement, landing-occupancy check, exposing whatever position/timestamp data the UI will need. Verified entirely through `texttests` (existing + new scripts) — no UI involved yet. This must come first: every later step builds on this new engine behavior, and reworking UI code after an engine behavior change would be wasted effort.
2. **Config layer** (§5, §6) — board size/margin config, meters-per-cell, sprite folder-name↔state mapping. Pure data, fast, unblocks both rendering and input work.
3. **Static rendering** — `board_mapper` margin support + `opencv_view` drawing the board and pieces with **no animation** (one static frame per piece). Purpose: visually verify the pixel math is correct before adding animation complexity on top (the lecturer's own advice — verify coordinate mapping visually first).
4. **Input handling** — `player_session` + the full click-selection semantics (§3) in `controller`, wired to real OpenCV mouse events, still rendered statically. This proves the full click → engine → board-update chain works end to end (pieces will appear to "teleport" to their destination — that's expected and fine at this stage).
5. **Driver** — `time_source` (`WallClock`) + `game_loop`, replacing manual/test-only `wait()` calls with a real continuous loop. This is what makes the game actually run in real time instead of only advancing when a script tells it to.
6. **Animation** — `sprite_registry` + `animation_clock` + continuous glide interpolation for in-progress moves, layered on top of the now-working interactive version.
7. **Observers** — `move_log_observer` (score/move history), additive and non-blocking.

**Deferred (already decided, not part of this build order):** promotion UI, networked/multi-machine play.

---

## 11. Post-Step-5 additions (decided after Step 5 completion)

These were decided once resizable-window support (built as an add-on to Step 5) surfaced further requirements. They extend, not replace, everything above.

### 11.1 Resizable window — click-scaling bugfix

Step 5's resizable-window add-on (`driver/window_scaling.py`) initially double-scaled click coordinates: on this environment's OpenCV build/backend, `cv2.setMouseCallback` already reports coordinates in the board's native pixel space on a `WINDOW_NORMAL` window, so applying `window_scaling.scale_to_native()` on top of that was applying a translation twice. Must be verified empirically (print raw callback coordinates vs `cv2.getWindowImageRect()` at known points, across a few window sizes) rather than assumed either way, then fixed accordingly (either drop the manual scaling and pass raw coordinates through, or fix a genuine transform bug if raw coordinates turn out to really be in displayed space).

### 11.2 Resizable window — aspect ratio lock

The board must **never distort** when the window is resized. The board's own width:height ratio (currently ~822:828 per the placeholder asset) is preserved on every resize — this belongs in `driver/` (the same layer that already owns resize/scaling), not in `board_mapper`/`renderer`/`opencv_view`, which keep working in native board pixel space exactly as today.

### 11.3 Score & move-list side panels

Brings forward part of Step 7 (Observers) with a concrete layout, ahead of Step 6 (animation):

- **Layout**: board centered, one panel flanking each side — one player's score + move list on the left, the other's on the right (which color goes on which side is arbitrary/cosmetic, not a rule).
- **Score**: standard material scoring (sum of captured piece values, standard chess values) — already implemented in the codebase, needs surfacing to this panel, not reimplementing.
- **Move list**: standard algebraic chess notation — already implemented in the codebase, same as above. The list must be **scrollable** (mouse wheel or equivalent), not truncated to a fixed number of most-recent moves with no way to see older ones.
- **Resize behavior**: when the window grows/shrinks, panel width stays close to fixed — most of the size change is absorbed by the board itself, not by the panels growing proportionally with it.
- Still built as an **Observer**, decoupled from the core move-resolution path (per §9's Observer pattern entry) — populating/updating the panels must never block or slow down piece movement resolution.
