# KFChess — About This Project

KFChess ("Kung Fu Chess") is a **real-time, simultaneous-move chess variant** implemented in Python. Unlike standard chess, there are no turns: either player can move any of their idle pieces at any moment, moves take real time to complete (scaled by distance), and pieces can collide, block, or capture each other mid-flight. The project ships both a live OpenCV-rendered UI (`app_ui.py`) and a headless text-script engine used for testing (`kungfu_chess/app.py`).

There is no `README.md`; the closest thing to a design document is **`UI_PLAN.md`** at the repo root, which is a decision record (not a build order) written during the `refactor/kungfu-chess-architecture` branch work. Much of the architectural rationale below is drawn from it.

## Repository layout

```
KFChess/
  app_ui.py                  # Live UI entry point: python app_ui.py
  UI_PLAN.md                 # Architecture/design-decision record
  requirements.txt           # pytest, coverage, opencv-python, numpy (unpinned)
  .coveragerc                # coverage.py config (source=kungfu_chess)
  assets/                    # In-use art: board.png + per-piece sprite states
  asets/                     # Stale duplicate asset tree (typo'd name, unreferenced by code)
  kungfu_chess/               # The Python package (see below)
  scripts/
    render_static_board.py             # Renders one static frame for visual sanity checks
    strip_next_state_when_finished.py  # One-off cleanup of a vestigial config.json field
  game_logic_combined.txt    # Ad-hoc scratch dump of older engine source, not part of the package
```

> **Note on cruft:** `asets/` (missing the "s") is an older, partial copy of `assets/` with fewer sprite frames and different `config.json` values. Nothing in the codebase references it — it appears to be a stale leftover safe to remove. `game_logic_combined.txt` is similarly a scratch/paste file reflecting an earlier version of the engine, not live code.

There is no `pyproject.toml`/`setup.py` — the project is run directly from source, not installed as a package.

## The `kungfu_chess/` package

The package is intentionally **flat** (no deep nesting) with each top-level subpackage owning one concern. Layers are separated by a strict **boundary discipline**: `input/`, `view/`, and `driver/` may only reach game logic through `Controller` and `GameState` snapshots — they never import `engine/`, `model/`, `rules/`, or `realtime/` internals directly. For example, the renderer only ever reads `piece.color` / `.kind` / `.state.name` / `.state_entered_at`, treating pieces as opaque objects.

```
kungfu_chess/
  app.py                # CLI entry: reads a .kfc script from stdin, runs it, writes results to stdout

  model/                # Pure data/entities — no rules, no timing, no IO
    position.py             Position(row, col), square_name(), chebyshev_distance()
    piece.py                Piece (eq=False, identity semantics), PieceState enum, passes_as_empty()
    board.py                Board: grid storage + apply_move/promote/remove/place/get/in_bounds
    game_state.py           GameState: move history, scores, pending promotions, game-over flag

  rules/                 # Legal-move definitions + consequences
    piece_rules.py           Config-driven patterns (Step/Slide/PawnDoubleStep), promotions, values
    rule_engine.py           RuleEngine: is_legal_move, settle_clear_move/stopped_move/airborne_capture

  realtime/               # In-flight timing/motion state
    motion.py                ManualClock, PendingMove/AirborneJump/Resting, MotionTracker
    real_time_arbiter.py     RealTimeArbiter.classify(): MOVER_GONE/FRIENDLY_BLOCK/ENEMY_CAPTURE/CLEAR

  engine/
    game_engine.py           GameEngine: the orchestrator tying board+rules+motion+arbiter+state together

  io/                     # Text ⟷ Board conversion (fixture format)
    board_parser.py          parse_board(lines) → Board
    board_printer.py         to_canonical(board) → text

  texttests/              # Script execution harness (composition root for the text protocol)
    script_parser.py         parse_script(text) → (board, commands): click/jump/wait/promote/print
    script_runner.py         build_engine(), run_script() — wires everything together; canonical
                              timing constants (MOVE_DURATION_PER_CELL_MS=1000, JUMP_DURATION_MS=1000,
                              LONG_REST_DURATION_MS=1000, SHORT_REST_DURATION_MS=500, CELL_SIZE_PX=100)

  input/                  # UI → engine translation
    board_mapper.py          BoardMapper: pixel (x, y) → Position(row, col)
    controller.py            Controller: the ONLY door from UI into GameEngine (Facade)
    player_session.py        PlayerSession: claims a color per player (not yet enforced)

  view/                   # Rendering
    renderer.py              BoardRenderer/CellView: pure GameState → pixel-rect layout, no image IO
    opencv_view.py           OpenCvView: actual cv2 image composition, animation, glide interpolation
    sprite_registry.py       Resolves ordered sprite frame paths + fps/is_loop per (color, kind, state)
    sprite_paths.py          sprite_path() helper
    animation_clock.py       frame_index(elapsed_ms, fps, num_frames, is_loop) — pure function
    promotion_menu_view.py   Promotion popup layout/data
    side_panel_view.py       Score + scrollable move-list panel rendering

  driver/                 # Real-time loop / window plumbing
    time_source.py           WallClock: time.time()-based now_ms()
    game_loop.py             GameLoop: tick()/run() — the only place touching cv2 directly
    aspect_ratio.py          Aspect-ratio-locked letterboxing for a resizable window
    panel_layout.py          Fixed-width side panel composition
    promotion_menu_layout.py Per-square promotion popup placement
    mouse_wheel.py           Mouse wheel delta decoding

  observers/
    move_log_observer.py    Pull-based panel data snapshot, decoupled from move resolution

  config/                 # Externalized JSON-backed config (dataclasses + loaders)
    board_config.py / data/board_config.json                 Image size, margins, cell_size_px/meters
    sprite_state_mapping.py / data/sprite_state_mapping.json Folder ↔ PieceState name mapping
    panel_config.py / data/panel_config.json                 Side-panel width/colors/labels/font
    promotion_menu_config.py / data/promotion_menu_config.json  Icon size, choice order
    selection_config.py / data/selection_config.json         Selection-outline color/thickness

  tests/
    unit/          ~35 files, one per module
    integration/    test_text_scripts.py (8 .kfc fixtures), test_opencv_view_smoke.py
```

