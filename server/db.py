"""SQLAlchemy models + engine/session management for the `users` table
(Stage 3 - see KFChess_Server_Plan.md). This module owns *all* database
access - auth.py/rating.py never construct their own queries or
sessions, they only call the functions below. Swapping the underlying
database engine later (Postgres, MySQL, ...) means changing
config.DB_PATH's connection URL, not rewriting this file (same
"don't hardcode to one implementation" principle as the project's
board/piece-representation extensibility guidance, applied to storage).
"""

from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from server import config

Base = declarative_base()

# Named once here (Sec 7 DRY) rather than re-typed as bare "win"/"loss"/
# "draw" literals in rating.py, which passes one of these into
# update_after_game.
OUTCOME_WIN = "win"
OUTCOME_LOSS = "loss"
OUTCOME_DRAW = "draw"

OUTCOME_COLUMNS = {OUTCOME_WIN: "wins", OUTCOME_LOSS: "losses", OUTCOME_DRAW: "draws"}


class User(Base):
    __tablename__ = "users"

    username = Column(String, primary_key=True)
    password_hash = Column(String, nullable=False)
    rating = Column(Integer, nullable=False, default=config.INITIAL_RATING)
    games_played = Column(Integer, nullable=False, default=0)
    wins = Column(Integer, nullable=False, default=0)
    losses = Column(Integer, nullable=False, default=0)
    draws = Column(Integer, nullable=False, default=0)


def create_session_factory(db_url=None):
    """Real engine + session-factory construction - the injectable seam
    other modules accept a `session` for, instead of building their own
    (see auth.py's AuthService, rating.py's RatingService). `db_url`
    defaults to config.DB_PATH; tests pass "sqlite:///:memory:" instead -
    a real SQLAlchemy engine, not a hand-rolled fake, mirroring how
    GameEngine's own tests use real deterministic collaborators rather
    than Fake classes.
    """
    engine = create_engine(db_url if db_url is not None else config.DB_PATH)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def get_user(session, username):
    return session.get(User, username)


def create_user(session, username, password_hash):
    session.add(User(username=username, password_hash=password_hash, rating=config.INITIAL_RATING))
    session.commit()


def update_after_game(session, username, new_rating, outcome):
    """Persist the result of one finished game for `username`: the new
    rating, plus one game towards games_played and the matching
    win/loss/draw counter - all in one commit.
    """
    user = get_user(session, username)
    user.rating = new_rating
    user.games_played += 1
    column = OUTCOME_COLUMNS[outcome]
    setattr(user, column, getattr(user, column) + 1)
    session.commit()