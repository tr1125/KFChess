from kungfu_chess.model.piece import (
    Piece,
    PieceState,
    KING_TYPE,
    QUEEN_TYPE,
    ROOK_TYPE,
    BISHOP_TYPE,
    KNIGHT_TYPE,
    PAWN_TYPE,
    WHITE,
    BLACK,
)


def test_piece_stores_color_and_kind():
    piece = Piece(color="w", kind=KING_TYPE)
    assert piece.color == "w"
    assert piece.kind == KING_TYPE


def test_piece_defaults_to_idle_state():
    piece = Piece(color="w", kind=PAWN_TYPE)
    assert piece.state == PieceState.IDLE


def test_piece_auto_assigns_a_unique_id():
    first = Piece(color="w", kind=PAWN_TYPE)
    second = Piece(color="w", kind=PAWN_TYPE)
    assert first.id != second.id


def test_pieces_with_identical_fields_are_not_equal():
    """Two same-kind-same-color pieces are distinct entities, not
    interchangeable values - RealTimeArbiter relies on this to tell them
    apart (see test_real_time_arbiter.py).
    """
    first = Piece(color="w", kind=PAWN_TYPE)
    second = Piece(color="w", kind=PAWN_TYPE)
    assert first != second
    assert first == first


def test_piece_str_is_the_legacy_two_letter_form():
    assert str(Piece(color="w", kind=KING_TYPE)) == "wK"
    assert str(Piece(color="b", kind=PAWN_TYPE)) == "bP"


def test_piece_type_constants_are_single_letters():
    for constant in (KING_TYPE, QUEEN_TYPE, ROOK_TYPE, BISHOP_TYPE, KNIGHT_TYPE, PAWN_TYPE):
        assert isinstance(constant, str)
        assert len(constant) == 1


def test_color_constants_match_token_prefixes():
    assert WHITE == "w"
    assert BLACK == "b"
