"""app.py is a thin stdin/stdout wrapper around texttests.script_runner.
Exercised via a real subprocess (not monkeypatched sys.stdin) so the
actual CLI entry point is what's under test.
"""

import io
import subprocess
import sys
from pathlib import Path

from kungfu_chess.app import main

_REPO_ROOT = Path(__file__).resolve().parents[3]


def run_app(input_text):
    result = subprocess.run(
        [sys.executable, "-m", "kungfu_chess.app"],
        input=input_text,
        capture_output=True,
        text=True,
        cwd=_REPO_ROOT,
    )
    return result.stdout


def test_app_reads_stdin_and_prints_board():
    input_text = "Board:\nwK . . bK\nCommands:\nprint board\n"
    assert run_app(input_text) == "wK . . bK\n"


def test_app_reports_parse_errors():
    input_text = "Board:\nwK xZ\nCommands:\n"
    assert run_app(input_text) == "ERROR UNKNOWN_TOKEN\n"


# --- main() with injected streams (no real process, no monkeypatching) ---

def test_main_reads_from_injected_stdin_and_writes_to_injected_stdout():
    stdin = io.StringIO("Board:\nwK . bK\nCommands:\nprint board\n")
    stdout = io.StringIO()
    main(stdin=stdin, stdout=stdout)
    assert stdout.getvalue() == "wK . bK\n"


def test_main_propagates_parse_errors_through_injected_stdout():
    stdin = io.StringIO("Board:\nwK xZ\nCommands:\n")
    stdout = io.StringIO()
    main(stdin=stdin, stdout=stdout)
    assert stdout.getvalue() == "ERROR UNKNOWN_TOKEN\n"