from kungfu_chess.model.board import Board
from kungfu_chess.model.piece import Piece, PieceState
from kungfu_chess.model.game_state import GameState
from kungfu_chess.rules.piece_rules import default_piece_rules
from kungfu_chess.rules.rule_engine import RuleEngine
from kungfu_chess.engine.game_engine import GameEngine
from kungfu_chess.input.board_mapper import BoardMapper
from kungfu_chess.input.controller import Controller
from kungfu_chess.input.player_session import PlayerSession


def board_from(rows):
    return Board([[None if cell == "." else Piece(color=cell[0], kind=cell[1]) for cell in row] for row in rows])


class RecordingEngine:
    """A hand-written test double (no mocking framework) that records
    which GameEngine method was called with which arguments. Controller
    now inspects board_rows()/board_height()/board_width() itself to
    drive click-selection semantics, so this fake wraps a real Board
    (via a real GameState) instead of returning a bare sentinel.
    """

    def __init__(self, board):
        game_state = GameState()
        game_state.attach_board(board)
        self._game_state = game_state
        self.calls = []

    def request_move(self, from_row, from_col, to_row, to_col):
        self.calls.append(("request_move", from_row, from_col, to_row, to_col))

    def jump(self, row, col):
        self.calls.append(("jump", row, col))

    def wait(self, ms):
        self.calls.append(("wait", ms))

    def choose_promotion(self, row, col, piece_type):
        self.calls.append(("choose_promotion", row, col, piece_type))

    def game_state(self):
        return self._game_state

    def now(self):
        self.calls.append(("now",))
        return 12345

    def in_flight_leg(self, piece):
        self.calls.append(("in_flight_leg", piece))
        return "sentinel-leg"


def make_controller(board, cell_size_px=100, player_session=None):
    engine = RecordingEngine(board)
    controller = Controller(engine, BoardMapper(cell_size_px), player_session=player_session)
    return controller, engine


# --- passthrough behavior ---

def test_jump_translates_pixels_to_cell_and_forwards_to_engine():
    controller, engine = make_controller(board_from([["wK", "."]]))
    controller.jump(150, 50)
    assert engine.calls == [("jump", 0, 1)]


def test_jump_respects_configured_cell_size():
    controller, engine = make_controller(board_from([["wK", "."]]), cell_size_px=50)
    controller.jump(120, 10)
    assert engine.calls == [("jump", 0, 2)]


def test_wait_forwards_milliseconds_unchanged():
    controller, engine = make_controller(board_from([["wK"]]))
    controller.wait(500)
    assert engine.calls == [("wait", 500)]


def test_choose_promotion_forwards_cell_and_piece_type_unchanged():
    controller, engine = make_controller(board_from([["wK"]]))
    controller.choose_promotion(0, 1, "Q")
    assert engine.calls == [("choose_promotion", 0, 1, "Q")]


def test_game_state_forwards_to_engine():
    controller, engine = make_controller(board_from([["wK"]]))
    assert controller.game_state() is engine.game_state()


def test_now_forwards_to_engine():
    controller, engine = make_controller(board_from([["wK"]]))
    assert controller.now() == 12345
    assert engine.calls == [("now",)]


def test_in_flight_leg_forwards_the_piece_argument_and_return_value():
    board = board_from([["wK"]])
    controller, engine = make_controller(board)
    piece = board.get(0, 0)

    result = controller.in_flight_leg(piece)

    assert result == "sentinel-leg"
    assert engine.calls == [("in_flight_leg", piece)]


# --- server-side cell-coordinate passthrough (move_piece/jump_piece) ---

def test_move_piece_forwards_cells_unchanged_bypassing_selection():
    controller, engine = make_controller(board_from([["wR", ".", "."]]))
    controller.move_piece(0, 0, 0, 2)
    assert engine.calls == [("request_move", 0, 0, 0, 2)]
    assert controller.selected() is None


def test_jump_piece_forwards_cell_unchanged():
    controller, engine = make_controller(board_from([["wK", "."]]))
    controller.jump_piece(0, 0)
    assert engine.calls == [("jump", 0, 0)]


def test_board_mapper_is_optional_when_only_cell_based_methods_are_used():
    engine = RecordingEngine(board_from([["wR", "."]]))
    controller = Controller(engine)
    controller.move_piece(0, 0, 0, 1)
    assert engine.calls == [("request_move", 0, 0, 0, 1)]


# --- flipped board orientation (networked Black client) ---

