from kungfu_chess.model.board import Board
from kungfu_chess.model.piece import Piece, PieceState
from kungfu_chess.model.position import Position
from kungfu_chess.model.game_state import GameState
from kungfu_chess.io.state_codec import to_wire_state, from_wire_state


def make_state():
    board = Board([[Piece(color="w", kind="K", cell=Position(0, 0)), None],
                   [None, Piece(color="b", kind="K", cell=Position(1, 1))]])
    state = GameState()
    state.attach_board(board)
    return state, board


def test_to_wire_state_serializes_the_board_by_color_kind_and_state():
    state, board = make_state()
    payload = to_wire_state(state)
    assert payload["board"] == [
        [{"color": "w", "kind": "K", "state": "IDLE"}, None],
        [None, {"color": "b", "kind": "K", "state": "IDLE"}],
    ]


def test_to_wire_state_serializes_a_pieces_current_state():
    state, board = make_state()
    board.get(0, 0).state = PieceState.MOVING
    payload = to_wire_state(state)
    assert payload["board"][0][0]["state"] == "MOVING"


def test_to_wire_state_includes_scores():
    state, _board = make_state()
    state.record_capture("w", 5)
    assert to_wire_state(state)["scores"] == {"w": 5, "b": 0}


def test_to_wire_state_includes_move_history_with_color():
    state, board = make_state()
    state.record_move(board, Piece(color="w", kind="P"), Position(1, 0), Position(0, 0))
    assert to_wire_state(state)["move_history"] == [{"color": "w", "notation": "a2"}]


def test_to_wire_state_includes_pending_promotions():
    state, board = make_state()
    pawn = Piece(color="w", kind="P", cell=Position(0, 1))
    state.schedule_promotion(Position(0, 1), "w", ("Q", "R", "B", "N"), pawn)
    assert to_wire_state(state)["pending_promotions"] == [
        {"row": 0, "col": 1, "color": "w", "choices": ["Q", "R", "B", "N"]}
    ]


def test_from_wire_state_reconstructs_the_board():
    state, _board = make_state()
    rebuilt = from_wire_state(to_wire_state(state))
    assert rebuilt.board_height() == 2
    assert rebuilt.board_width() == 2
    top_left = rebuilt.board_rows()[0][0]
    assert (top_left.color, top_left.kind, top_left.state) == ("w", "K", PieceState.IDLE)
    assert rebuilt.board_rows()[0][1] is None


def test_from_wire_state_reconstructs_piece_state():
    state, board = make_state()
    board.get(1, 1).state = PieceState.AIRBORNE
    rebuilt = from_wire_state(to_wire_state(state))
    assert rebuilt.board_rows()[1][1].state == PieceState.AIRBORNE


def test_from_wire_state_reconstructs_scores():
    state, _board = make_state()
    state.record_capture("b", 3)
    rebuilt = from_wire_state(to_wire_state(state))
    assert rebuilt.scores() == {"w": 0, "b": 3}


def test_from_wire_state_reconstructs_move_history_and_moves_for_color():
    state, board = make_state()
    state.record_move(board, Piece(color="w", kind="P"), Position(1, 0), Position(0, 0))
    state.record_move(board, Piece(color="b", kind="P"), Position(0, 1), Position(1, 1))
    rebuilt = from_wire_state(to_wire_state(state))
    assert rebuilt.move_history() == ["a2", "b1"]
    assert rebuilt.moves_for_color("w") == ["a2"]
    assert rebuilt.moves_for_color("b") == ["b1"]


def test_from_wire_state_reconstructs_pending_promotions():
    state, board = make_state()
    pawn = Piece(color="w", kind="P", cell=Position(0, 1))
    board.place(0, 1, pawn)
    state.schedule_promotion(Position(0, 1), "w", ("Q", "R"), pawn)
    rebuilt = from_wire_state(to_wire_state(state))
    pending = rebuilt.get_pending_promotion(Position(0, 1))
    assert pending.color == "w"
    assert pending.choices == ("Q", "R")
    # The pending promotion's `piece` is the exact instance sitting on the
    # rebuilt board at that square, not the original - see
    # GameLoop/Controller's identity-keyed promotion-menu bookkeeping.
    assert pending.piece is rebuilt.board_rows()[0][1]