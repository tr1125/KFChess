"""Runs every .kfc fixture in tests/integration/scripts/ end-to-end
through texttests.script_runner and checks its output against the
"Expected:" section embedded in the same file.

The "Expected:" section is a fixture-file convention understood only by
this harness - it is not part of the real Board:/Commands: protocol
script_parser.py knows about, so it is stripped out here before the
script text is handed to run_script.
"""

import io
from pathlib import Path

import pytest

from kungfu_chess.texttests.script_runner import run_script

SCRIPTS_DIR = Path(__file__).parent / "scripts"
EXPECTED_MARKER = "\nExpected:\n"


def _load_script(path):
    text = path.read_text()
    script_text, marker, expected_text = text.partition(EXPECTED_MARKER)
    assert marker == EXPECTED_MARKER, f"{path.name} is missing an 'Expected:' section"
    # Every run_script print command ends its output with exactly one
    # newline; normalize the fixture file's trailing newline (present or
    # not, depending on how the file was saved) to match that instead of
    # making the convention depend on editors preserving a final EOL.
    if expected_text:
        expected_text = expected_text.rstrip("\n") + "\n"
    return script_text, expected_text


def _script_paths():
    paths = sorted(SCRIPTS_DIR.glob("*.kfc"))
    assert paths, "no .kfc integration scripts found"
    return paths


@pytest.mark.parametrize("script_path", _script_paths(), ids=lambda p: p.name)
def test_kfc_script_produces_expected_output(script_path):
    script_text, expected_text = _load_script(script_path)
    out = io.StringIO()
    run_script(script_text, out)
    assert out.getvalue() == expected_text