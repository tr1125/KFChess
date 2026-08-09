"""Named constants for the server (see KFChess_Server_Plan.md Sec 7's DRY
rule: every constant that affects behavior lives here exactly once, never
re-typed as a bare literal in business logic).
"""

WS_HOST = "localhost"
WS_PORT = 8765

# No accounts/persistence yet (that's Stage 3) - used as a placeholder
# rating in login_ok until real per-user ratings exist.
INITIAL_RATING = 1200

# Stage 2 has exactly one hardcoded room (no room management yet - that's
# Stage 5's job). ROOM_ID is a placeholder used only in the game_started
# message until real room IDs exist.
ROOM_ID = "local"
MAX_PLAYERS_PER_ROOM = 2

# How often the room's engine clock is advanced in real time (see
# rooms.py's tick_loop) - independent of and much finer-grained than any
# single move's duration, so in-flight legs settle promptly.
TICK_INTERVAL_MS = 50

# ELO update (see server/rating.py) - fixed for every player/game, never
# tiered by rating or experience (Stage 3).
K_FACTOR = 32

# SQLAlchemy connection URL (not a bare file path) - see server/db.py.
# Swapping the underlying database engine later means changing this URL,
# not rewriting db.py's query logic.
DB_PATH = "sqlite:///kfchess.db"

# Generic login-failure reason - deliberately the same whether the
# username doesn't exist or the password is wrong, so a client can never
# tell which (see server/auth.py.AuthError).
LOGIN_FAILURE_REASON = "invalid username or password"