def test_flipped_click_converts_display_position_to_logical_before_selecting():
    board = board_from([["bK", "."], [".", "wK"]])  # 2x2 board
    engine = RecordingEngine(board)
    controller = Controller(engine, BoardMapper(cell_size_px=100), flipped=True)
    # Display-space (0, 0) (top-left) is logical (1, 1) when flipped on a
    # 2x2 board - that's wK, not bK.
    controller.click(50, 50)
    controller.click(50, 150)  # display (1, 0) -> logical (0, 1): empty target
    assert engine.calls == [("request_move", 1, 1, 0, 1)]


def test_unflipped_click_is_unaffected_by_the_flipped_flag_default():
    controller, engine = make_controller(board_from([["wR", ".", "."]]))
    controller.click(50, 50)
    controller.click(250, 50)
    assert engine.calls == [("request_move", 0, 0, 0, 2)]


# --- first click: what counts as a selection ---

def test_first_click_on_empty_square_does_not_select():
    controller, engine = make_controller(board_from([[".", "."]]))
    controller.click(50, 50)  # (0, 0) empty
    controller.click(150, 50)  # would be a move-attempt if something were selected
    assert engine.calls == []


def test_first_click_on_any_idle_piece_selects_it_regardless_of_color():
    # Player identity is bookkeeping only in this phase (no way to tell
    # which human clicked with a single shared mouse) - so Controller
    # doesn't gate a first click by color, only by IDLE state.
    controller, engine = make_controller(board_from([["bK", ".", "."]]))
    controller.click(50, 50)  # (0, 0) - selects the black king
    controller.click(250, 50)  # (0, 2) - target
    assert engine.calls == [("request_move", 0, 0, 0, 2)]


def test_first_click_on_a_busy_piece_does_not_select():
    board = board_from([["wK", "."]])
    board.get(0, 0).state = PieceState.MOVING
    controller, engine = make_controller(board)
    controller.click(50, 50)  # busy - not registered as a selection at all
    controller.click(150, 50)
    assert engine.calls == []


def test_first_click_outside_the_board_does_not_select():
    controller, engine = make_controller(board_from([["wK", "."]]))
    controller.click(-50, 50)  # off-board
    controller.click(150, 50)
    assert engine.calls == []


# --- second click: move, jump, switch, or cancel ---

def test_selecting_own_idle_piece_then_clicking_empty_square_requests_a_move():
    controller, engine = make_controller(board_from([["wR", ".", "."]]))
    controller.click(50, 50)  # select wR at (0, 0)
    controller.click(250, 50)  # target (0, 2)
    assert engine.calls == [("request_move", 0, 0, 0, 2)]


def test_selecting_own_idle_piece_then_clicking_an_opponent_requests_a_move():
    controller, engine = make_controller(board_from([["wR", ".", "bK"]]))
    controller.click(50, 50)
    controller.click(250, 50)
    assert engine.calls == [("request_move", 0, 0, 0, 2)]


def test_clicking_the_same_selected_square_again_jumps_instead_of_requesting_a_move():
    controller, engine = make_controller(board_from([["wR", "."]]))
    controller.click(50, 50)
    controller.click(50, 50)
    assert engine.calls == [("jump", 0, 0)]


def test_clicking_a_different_own_color_idle_piece_switches_selection_without_moving():
    controller, engine = make_controller(board_from([["wR", "wN", "."]]))
    controller.click(50, 50)  # select wR at (0, 0)
    controller.click(150, 50)  # switch to wN at (0, 1) - no move attempted
    assert engine.calls == []
    controller.click(250, 50)  # now move wN, not wR
    assert engine.calls == [("request_move", 0, 1, 0, 2)]


def test_clicking_a_busy_own_color_piece_as_second_click_is_an_invalid_target_not_a_switch():
    board = board_from([["wR", "wN", "."]])
    board.get(0, 1).state = PieceState.MOVING
    controller, engine = make_controller(board)
    controller.click(50, 50)  # select wR
    controller.click(150, 50)  # wN is busy - falls through to a move attempt instead of switching
    assert engine.calls == [("request_move", 0, 0, 0, 1)]


