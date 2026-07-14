from kungfu_chess.model.board import Board
from kungfu_chess.model.piece import Piece
from kungfu_chess.rules.piece_rules import default_piece_rules
from kungfu_chess.rules.rule_engine import RuleEngine
from kungfu_chess.engine.game_engine import GameEngine
from kungfu_chess.input.board_mapper import BoardMapper
from kungfu_chess.input.controller import Controller


def board_from(rows):
    return Board([[None if cell == "." else Piece(color=cell[0], kind=cell[1]) for cell in row] for row in rows])


class RecordingEngine:
    """A hand-written test double (no mocking framework) that records
    which GameEngine method was called with which arguments, so
    Controller's translation can be verified in isolation from real
    engine behavior.
    """

    def __init__(self):
        self.calls = []

    def click(self, row, col):
        self.calls.append(("click", row, col))

    def jump(self, row, col):
        self.calls.append(("jump", row, col))

    def wait(self, ms):
        self.calls.append(("wait", ms))

    def choose_promotion(self, row, col, piece_type):
        self.calls.append(("choose_promotion", row, col, piece_type))


def make_controller(cell_size_px=100):
    engine = RecordingEngine()
    controller = Controller(engine, BoardMapper(cell_size_px))
    return controller, engine


# --- translation to cell coordinates ---

def test_click_translates_pixels_to_cell_and_forwards_to_engine():
    controller, engine = make_controller()
    controller.click(250, 150)
    assert engine.calls == [("click", 1, 2)]


def test_jump_translates_pixels_to_cell_and_forwards_to_engine():
    controller, engine = make_controller()
    controller.jump(250, 150)
    assert engine.calls == [("jump", 1, 2)]


def test_wait_forwards_milliseconds_unchanged():
    controller, engine = make_controller()
    controller.wait(500)
    assert engine.calls == [("wait", 500)]


def test_choose_promotion_forwards_cell_and_piece_type_unchanged():
    controller, engine = make_controller()
    controller.choose_promotion(0, 1, "Q")
    assert engine.calls == [("choose_promotion", 0, 1, "Q")]


def test_click_and_jump_respect_configured_cell_size():
    controller, engine = make_controller(cell_size_px=50)
    controller.click(120, 60)
    assert engine.calls == [("click", 1, 2)]


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