from kungfu_chess.model.board import Board
from kungfu_chess.model.piece import Piece
from kungfu_chess.model.position import Position
from kungfu_chess.model.game_state import GameState


def piece(token):
    return Piece(color=token[0], kind=token[1])


def board_from(rows):
    return Board([[None if cell == "." else piece(cell) for cell in row] for row in rows])


def make_board(rows=None):
    rows = rows if rows is not None else [["wK", "."], [".", "bK"]]
    return board_from(rows)


def empty_board(size=8):
    return board_from([["."] * size for _ in range(size)])


def signature(cell):
    return None if cell is None else (cell.color, cell.kind)


# --- move history: square naming and move formatting ---

def test_pawn_move_has_no_prefix():
    state = GameState()
    state.record_move(empty_board(), piece("wP"), Position(6, 4), Position(4, 4))  # e2-e4
    assert state.move_history() == ["e4"]


def test_pawn_capture_prefixes_origin_file():
    state = GameState()
    state.record_move(
        empty_board(), piece("wP"), Position(2, 4), Position(3, 3), captured_piece=piece("bP")
    )  # exd5
    assert state.move_history() == ["exd5"]


def test_piece_move_prefixes_piece_letter():
    state = GameState()
    state.record_move(empty_board(), piece("wN"), Position(7, 6), Position(5, 5))  # Nf3
    assert state.move_history() == ["Nf3"]


def test_piece_capture_includes_x():
    state = GameState()
    state.record_move(
        empty_board(), piece("wN"), Position(7, 6), Position(5, 5), captured_piece=piece("bP")
    )
    assert state.move_history() == ["Nxf3"]


def test_promotion_appends_equals_new_type():
    state = GameState()
    state.record_move(
        empty_board(), piece("wP"), Position(1, 4), Position(0, 4), promoted_piece=piece("wQ")
    )  # e8=Q
    assert state.move_history() == ["e8=Q"]


def test_capture_promotion_combines_both():
    state = GameState()
    state.record_move(
        empty_board(),
        piece("wP"),
        Position(1, 3),
        Position(0, 4),
        captured_piece=piece("bR"),
        promoted_piece=piece("wQ"),
    )
    assert state.move_history() == ["dxe8=Q"]


def test_ends_game_appends_hash():
    state = GameState()
    state.record_move(
        empty_board(), piece("wQ"), Position(4, 4), Position(0, 4), captured_piece=piece("bK"), ends_game=True
    )
    assert state.move_history() == ["Qxe8#"]


def test_airborne_capture_is_recorded_as_comment():
    state = GameState()
    state.record_airborne_capture(empty_board(), piece("bN"), piece("wK"), Position(4, 4))
    assert state.move_history() == ["{bN captured mid-air by wK at e4}"]


def test_record_promotion_logs_square_and_new_type():
    state = GameState()
    state.record_promotion(empty_board(), piece("wQ"), Position(0, 1))
    assert state.move_history() == ["b8=Q"]


def test_entries_are_appended_in_order():
    state = GameState()
    state.record_move(empty_board(), piece("wP"), Position(6, 4), Position(4, 4))
    state.record_move(empty_board(), piece("bP"), Position(1, 3), Position(3, 3))
    assert state.move_history() == ["e4", "d5"]


def test_history_text_joins_entries_with_spaces():
    state = GameState()
    state.record_move(empty_board(), piece("wP"), Position(6, 4), Position(4, 4))
    state.record_move(empty_board(), piece("bP"), Position(1, 3), Position(3, 3))
    assert state.history_text() == "e4 d5"


def test_move_history_returns_a_defensive_copy():
    state = GameState()
    state.record_move(empty_board(), piece("wP"), Position(6, 4), Position(4, 4))
    snapshot = state.move_history()
    snapshot.append("bogus")
    assert state.move_history() == ["e4"]


# --- scores ---

def test_new_state_scores_start_at_zero_for_both_colors():
    state = GameState()
    assert state.scores() == {"w": 0, "b": 0}


def test_record_capture_credits_the_given_color_with_the_given_value():
    state = GameState()
    state.record_capture("w", 3)
    assert state.scores() == {"w": 3, "b": 0}


def test_record_capture_accumulates_across_multiple_captures():
    state = GameState()
    state.record_capture("w", 1)
    state.record_capture("w", 9)
    state.record_capture("b", 5)
    assert state.scores() == {"w": 10, "b": 5}


def test_scores_returns_a_defensive_copy():
    state = GameState()
    snapshot = state.scores()
    snapshot["w"] = 999
    assert state.scores() == {"w": 0, "b": 0}


# --- pending promotions ---

def test_scheduled_promotion_is_pending_at_its_position():
    state = GameState()
    state.schedule_promotion(Position(0, 1), "w", ("Q", "R", "B", "N"))
    assert state.get_pending_promotion(Position(0, 1)) is not None
    assert state.get_pending_promotion(Position(1, 1)) is None


def test_has_pending_promotion_reflects_whether_anything_is_pending():
    state = GameState()
    assert not state.has_pending_promotion()
    state.schedule_promotion(Position(0, 1), "w", ("Q",))
    assert state.has_pending_promotion()


def test_take_pending_promotion_removes_the_entry():
    state = GameState()
    state.schedule_promotion(Position(0, 1), "w", ("Q",))
    taken = state.take_pending_promotion(Position(0, 1))
    assert taken.color == "w"
    assert not state.has_pending_promotion()
    assert state.take_pending_promotion(Position(0, 1)) is None


def test_pending_promotions_lists_every_pending_entry():
    state = GameState()
    state.schedule_promotion(Position(0, 1), "w", ("Q",))
    state.schedule_promotion(Position(3, 1), "b", ("Q",))
    positions = {pending.position for pending in state.pending_promotions()}
    assert positions == {Position(0, 1), Position(3, 1)}


# --- game over ---

def test_new_state_is_not_game_over():
    assert not GameState().is_game_over()


def test_set_game_over_marks_state_as_over():
    state = GameState()
    state.set_game_over()
    assert state.is_game_over()


# --- board snapshot ---

def test_board_rows_reflects_the_attached_board():
    state = GameState()
    board = make_board()
    state.attach_board(board)
    assert [[signature(cell) for cell in row] for row in state.board_rows()] == [
        [("w", "K"), None],
        [None, ("b", "K")],
    ]


def test_board_rows_is_live_not_a_stale_copy():
    state = GameState()
    board = make_board()
    state.attach_board(board)
    board.apply_move(0, 0, 1, 0)
    assert [[signature(cell) for cell in row] for row in state.board_rows()] == [
        [None, None],
        [("w", "K"), ("b", "K")],
    ]


def test_board_height_and_width_reflect_the_attached_board():
    state = GameState()
    state.attach_board(make_board())
    assert state.board_height() == 2
    assert state.board_width() == 2
