"""Unit-level coverage of script_runner's parsing/dispatch/error-handling
seams. Full realistic play-throughs live in tests/integration/ against
the .kfc scripts.
"""

import io

from kungfu_chess.model.board import Board
from kungfu_chess.model.piece import Piece
from kungfu_chess.texttests.script_runner import run_script, build_engine


def run_and_capture(input_text):
    out = io.StringIO()
    run_script(input_text, out)
    return out.getvalue()


def test_build_engine_wires_a_usable_engine():
    engine = build_engine(Board([[Piece(color="w", kind="K"), None]]))
    piece = engine.board().get(0, 0)
    assert (piece.color, piece.kind) == ("w", "K")
    assert not engine.is_game_over()


def test_run_script_parses_and_prints_board():
    input_text = "Board:\nwK . . bK\n. . . .\nCommands:\nprint board\n"
    assert run_and_capture(input_text) == "wK . . bK\n. . . .\n"


def test_run_script_reports_unknown_token_error():
    input_text = "Board:\nwK xZ\nCommands:\n"
    assert run_and_capture(input_text) == "ERROR UNKNOWN_TOKEN\n"


def test_run_script_reports_row_width_mismatch_error():
    input_text = "Board:\nwK . .\n. bK\nCommands:\n"
    assert run_and_capture(input_text) == "ERROR ROW_WIDTH_MISMATCH\n"


def test_run_script_click_and_wait_settle_a_move():
    input_text = (
        "Board:\nwK . .\n. . .\n. . .\nCommands:\n"
        "click 50 50\nclick 150 150\nwait 1000\nprint board\n"
    )
    assert run_and_capture(input_text) == ". . .\n. wK .\n. . .\n"


def test_run_script_jump_command_is_wired():
    input_text = "Board:\n. . .\n. wK .\n. . .\nCommands:\njump 150 150\nwait 1000\nprint board\n"
    assert run_and_capture(input_text) == ". . .\n. wK .\n. . .\n"


def test_run_script_promote_command_is_wired():
    input_text = (
        "Board:\nwK . . bK\n. wP . .\n. . . .\nCommands:\n"
        "click 150 150\nclick 150 50\nwait 1000\npromote 0 1 Q\nprint board\n"
    )
    assert run_and_capture(input_text) == "wK wQ . bK\n. . . .\n. . . .\n"


def test_run_script_print_score_reports_zero_before_any_capture():
    input_text = "Board:\nwK . bK\nCommands:\nprint score\n"
    assert run_and_capture(input_text) == "w 0 b 0\n"


def test_run_script_print_score_after_a_capture():
    input_text = (
        "Board:\nwR . bN\nCommands:\nclick 50 50\nclick 250 50\nwait 2000\nprint score\n"
    )
    assert run_and_capture(input_text) == "w 3 b 0\n"  # knight captured, worth 3


def test_run_script_print_promotions_reports_pending_choice():
    input_text = (
        "Board:\nwK . . bK\n. wP . .\n. . . .\nCommands:\n"
        "click 150 150\nclick 150 50\nwait 1000\nprint promotions\n"
    )
    assert run_and_capture(input_text) == "0 1 w QRBN\n"


def test_run_script_print_promotions_empty_when_nothing_pending():
    input_text = "Board:\nwK . bK\nCommands:\nprint promotions\n"
    assert run_and_capture(input_text) == ""


def test_run_script_ignores_an_unrecognized_command():
    input_text = "Board:\nwK . bK\nCommands:\nfoobar\nprint board\n"
    assert run_and_capture(input_text) == "wK . bK\n"