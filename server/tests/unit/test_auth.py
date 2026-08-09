import pytest

from server import config, db
from server.auth import AuthError, AuthService


def make_service():
    session = db.create_session_factory("sqlite:///:memory:")()
    # A low bcrypt cost factor keeps these tests fast - still the real
    # bcrypt library, not a fake, per KFChess_Server_Plan.md Sec 8.
    return AuthService(session, rounds=4), session


def test_first_login_auto_creates_the_account_at_initial_rating():
    auth_service, session = make_service()

    rating = auth_service.login("alice", "hunter2")

    assert rating == config.INITIAL_RATING
    user = db.get_user(session, "alice")
    assert user is not None
    assert user.password_hash != "hunter2"  # never stored as plaintext


def test_correct_password_on_an_existing_account_returns_the_stored_rating():
    auth_service, session = make_service()
    auth_service.login("alice", "hunter2")
    db.update_after_game(session, "alice", 1350, "win")

    rating = auth_service.login("alice", "hunter2")

    assert rating == 1350


def test_wrong_password_raises_a_generic_auth_error():
    auth_service, _session = make_service()
    auth_service.login("alice", "hunter2")

    with pytest.raises(AuthError) as excinfo:
        auth_service.login("alice", "wrong-password")

    # The message must never reveal whether the username exists or the
    # password was wrong - always the same generic text.
    assert str(excinfo.value) == config.LOGIN_FAILURE_REASON