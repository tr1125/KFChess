import io
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import run


def run_and_capture(input_text):
    out = io.StringIO()
    run(input_text, out)
    return out.getvalue()


# --- Iteration 1: parsing & validation ---

def test_parse_rectangular_board_3x4():
    input_text = (
        "Board:\n"
        "wK . . bK\n"
        ". . . . \n"
        "wR . . bR\n"
        "Commands:\n"
        "print board\n"
    )
    expected = "wK . . bK\n. . . .\nwR . . bR\n"
    assert run_and_capture(input_text) == expected


def test_parse_piece_tokens_and_colors():
    input_text = (
        "Board:\n"
        "wK . bQ\n"
        ". wN .\n"
        "bP . wR\n"
        "Commands:\n"
        "print board\n"
    )
    expected = "wK . bQ\n. wN .\nbP . wR\n"
    assert run_and_capture(input_text) == expected


def test_reject_unknown_token():
    input_text = "Board:\nwK xZ\n. .\nCommands:\n"
    assert run_and_capture(input_text) == "ERROR UNKNOWN_TOKEN\n"


def test_reject_row_width_mismatch():
    input_text = "Board:\nwK . .\n. bK\nCommands:\n"
    assert run_and_capture(input_text) == "ERROR ROW_WIDTH_MISMATCH\n"


# --- Iteration 2: click / wait / print board ---

def test_select_piece_by_center_click():
    input_text = (
        "Board:\n"
        "wK . .\n"
        ". . .\n"
        ". . .\n"
        "Commands:\n"
        "click 50 50\n"
        "click 150 150\n"
        "wait 1000\n"
        "print board\n"
    )
    expected = ". . .\n. wK .\n. . .\n"
    assert run_and_capture(input_text) == expected


def test_click_empty_cell_does_not_select():
    input_text = (
        "Board:\n"
        "wK . .\n"
        ". . .\n"
        ". . .\n"
        "Commands:\n"
        "click 150 150\n"
        "click 250 250\n"
        "wait 1000\n"
        "print board\n"
    )
    expected = "wK . .\n. . .\n. . .\n"
    assert run_and_capture(input_text) == expected


def test_click_outside_board_is_ignored():
    input_text = (
        "Board:\n"
        "wK . .\n"
        ". . .\n"
        ". . .\n"
        "Commands:\n"
        "click 350 50\n"
        "click -10 50\n"
        "print board\n"
    )
    expected = "wK . .\n. . .\n. . .\n"
    assert run_and_capture(input_text) == expected


def test_clicking_another_friendly_piece_replaces_selection():
    input_text = (
        "Board:\n"
        "wR . wK\n"
        ". . .\n"
        "Commands:\n"
        "click 50 50\n"
        "click 250 50\n"
        "click 250 150\n"
        "wait 1000\n"
        "print board\n"
    )
    expected = "wR . .\n. . wK\n"
    assert run_and_capture(input_text) == expected


def test_move_not_yet_settled_before_duration_elapses():
    """Not one of the failing VPL cases, but documents the design intent:
    a requested move only appears on the board once enough time has
    passed (see config.settings.MOVE_DURATION_MS)."""
    input_text = (
        "Board:\n"
        "wK . .\n"
        ". . .\n"
        ". . .\n"
        "Commands:\n"
        "click 50 50\n"
        "click 150 150\n"
        "wait 1\n"
        "print board\n"
    )
    expected = "wK . .\n. . .\n. . .\n"
    assert run_and_capture(input_text) == expected