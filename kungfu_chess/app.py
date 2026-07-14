"""CLI entry point: reads a script from stdin and runs it through
texttests.script_runner, writing results to stdout.
"""

import sys

from kungfu_chess.texttests.script_runner import run_script


def main(stdin=None, stdout=None):
    stdin = stdin if stdin is not None else sys.stdin
    stdout = stdout if stdout is not None else sys.stdout
    run_script(stdin.read(), stdout)


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess in test_app.py
    main()