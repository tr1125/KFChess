# KFChess Server — Staged Implementation Plan

This document is the build order for turning KFChess from a single-process local desktop
game into a networked, multiplayer, rated game with accounts, matchmaking, and rooms.
It assumes the codebase and conventions described in the project's `ABOUT.md`
(flat `kungfu_chess/` package, strict boundary discipline, `Controller` as the sole
Facade into `GameEngine`, `GameState` as a pure read-only snapshot).

Every decision below was explicitly confirmed with the project owner. Nothing in this
document should be re-litigated or "improved" during implementation without checking
back — if something is ambiguous, stop and ask rather than guessing.

---

## 0. Global Conventions (apply to every stage)

These are fixed choices that affect the whole project. Treat them as settled.

| Decision | Value |
|---|---|
| Server transport | Python `websockets` library (asyncio-based). No web framework. |
| Wire protocol | JSON envelope: `{"type": "<event_name>", "payload": {...}}` on every message, both directions. |
| Bus subscriber model | `async def` subscribers (coroutines), matching `websockets`' asyncio model. |
| Server process model | Single process, single Python program, handles all rooms/connections concurrently via asyncio. |
| Client codebase | One client entry point (extended `app_ui.py`), parameterized by `--color` (or equivalent), not two separate client files. |
| Board orientation | Flips per player's color (like chess.com) — each player's own pieces render at the bottom of their own screen. |
| Offline / local-only mode | **Removed.** The client always connects to a server (even a `localhost` one during dev). No dual code path for "local GameEngine" vs "remote via Controller". |
| Login | Terminal (`input()`) prompt, run before the OpenCV window opens. Not a full text-mode client — just the login step is shell-based. |
| Starting rating | `INITIAL_RATING = 1200`, defined as a single named constant, trivially changeable in code. |
| ELO formula | Standard: `E_A = 1 / (1 + 10 ** ((R_B - R_A) / 400))`; `R_A' = R_A + K * (S_A - E_A)`. |
| K-factor | Fixed `K = 32` for every player, every game. **Not** tiered by rating or experience. |
| Draw / tie support | **Being added to the engine** (currently doesn't exist). Trigger: **King vs King only** (no other side has any non-king piece left). No other automatic draw condition. |
| Draw scoring | `S = 0.5` for both players in the ELO formula when a draw occurs. |
| Out of scope (explicitly, do not build) | Draw by player agreement/offer. Any "insufficient material" case beyond bare K-v-K (no K+B v K, K+N v K, etc.). Any stagnation/move-limit/timeout-based draw. Tiered K-factor. Reconnection support beyond the one 20s disconnect window (see §5). |
| Color assignment — matchmaking (Stage 4) | **Deterministic, not random.** Whoever joined the matchmaking queue **first** (of the two players being matched) is White; the other is Black. Same underlying rule as Stage 2/3 and Rooms — "whoever was there first is White" — just using queue arrival order instead of room creation as the tie-break. No coin flip anywhere in this project. |
| Color assignment — Stage 2/3 baseline, and Rooms (Stage 5) | First player to join / room creator is **White**, second player / first person to join the room is **Black** — per the slide's explicit wording ("the second person that joins the room is the Black player"). |
| Room ID format | Short human-typeable code, 6 characters (letters+digits), not a UUID. |
| Logs (client + server) | Plain text, one line per event, human-readable timestamp prefix — not JSON lines. |
| Disconnect handling | See §5 in detail. Game **freezes** (neither player can move) during the 20s grace window. Reconnect within 20s → game resumes exactly as it was. No reconnect within 20s → game ends, disconnected player auto-resigns. |
| Password storage | Hashed (bcrypt or argon2) — never plaintext, even though the source slides didn't call this out explicitly. |

### Assumption flagged for confirmation
Whether a game played inside a private **Room** affects players' `rating` the same way
a matchmade game does was never explicitly settled. This plan assumes **yes, rooms are
rated the same as matchmaking** unless told otherwise — flag this back to the project
owner before Stage 5 is finalized.

---

## 1. New top-level `server/` package

Sibling to `kungfu_chess/`, keeping the existing package untouched wherever possible.
Suggested modules (create incrementally, stage by stage — don't build all of this in Stage 1):

```
server/
  config.py          # INITIAL_RATING, K_FACTOR, MATCH_RANGE, MATCH_TIMEOUT_SEC,
                      # DISCONNECT_GRACE_SEC, ROOM_ID_LENGTH — all named constants, one place
  bus.py              # EventBus: subscribe(topic, async_callback) / publish(topic, payload)
                      # one EventBus instance per room/game
  protocol.py         # encode/decode helpers for the {"type","payload"} envelope,
                      # one constant per message type (avoid magic strings elsewhere)
  ws_server.py        # entry point: starts the websockets server, accepts connections,
                      # routes incoming envelopes to the right room/session
  rooms.py            # Room/session manager: room_id -> {GameEngine, EventBus, sockets, players}
  matchmaking.py       # queue of waiting players + ELO-range matching logic (Stage 4)
  disconnect.py       # 20s grace-period timers, freeze/resume/resign logic (Stage 4)
  auth.py             # login/password verification against SQLite (Stage 3)
  db.py               # SQLite connection + schema (users table) (Stage 3)
  rating.py           # ELO update + K-v-K draw detection (Stage 3/draw logic)
  server_log.py       # thin config wrapper around Python's built-in `logging` module
                      # (Formatter for the timestamp prefix + FileHandler) — do not
                      # hand-roll file writes/timestamps, use the standard library
```

Client-side changes live in the existing `kungfu_chess/` tree (`app_ui.py`, `view/`,
`input/`, `driver/`) — see each stage below for what changes.

---

## 2. Wire Protocol Reference

All messages are JSON objects: `{"type": "...", "payload": {...}}`. Square names use the
existing `Position.square_name()` convention already in `model/position.py` (e.g. `"e2"`).

| type | direction | payload | introduced in |
|---|---|---|---|
| `login` | client→server | `{"username", "password"}` (Stage 3; Stage 2 has no `password` field) | Stage 2/3 |
| `login_ok` | server→client | `{"username", "rating"}` | Stage 2/3 |
| `login_error` | server→client | `{"reason"}` | Stage 2/3 |
| `move_started` | server→client | `{"color", "kind", "from", "to", "duration_ms"}` — sent once when a leg begins; client runs its own local glide animation for `duration_ms` from receipt, no further messages needed mid-flight | Stage 2 |
| `move` | client→server | `{"from", "to"}` | Stage 2 |
| `jump` | client→server | `{"square"}` | Stage 2 |
| `promote` | client→server | `{"square", "piece_type"}` — overrides the auto-Queen default; calls the existing (already-tested) `choose_promotion`/`apply_promotion_choice` on the server's `Controller`. Preserves the local promotion-menu popup feature over the network unchanged. | Stage 2 |
| `state` | server→client | full `GameState` snapshot (board, scores, move log, pending promotions) | Stage 2 |
| `game_started` | server→client | `{"white", "black", "room_id"}` | Stage 2 |
| `game_ended` | server→client | `{"result": "white_wins"/"black_wins"/"draw", "reason": "capture"/"resign"/"disconnect_timeout"/"insufficient_material", "rating_changes": {...}}` | Stage 2 (result), Stage 3 (rating_changes) |
| `play` | client→server | `{}` — join matchmaking queue | Stage 4 |
| `cancel_play` | client→server | `{}` — leave queue | Stage 4 |
| `queue_status` | server→client | `{"waiting_seconds"}` | Stage 4 |
| `no_opponent_found` | server→client | `{}` | Stage 4 |
| `opponent_disconnected` | server→client | `{"seconds_left"}` (ticks down) | Stage 4 |
| `opponent_reconnected` | server→client | `{}` | Stage 4 |
| `create_room` | client→server | `{}` | Stage 5 |
| `room_created` | server→client | `{"room_id"}` | Stage 5 |
| `join_room` | client→server | `{"room_id"}` | Stage 5 |
| `join_error` | server→client | `{"reason": "room_not_found"}` | Stage 5 |
| `joined_as_spectator` | server→client | `{"room_id"}` | Stage 5 |

Add new types here as needed during implementation — keep this table in sync with the code.

---

## Stage 1 — Pub/Sub Bus (local refactor, no networking yet)

**Goal:** introduce an explicit event bus into the existing local engine, replacing
ad-hoc direct calls with publish/subscribe, so the future server has something to
subscribe to instead of reaching into `GameEngine` internals.

**Scope:**
- Implement `server/bus.py`: `EventBus` with `subscribe(topic: str, callback: Callable[[dict], Awaitable[None]])` and `async publish(topic: str, payload: dict)`.
- One `EventBus` instance per game (later: per room).
- Topics: `move_started`, `move_made`, `score_updated`, `game_started`, `game_ended`. (No separate `sound` topic — client derives sound cues from these same events.)
- `move_started` fires the instant a leg begins (mirrors the existing settlement call sites but at the *start* of a leg instead of the end — added as a small addendum to this stage's event-buffering work, using the exact same `_pending_events`/`drain_events()` mechanism, not a new mechanism). Payload: piece color/kind, from-square, to-square, `duration_ms` for this leg. This exists specifically so Stage 2's client can animate smooth gliding over the network by running its *own* local interpolation timer from the moment it receives this message, instead of the server needing to broadcast full state on a tick (see Stage 2).
- Wire the existing local engine's known trigger points (score changes, move completions, game start/end) to `publish()` calls instead of direct calls into the panel/observer.
- The existing `observers/move_log_observer.py` pattern is the closest analog — extend/replace it to subscribe to the bus rather than being called directly, if that doesn't break existing tests.

**Acceptance criteria:**
- All 528 existing tests still pass unmodified (or with only mechanical updates, no behavior changes).
- A new unit test proves: publishing to a topic invokes all subscribers with the right payload; unsubscribed topics don't crash if published with no subscribers.
- No networking code yet — this stage is purely internal plumbing.

---

## Stage 2 — Single-Process WebSocket Server + Networked Client

**Goal:** two `app_ui.py` clients (one `--color white`, one `--color black`) talk to each
other only through a shared server process over WebSockets. No accounts yet — first
client to connect is White, second is Black, exactly two players supported, everyone else
rejected.

**Server side (`server/ws_server.py`, `server/rooms.py`, `server/protocol.py`):**
- Single hardcoded "room" (no room management yet — that's Stage 5).
- Accepts exactly 2 connections; a 3rd connecting client gets an error and is dropped (no spectators yet).
- On connect: prompt via `login` message with just `{"username"}` (no password check yet — any username accepted).
- Assign color by join order (first = White, second = Black), consistent with §0.
- Translate incoming `move`/`jump` envelopes into calls on a server-side `Controller` instance wrapping `GameEngine`.
- On every `move_started`/`move_made`/`score_updated`/`game_started`/`game_ended` bus event (from Stage 1's bus), broadcast the matching message to both connected clients.
- **Animation approach (deliberate choice, not a periodic tick):** `move_started` is sent once per leg, at the start. The client uses it to run its *own* local glide animation for `duration_ms` (reusing the exact interpolation logic the local single-player renderer already has), rather than the server broadcasting full state repeatedly during the flight. This is both smoother (matches today's local feel) and far cheaper on the wire than a tick-based broadcast (one message per leg, not 20–30/sec). `state` messages (on settlement events) remain the authority for final/resting positions and anything else (captures, scores).
- Server owns the only `GameEngine`/`Controller` instance — it is the sole source of truth.

**Client side (`app_ui.py`, `driver/`, `view/`):**
- Add `--color {white,black}` argument (or equivalent CLI flag).
- Remove local `GameEngine` instantiation entirely (per §0, no offline mode) — client only ever talks to a `Controller`-like object that forwards `click`/`jump` to the server via WS and receives `state` broadcasts to re-render.
- `view/renderer.py` (or wherever board layout is computed): flip orientation when `--color black` is passed, so the player's own pieces render at the bottom.
- Client still reads `GameState`-shaped data purely for rendering (unchanged boundary discipline) — only the *source* of that data changes from local engine to deserialized server message.

**Acceptance criteria:**
- Two client processes on the same machine, pointed at the same local server, can play a full game to king-capture, each seeing the other's moves reflected live.
- Board is visually flipped on the Black client relative to the White client.
- A 3rd connection attempt is cleanly rejected with a clear message, not a crash.
- **Color authorization is actually enforced, not just assigned.** The White-assigned socket's `move`/`jump`/`promote` requests are rejected (or silently ignored) if they target a Black piece, and vice versa. This was flagged as a known gap all the way back in `ABOUT.md` (`PlayerSession... claims a color per player (not yet enforced)`) — it must be a real server-side check now that two independent, untrusted client processes exist, not an assumption. Test this explicitly: confirm from a live White client, attempting to move a Black piece has no effect.

---

## Stage 3 — Accounts (SQLite) + Rating + Draw Logic

**Goal:** persistent accounts with hashed passwords, and a real ELO rating that updates
after every game (including the new draw case).

**Server side (`server/db.py`, `server/auth.py`, `server/rating.py`):**
- **Database access goes through SQLAlchemy — not raw `sqlite3` calls or hand-written SQL strings.** The storage engine is still SQLite (a local file, per the original requirement), but `db.py` must talk to it via SQLAlchemy (either the ORM with a declarative `User` model, or SQLAlchemy Core with a `Table` definition — either is fine, pick one and be consistent). The point: swapping the underlying database engine later (Postgres, MySQL, whatever) should mean changing a connection URL in `server/config.py`, not rewriting `db.py`'s query logic. This is the same "don't hardcode to one implementation" principle as §6's extensibility guidance, applied to storage instead of board representation. `db.py` still owns *all* database access — `auth.py`/`rating.py` never construct their own queries/sessions — same DRY/SRP boundary as before, just expressed through SQLAlchemy instead of raw SQL. Add `sqlalchemy` to `requirements.txt`. `config.py`'s `DB_PATH` becomes a SQLAlchemy connection URL (e.g. `sqlite:///kfchess.db`; tests use `sqlite:///:memory:`) rather than a bare file path.
- Schema (single `users` table, defined via SQLAlchemy — this is illustrative of the columns/types/defaults needed, not literal SQL to paste in):

```sql
CREATE TABLE users (
    username      TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    rating        INTEGER NOT NULL DEFAULT 1200,  -- = config.INITIAL_RATING
    games_played  INTEGER NOT NULL DEFAULT 0,
    wins          INTEGER NOT NULL DEFAULT 0,
    losses        INTEGER NOT NULL DEFAULT 0,
    draws         INTEGER NOT NULL DEFAULT 0
);
```

- `login` now requires `{"username", "password"}`; verify against `password_hash` using bcrypt/argon2 (never plaintext, never plain equality check).
- New username on first login → create row with `INITIAL_RATING` (1200), or require an explicit register step if that's cleaner — pick whichever is simpler to implement, note the choice in code comments.
- `server/rating.py`:
  - Implement the ELO update from §0 exactly, `K_FACTOR = 32` from `server/config.py`.
  - Implement **K-v-K draw detection**: after every move settles, check the board — if the only pieces remaining are the two kings, immediately end the game with `result: "draw"`, `reason: "insufficient_material"`, apply `S = 0.5` to both players' ratings.
  - **Implementation pattern (discovered during Stage 3 build, keep for Stage 4):** several existing test fixtures across `kungfu_chess/tests/` are bare King-vs-King boards used to test unrelated things. Do **not** wire K-v-K detection into `GameEngine`/`RuleEngine`'s automatic settle path — that would make those tests freeze on their first move. Instead, add an additive `GameEngine.force_draw()` method (mirrors the existing king-capture-ends-game mechanism) that only `Room` calls, only after explicitly checking the board via a pure `server/rating.py` helper. Same pattern applies to Stage 4's disconnect-timeout resignation — that's also an externally-triggered game end, not a capture the engine detects on its own, so it should follow this same "additive engine method, externally triggered" shape rather than being pushed into the engine's automatic path.
  - On any `game_ended` bus event, compute and persist the new ratings to SQLite, and increment `games_played`/`wins`/`losses`/`draws` accordingly. Include the resulting `rating_changes` in the `game_ended` message sent to clients.

**Client side:**
- Shell login prompt now asks for both username and password (`input()` for username, a masked prompt e.g. `getpass` for password).
- Display own current rating somewhere in the side panel (extend `view/side_panel_view.py`) after `login_ok`.

**Acceptance criteria:**
- Restarting the server does not lose accounts or ratings (SQLite persists to disk).
- Wrong password is rejected with `login_error`, doesn't leak whether the username exists vs. password is wrong (generic "invalid username or password").
- A test game reduced to bare kings ends automatically as a draw, and both players' ratings move toward each other correctly per the ELO formula with `K=32`.
- A won/lost game updates the winner's and loser's ratings per the standard formula (verify against the worked example in this doc's history: 1500 vs 1500, winner → 1516, loser → 1484, with K=32).

---

## Stage 4 — Matchmaking ("Play" button) + Disconnect Handling

**Goal:** replace the "first join = White" pairing with real ELO-based matchmaking, and
handle mid-game disconnects gracefully.

**Matchmaking (`server/matchmaking.py`):**
- `play` message enters the caller into a single waiting queue (with their `username`/`rating`).
- Continuously (e.g., check whenever the queue changes, or on a short periodic tick): if any two waiting players are within `MATCH_RANGE = ±100` rating of each other, match them **immediately** — don't wait for the timeout.
- Track each waiting player's own wait time. If a player has waited `MATCH_TIMEOUT_SEC = 60` seconds with **still no one in the ±100 range**, send `no_opponent_found` and remove them from the queue (they'd need to click Play again).
  - **No fallback matching outside the range.** This follows the slide literally: *"waits for 1 min, if can't find - pops up a message that can't find"* — there is no wording anywhere about widening the range or matching with the closest available player regardless of range. Do not implement a nearest-available fallback here, even though it would arguably be friendlier UX.
- On match: assign colors **deterministically** — whichever of the two players joined the queue **first** is White, the other is Black (§0) — create a new room via `server/rooms.py`, send `game_started` to both.
- `cancel_play` removes the caller from the queue before a match is found.

**Disconnect handling (`server/disconnect.py`):**
- Use the `websockets` library's built-in ping/pong keepalive (`ping_interval`/`ping_timeout`) to detect a dropped connection rather than only relying on a clean close event.
- On detecting a drop mid-game: **freeze the game** (reject/queue any `move`/`jump` from the remaining player while frozen), start a 20s (`DISCONNECT_GRACE_SEC`) timer, and send `opponent_disconnected` with a ticking `seconds_left` to the still-connected player.
- If the disconnected player's client re-establishes a WS connection within the 20s window (matched back to their in-progress room via their session — e.g. re-send `login` and the server recognizes they have an active room), **unfreeze and resume exactly where the game was** — no state was lost since it was frozen. Send `opponent_reconnected` to the other player.
- If 20s elapse with no reconnection: end the game as a resignation (`game_ended`, `reason: "disconnect_timeout"`, the disconnected player counted as the loser), apply the ELO update via Stage 3's rating logic exactly as any other loss.

**Client side:**
- Home screen gains a "Play" button; while queued, show waiting time / a friendly "searching…" state; render `no_opponent_found` as a clear message with the option to try again.
- Render `opponent_disconnected`'s countdown visibly (e.g. in the side panel) and clear it on `opponent_reconnected` or `game_ended`.

**Acceptance criteria:**
- Two clients with ratings within 100 of each other are matched near-instantly.
- A client waiting alone for 60s with no other player at all gets `no_opponent_found`.
- A client waiting 60s with only an out-of-range opponent available also gets `no_opponent_found` at the 60s mark — it is **not** matched with them, regardless of how close they are outside the ±100 range.
- Killing one client's network mid-game freezes the other client's board; reconnecting within 20s resumes seamlessly; not reconnecting within 20s ends the game with the correct rating change.

---

## Stage 5 — Rooms (Create/Join) + Spectators + Logging

**Goal:** let two specific people (e.g. friends) play each other directly via a shared
room code, with anyone else who joins becoming a read-only spectator, and persist an
activity log on both sides.

**Server side (`server/rooms.py`):**
- `create_room` generates a new room ID: 6-character alphanumeric code (per §0), creates an empty room, sends `room_created` with the code back to the creator.
- `join_room` with a given `room_id`:
  - If room doesn't exist: `join_error` with `reason: "room_not_found"`.
  - If this is the **first** person to join after the creator: they become the opponent. Color assignment is **deterministic, not random**, per the slide's explicit wording: the room **creator is White**, the **first person to join is Black** (§0). Send `game_started` to both.
  - Any subsequent joiner to that room: `joined_as_spectator` — they receive `state` broadcasts (read-only) but any `move`/`jump` they send is rejected.
- Room games use the same `EventBus`, `Controller`/`GameEngine`, matchmaking-independent — treat exactly like a matchmade game for rating purposes (per the flagged assumption in §0) once it ends.

**Logging (`server/server_log.py` + client-side equivalent):**
- Use Python's built-in `logging` module on both sides — do not hand-roll file writes or
  timestamp formatting. Configure one `Formatter` for the `[YYYY-MM-DD HH:MM:SS]`-style
  prefix, attach a `FileHandler` pointing at the log file, and get a named logger per
  module (e.g. `logging.getLogger("server.rooms")`, `logging.getLogger("server.matchmaking")`)
  so each log line shows which part of the system produced it.
- Plain text, one line per event, e.g.:
  `[2026-07-21 14:03:41] room=AB3XZ9 white=alice black=bob move e2->e4`
- Log at minimum: connections/disconnections, logins, moves, game start/end (with result and reason), room create/join/spectate events.
- Server writes its log file; the client independently writes its own log of what it sent/received (also via `logging`, its own `FileHandler`) — the two logs don't need to be merged, just both present for comparison purposes.

**Client side:**
- Home screen gains a "Room" button opening a small dialog: text box + Create / Join / Cancel, matching the original spec.
- Room ID is displayed prominently at the top of the screen for both the creator (immediately) and joiner (after joining).
- Spectator clients render the board read-only (no click handling forwarded as moves).

**Acceptance criteria:**
- Creating a room and joining it from a second client starts a game with the creator as White and the joiner as Black (deterministic, not random).
- A third client joining the same room becomes a spectator, sees live board updates, and cannot move pieces.
- Both server and client log files contain a coherent, readable trail of a full game session.
- Room games update rating exactly like matchmade games (or: this is flagged to the project owner if that assumption turns out to be wrong).

---

## 6. Extensibility Guidance (Lecturer Hints — Do NOT Implement, Just Don't Block)

The lecturer's emails flagged two future directions. Neither is to be built now. The
requirement is architectural only: make sure nothing added in Stages 1–5 makes these
structurally harder later, and be ready to explain the approach if asked.

**6.1 Binary board/piece representation (memory optimization, hinted "rumor")**
- This project already has the right seam for this: `io/board_parser.py` /
  `io/board_printer.py` are the Adapter boundary between `Board`'s internal storage and
  any external representation (today: the `.kfc` text format).
- Rule for all new server code: nothing outside `model/`, `rules/`, and `io/` may read
  `board.grid` (or a `Piece`'s internal attributes) directly. When building the `state`
  WS message, add **one** serialization function (e.g. `server/state_serializer.py`, or
  extend `io/`) that turns a `GameState` snapshot into the wire payload. If board/piece
  storage ever becomes binary, only that one function (plus `io/board_parser.py`/
  `board_printer.py`) would need to change — not `ws_server.py`, `rooms.py`, or any
  client code.
- Explain-on-demand answer: "our board/piece internals are already opaque outside
  model/rules/io; switching to binary storage means rewriting the io/ adapters and our
  one state-serializer function, nothing else."

**6.2 User-defined piece/game rules ("Kung Fu Chess Shlomi-style")**
- Movement is already a Strategy pattern, fully config-driven
  (`rules/piece_rules.py`: `Step`/`Slide`/`PawnDoubleStep`, occupancy rules, promotions).
- Rule for all new server code: never hardcode piece-kind checks (no
  `if kind == "Q"`, no `piece_type in ["Q","R","B","N"]` embedded in server logic).
  Treat `piece.kind` as an opaque string key everywhere — the same discipline the
  existing renderer already follows (`ABOUT.md`: "the renderer only ever reads
  `piece.color`/`.kind`/`.state.name`"). Anywhere the server needs the list of legal
  piece kinds (e.g. promotion choices), read it from config
  (`promotion_menu_config.json`'s `choice_order`), never from a literal list in code.
- Explain-on-demand answer: "adding a new piece with custom movement today only means
  adding a new entry to `rules/piece_rules.py`'s config and a sprite folder — no engine,
  server, or view code needs to change, because movement dispatch is keyed by config,
  not by hardcoded piece-type branches."
- Not building: no game-design UI, no way for a user to actually author a variant yet.
  Only confirming the current design doesn't block it.

**6.2.1 Explain-on-demand: how a ruleset would be agreed between two real opponents**
There is always exactly **one** `GameEngine` per match, configured **once**, before the
match starts — never negotiated mid-game, never two engines reconciling. How "once,
before the match" gets decided differs by how the match was formed:
- **Rooms:** no conflict exists — the room creator's chosen ruleset (if any) is set when
  the room is created; anyone who joins is joining *into* that already-decided config,
  the same way they're joining into an already-decided color (§0).
- **Matchmaking:** two strangers arrive independently, so there's no room creator — but
  there's still a natural tie-break, the same one used for color (§0): whichever of the
  two players **joined the matchmaking queue first** is authoritative — their requested
  config (if any) applies to the match, exactly as they're also the one who gets White.
  "First in queue" decides both together, consistently, with the same rule. The
  `game_started` message communicates the effective settings to both clients — the
  later-arriving player's own preference simply doesn't apply to this particular match.
  No negotiation UI, no "rejected" message, and critically: **no randomness anywhere in
  this project** — every tie-break is "whoever was there first."
- None of this is implemented now — it's the answer to have ready if asked how it would
  work, per the lecturer's "don't implement, don't block" instruction in §6.2.

**6.3 One-time audit action (do this, it's small)**
- Grep the existing codebase for literal `8` used as a board dimension (in
  `model/board.py`, `rules/piece_rules.py`, boundary/`in_bounds()` checks, anywhere
  movement math assumes an 8×8 board). Boundary checks should read the `Board`
  instance's actual row/column count, not a hardcoded literal.
- Grep for any hardcoded piece-kind lists (e.g. `["Q","R","B","N"]`) embedded directly
  in control-flow logic (as opposed to read from `promotion_menu_config.json` or
  `piece_rules.py`'s config). Move any you find into config.
- This is a quick verification pass, not new functionality — if everything already
  reads from the `Board` instance / config, there's nothing to change. Note the
  findings either way so it's clear this was checked.
- **Board size and custom piece rules are explicitly NOT being built as user-facing
  features in this project.** No UI, no protocol messages, no per-room configurable
  board dimensions. This section exists purely so the codebase doesn't structurally
  block that hypothetical future work — nothing more.

---

## 7. Code Quality Checklist (apply to every new `server/` module)

Per the lecturer's "code smells" guidance — check every new module against these before
considering a stage done:

| Principle | What it means here |
|---|---|
| **DRY** | Every constant (K=32, ±100 range, 60s/20s timeouts, room ID length, INITIAL_RATING) is defined exactly once in `server/config.py`. Every message-type string is defined exactly once in `server/protocol.py`. Never re-type the same literal in two files. |
| **SRP** | One concern per module: `matchmaking.py` only matches players, `disconnect.py` only handles grace-period timers, `rating.py` only computes ELO, `rooms.py` only tracks room membership. `ws_server.py` should be thin — it routes incoming envelopes to the right module, it doesn't contain matchmaking/rating/disconnect logic itself. |
| **No hardcoded constants/strings in business logic** | Anything that affects behavior (timeouts, thresholds, sizes) lives in `server/config.py`, referenced by name — never a bare number/string dropped into an `if` statement. |
| **Encapsulation** | E.g. `rooms.py`'s internal `room_id → room state` mapping is never reached into directly by `ws_server.py` or `matchmaking.py` — they call methods (`get_room(id)`, `create_room()`) and never assume the internal shape of that data structure. Same discipline for `matchmaking.py`'s internal queue, `disconnect.py`'s internal timer state, etc. |

---

## 8. Testing & Process Requirements (per lecturer's email)

- Aim for as close to 100% unit test coverage as possible on every new `server/` module.
  Generate an HTML coverage report (the project already has `.coveragerc` /
  `coverage run -m pytest && coverage html` conventions — extend `source=` to include
  `server` alongside `kungfu_chess`).
- Use dependency injection for anything that needs faking in tests — mirrors the
  existing pattern (`GameEngine` takes an injectable clock/motion/arbiter,
  `SpriteRegistry` takes injectable `listdir`/`read_config`). Concretely: inject a fake
  clock into `disconnect.py`'s grace-timer logic, a fake RNG into color assignment and
  room-ID generation, a fake DB connection into `auth.py`/`rating.py`, a fake transport
  into anything that would otherwise need a real WebSocket to test.
- **No monkey-patching in tests, ever** — this was called out explicitly and strongly in
  the lecturer's email as unacceptable. If a module seems to require monkey-patching to
  test, that's a signal it's missing a proper DI seam — fix the module, don't patch
  around it.
- Add a comment at the top of the server's main entry file (wherever
  `if __name__ == "__main__"` lives) with the git repo URL, per the lecturer's request.

---

## Suggested Build Order Recap

1. Bus (local refactor only, existing tests must still pass)
2. WS server + 2-client networked play, no accounts
3. SQLite accounts + password + rating + K-v-K draw
4. Matchmaking queue + disconnect/reconnect handling
5. Rooms + spectators + logging

Each stage should be a separate, reviewable chunk of work — don't blend stages together
even if it seems more efficient, since each one has its own acceptance criteria above.

Sections 6–8 (extensibility guidance, code quality, testing/process) are not a stage —
they're standing constraints that apply continuously across all five stages above.
Re-check them at the end of every stage, not just once at the end of the project.
