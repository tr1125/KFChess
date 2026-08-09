from server import db


def make_session():
    return db.create_session_factory("sqlite:///:memory:")()


# --- schema / get_user ---

def test_get_user_returns_none_for_an_unknown_username():
    session = make_session()
    assert db.get_user(session, "alice") is None


def test_create_user_then_get_user_returns_defaults():
    session = make_session()
    db.create_user(session, "alice", "hashed-password")

    user = db.get_user(session, "alice")
    assert user.username == "alice"
    assert user.password_hash == "hashed-password"
    assert user.rating == 1200  # config.INITIAL_RATING
    assert user.games_played == 0
    assert user.wins == 0
    assert user.losses == 0
    assert user.draws == 0


# --- update_after_game ---

def test_update_after_game_win_sets_rating_and_increments_wins():
    session = make_session()
    db.create_user(session, "alice", "hash")

    db.update_after_game(session, "alice", 1216, "win")

    user = db.get_user(session, "alice")
    assert user.rating == 1216
    assert user.games_played == 1
    assert user.wins == 1
    assert user.losses == 0
    assert user.draws == 0


def test_update_after_game_loss_sets_rating_and_increments_losses():
    session = make_session()
    db.create_user(session, "alice", "hash")

    db.update_after_game(session, "alice", 1184, "loss")

    user = db.get_user(session, "alice")
    assert user.rating == 1184
    assert user.games_played == 1
    assert user.losses == 1


def test_update_after_game_draw_sets_rating_and_increments_draws():
    session = make_session()
    db.create_user(session, "alice", "hash")

    db.update_after_game(session, "alice", 1200, "draw")

    user = db.get_user(session, "alice")
    assert user.rating == 1200
    assert user.games_played == 1
    assert user.draws == 1


def test_update_after_game_accumulates_across_multiple_games():
    session = make_session()
    db.create_user(session, "alice", "hash")

    db.update_after_game(session, "alice", 1216, "win")
    db.update_after_game(session, "alice", 1200, "loss")

    user = db.get_user(session, "alice")
    assert user.rating == 1200
    assert user.games_played == 2
    assert user.wins == 1
    assert user.losses == 1


# --- restart-durable persistence (the one thing :memory: can't prove) ---

def test_data_survives_reopening_the_same_file_backed_database(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'test.db'}"

    session = db.create_session_factory(db_url)()
    db.create_user(session, "alice", "hash")
    db.update_after_game(session, "alice", 1216, "win")
    session.close()

    # A brand-new engine/session on the same file, as if the server had
    # been restarted - config.DB_PATH is what production points at a
    # real file for exactly this reason (see Stage 3 acceptance
    # criteria: "restarting the server does not lose accounts or ratings").
    reopened_session = db.create_session_factory(db_url)()
    user = db.get_user(reopened_session, "alice")
    assert user is not None
    assert user.rating == 1216
    assert user.wins == 1