"""Login/password verification against the `users` table (Stage 3 - see
KFChess_Server_Plan.md). Passwords are never stored or compared as
plaintext - always through a real hashing library (bcrypt).
"""

import bcrypt

from server import config, db


class AuthError(Exception):
    """Raised for any login failure. The message is always the generic
    "invalid username or password" text (config.LOGIN_FAILURE_REASON) -
    callers must never be able to tell an unknown username from a wrong
    password for a known one.
    """


class AuthService:
    def __init__(self, session, hasher=bcrypt, rounds=12):
        self._session = session
        self._hasher = hasher
        self._rounds = rounds

    def login(self, username, password):
        """Verify credentials, returning the account's current rating.

        A username seen for the first time is auto-created on the spot
        with config.INITIAL_RATING (chosen over a separate explicit
        register step - simpler, and needs no new protocol message type,
        matching how Stage 2's login already accepted any username
        unconditionally). Raises AuthError (generic message) for a wrong
        password on an existing account.
        """
        user = db.get_user(self._session, username)
        if user is None:
            password_hash = self._hasher.hashpw(
                password.encode("utf-8"), self._hasher.gensalt(self._rounds)
            )
            db.create_user(self._session, username, password_hash.decode("utf-8"))
            return config.INITIAL_RATING

        if not self._hasher.checkpw(password.encode("utf-8"), user.password_hash.encode("utf-8")):
            raise AuthError(config.LOGIN_FAILURE_REASON)

        return user.rating