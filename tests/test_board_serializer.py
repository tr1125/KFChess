import io
import sys
import os
 
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
 
from main import run
 
 
def run_and_capture(input_text):
    out = io.StringIO()
    run(input_text, out)
    return out.getvalue()
 
 
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