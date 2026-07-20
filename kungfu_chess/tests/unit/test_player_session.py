from kungfu_chess.input.player_session import PlayerSession


def test_claiming_a_new_color_appends_it():
    session = PlayerSession()
    session.claim("w")
    assert session.claimed_colors() == ["w"]


def test_claiming_an_already_claimed_color_is_a_no_op():
    session = PlayerSession()
    session.claim("w")
    session.claim("w")
    assert session.claimed_colors() == ["w"]


def test_claim_order_is_preserved():
    session = PlayerSession()
    session.claim("b")
    session.claim("w")
    assert session.claimed_colors() == ["b", "w"]


def test_claimed_colors_returns_a_defensive_copy():
    session = PlayerSession()
    session.claim("w")
    snapshot = session.claimed_colors()
    snapshot.append("b")
    assert session.claimed_colors() == ["w"]