def test_invalid_target_cancels_selection_so_the_next_click_starts_fresh():
    controller, engine = make_controller(board_from([["wR", ".", "."], [".", ".", "wK"]]))
    controller.click(50, 50)  # select wR at (0, 0)
    controller.click(50, 150)  # (1, 0) empty target - always clears selection afterward
    assert engine.calls == [("request_move", 0, 0, 1, 0)]

    controller.click(250, 150)  # a fresh first click on wK at (1, 2)
    controller.click(150, 150)  # a fresh target
    assert engine.calls == [
        ("request_move", 0, 0, 1, 0),
        ("request_move", 1, 2, 1, 1),
    ]


def test_second_click_outside_the_board_is_treated_as_an_invalid_target():
    controller, engine = make_controller(board_from([["wR", "."]]))
    controller.click(50, 50)  # select wR at (0, 0)
    controller.click(-50, 50)  # off-board (row 0, col -1)
    assert engine.calls == [("request_move", 0, 0, 0, -1)]


# --- player identity bookkeeping ---

def test_first_successful_selection_claims_the_pieces_color():
    session = PlayerSession()
    controller, engine = make_controller(board_from([["wR", "."]]), player_session=session)
    controller.click(50, 50)
    assert session.claimed_colors() == ["w"]


def test_a_click_that_does_not_select_does_not_claim_a_color():
    session = PlayerSession()
    controller, engine = make_controller(board_from([[".", "."]]), player_session=session)
    controller.click(50, 50)  # empty square - no selection, no claim
    assert session.claimed_colors() == []


def test_controller_constructs_its_own_player_session_by_default():
    controller, engine = make_controller(board_from([["wR", "."]]))
    controller.click(50, 50)
    controller.click(150, 50)
    # No exception, and the move was still requested - confirms a default
    # PlayerSession was wired in without the caller having to supply one.
    assert engine.calls == [("request_move", 0, 0, 0, 1)]


# --- end-to-end with a real GameEngine ---

def test_controller_drives_a_real_game_engine():
    rows = [["wK", ".", "."], [".", ".", "."], [".", ".", "."]]
    board = board_from(rows)
    engine = GameEngine(board, RuleEngine(default_piece_rules()))
    controller = Controller(engine, BoardMapper(cell_size_px=100))

    controller.click(50, 50)  # (0, 0) - select wK
    controller.click(150, 150)  # (1, 1) - request move
    controller.wait(1000)

    piece = board.get(1, 1)
    assert (piece.color, piece.kind) == ("w", "K")
    assert controller.game_state() is engine.game_state()


def test_controller_now_and_in_flight_leg_against_a_real_game_engine():
    rows = [["wR", ".", "."]]
    board = board_from(rows)
    engine = GameEngine(board, RuleEngine(default_piece_rules()))
    controller = Controller(engine, BoardMapper(cell_size_px=100))
    piece = board.get(0, 0)

    assert controller.now() == 0
    assert controller.in_flight_leg(piece) is None

    controller.click(50, 50)  # (0, 0) - select wR
    controller.click(150, 50)  # (0, 1) - request move

    current, target, started_at, complete_at = controller.in_flight_leg(piece)
    assert (current.row, current.col) == (0, 0)
    assert (target.row, target.col) == (0, 1)
    assert started_at == 0
    assert complete_at == 1000

    controller.wait(1000)
    assert controller.now() == 1000
    assert controller.in_flight_leg(piece) is None


# --- has_moved_since_promotion ---

def test_has_moved_since_promotion_is_false_for_idle_or_long_rest():
    controller, _engine = make_controller(board_from([["wQ"]]))
    piece = Piece(color="w", kind="Q", state=PieceState.IDLE)
    assert controller.has_moved_since_promotion(piece) is False

    piece.state = PieceState.LONG_REST
    assert controller.has_moved_since_promotion(piece) is False


def test_has_moved_since_promotion_is_true_once_moving_or_airborne():
    controller, _engine = make_controller(board_from([["wQ"]]))
    piece = Piece(color="w", kind="Q", state=PieceState.MOVING)
    assert controller.has_moved_since_promotion(piece) is True

    piece.state = PieceState.AIRBORNE
    assert controller.has_moved_since_promotion(piece) is True


def test_controller_drives_a_real_game_engine_through_a_jump():
    rows = [[".", ".", "."], [".", "wK", "."], [".", ".", "."]]
    board = board_from(rows)
    engine = GameEngine(board, RuleEngine(default_piece_rules()))
    controller = Controller(engine, BoardMapper(cell_size_px=100))

    controller.click(150, 150)  # (1, 1) - select wK
    controller.click(150, 150)  # same square again - jump
    controller.wait(1)

    assert board.get(1, 1).state == PieceState.AIRBORNE