## Game mechanics

KFChess implements real-time chess mechanics on top of standard chess movement rules:

- **No turns.** Either color may move any `IDLE` piece at any time.
- **Moves take real time.** Duration = `chebyshev_distance(leg) × move_duration_per_cell_ms` (default 1000ms/cell). A moving piece cannot be redirected or reselected until it settles.
- **Cell-by-cell collision.** Multi-cell slides (rook/bishop/queen/pawn double-step) advance one cell ("leg") at a time, and occupancy is re-checked at the instant each leg completes — not just once at click time:
  - A friendly piece now in the way → the mover stops permanently (`LONG_REST`).
  - A grounded enemy piece in the way → captured, mover stops (`LONG_REST`).
  - An enemy piece currently airborne (mid-jump) → passed through as if empty.
  - Knight moves are a single leg regardless of distance, but that leg's duration still scales with Chebyshev distance (2 cells), i.e. twice a normal single-cell leg.
- **Jumping.** Clicking an already-selected piece's own square makes it jump in place: it becomes `AIRBORNE` for `jump_duration_ms` (default 1000ms), logically vacating its square for other movers' path checks while still being rendered there. Whatever piece occupies that square at the exact landing instant gets captured by the landing piece — a reversed-direction capture versus a normal move.
- **Rests.** After settling a move, a piece enters `LONG_REST` (1000ms default); after landing a jump, `SHORT_REST` (500ms default). A resting piece can't be selected until the rest elapses.
- **Captures** are just an unconditional overwrite of the destination cell; scoring uses standard piece values (Q9/R5/B3/N3/P1, K0).
- **Game over** is triggered by capturing a King (configurable, not hardcoded), which pauses the entire engine.
- **Promotion** auto-applies a configured default (Queen) instantly so play is never blocked, but the choice stays open for the player to override via a promotion menu, guarded against staleness by exact piece-instance identity.
- **Move legality** is fully config-driven (`rules/piece_rules.py`): each piece type has movement patterns (`Step`, `Slide`, `PawnDoubleStep`) paired with occupancy requirements (`ANY`/`MOVE_ONLY`/`CAPTURE_ONLY`), decoupling geometry from capture semantics.
- **Time model.** The engine itself is pull-based (`ManualClock`, only advances via `wait(ms)`) — it has no built-in notion of real time. The live UI's `driver/game_loop.py` measures actual wall-clock elapsed time each frame via `WallClock` and feeds it into `controller.wait(dt_ms)`.

## Assets

```
assets/
  board.png
  pieces/
    <color><kind>/            # wK wQ wR wB wN wP bK bQ bR bB bN bP (12 total)
      states/
        idle/   move/   jump/   long_rest/   short_rest/
          config.json
          sprites/1.png … N.png
```

There is no `CAPTURED` sprite folder — none is needed since captured pieces are simply removed. The folder-name ↔ engine `PieceState` mapping is fully data-driven via `config/data/sprite_state_mapping.json` (e.g. `MOVING` → `"move"`, `AIRBORNE` → `"jump"`, `CAPTURED` → `null`).

Each state's `config.json` carries per-state physics/graphics parameters, e.g. (`wQ/states/move/config.json`):
```json
{
  "physics": { "speed_m_per_sec": 1.5 },
  "graphics": { "frames_per_sec": 32, "is_loop": true }
}
```
`is_loop: false` (used by `jump`) holds the animation's final frame once finished. `physics.speed_m_per_sec` is currently unused by any Python code — noted in `UI_PLAN.md` as vestigial, along with a `next_state_when_finished` field the engine alone is responsible for (hence `scripts/strip_next_state_when_finished.py`).

No audio assets exist in the project.

## Configuration

| File | Purpose |
|---|---|
| `requirements.txt` | `pytest`, `coverage`, `opencv-python`, `numpy` (no version pins) |
| `.coveragerc` | coverage.py: `source=kungfu_chess`, omits tests, HTML report → `htmlcov/` |
| `kungfu_chess/config/data/board_config.json` | Board image size 847×851px, margins 47/47px, `cell_size_px=94`, `cell_size_meters=1.0` |
| `kungfu_chess/config/data/sprite_state_mapping.json` | `PieceState` ↔ sprite-folder-name mapping |
| `kungfu_chess/config/data/panel_config.json` | Side-panel width (240px), colors, labels (`{"w":"White","b":"Black"}`) |
| `kungfu_chess/config/data/promotion_menu_config.json` | Icon size (48px), `choice_order: ["Q","R","B","N"]` |
| `kungfu_chess/config/data/selection_config.json` | Selection-outline color/thickness |

## Tests

Framework: **pytest** + **coverage**. Running `pytest -q` from the repo root currently passes **528 tests**.

- `kungfu_chess/tests/unit/` — ~35 files, essentially one per module, heavily using dependency injection/fakes (e.g. `GameEngine` accepts an injectable clock/motion/arbiter/game_state; `SpriteRegistry` accepts injectable `listdir`/`read_config`).
- `kungfu_chess/tests/integration/`
  - `test_text_scripts.py` — parametrized over 8 `.kfc` fixture files (`01_board_parsing.kfc` … `08_airborne_landing_capture.kfc`), each run through `run_script()` and diffed against an embedded `Expected:` section.
  - `test_opencv_view_smoke.py` — a heavier smoke test exercising `OpenCvView` against real assets/cv2.

### The `.kfc` text-script mini-DSL

Each fixture file has three sections:
```
Board:
bR bN bB bQ bK bB bN bR
bP bP bP bP bP bP bP bP
. . . . . . . .
...

Commands:
click <x> <y>
jump <x> <y>
wait <ms>
promote <row> <col> <piece_type>
print board
print score
print promotions

Expected:
<expected stdout>
```

## Running it

- **Live UI:** `python app_ui.py` from the repo root. Opens a resizable OpenCV window ("KFChess") with the standard chess starting position. Click a piece then a destination to request a move; click the same square again to jump in place; `q`/`Esc` to quit. Renders score + move-list side panels and inline promotion popups.
- **Headless text-protocol engine:** `python -m kungfu_chess.app` — reads a `.kfc`-style script from stdin, writes command output to stdout.
- **Dev utilities:** `scripts/render_static_board.py` (one static frame for visual sanity checks), `scripts/strip_next_state_when_finished.py` (removes the vestigial config field from sprite configs).
- **Tests:** `pytest -q`; `coverage run -m pytest && coverage html` for a coverage report.

## Architecture notes

- **Design patterns** used throughout (per `UI_PLAN.md` §9): Strategy (movement patterns in `piece_rules.py`), State (`PieceState` + `MotionTracker`), Observer (`observers/move_log_observer.py`), Adapter (`io/` text ⟷ `Board`), Facade (`Controller` as the sole UI→engine entry point), and Dependency Injection throughout (clock, motion tracker, arbiter, sprite lookups all injectable for testing).
- **Boundary discipline**: `input/`, `view/`, `driver/` never import `engine`/`model`/`rules`/`realtime` internals directly — only `Controller` and `GameState` snapshots cross that line.
- **Git history** shows organic, incremental development matching `UI_PLAN.md`'s described build order almost exactly: text-fixture parsing → click/wait/print commands → movement patterns → blockers/capture → pawn rules → real-time movement → advanced real-time interactions → game-over → advanced pawn rules → jump feature → refactor → package restructure → logic features → UI.
- Current branch `refactor/kungfu-chess-architecture` is the branch on which `UI_PLAN.md` and the current architecture were written; it is the best source for the "why" behind design decisions and should be treated as a living decision record rather than a historical artifact.