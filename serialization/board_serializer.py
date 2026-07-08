"""Parsing and printing of the text board fixture format.

This module is the single place that knows the on-disk/stdin text format.
If the format ever changes (e.g. binary board later), only this file
(and a new sibling serializer) needs to change - Board and the engine
stay untouched.
"""

import re

from domain.board import Board, EMPTY_TOKEN

_VALID_TOKEN_PATTERN = re.compile(r"^[wb][KQRBNP]$")


class BoardFormatError(Exception):
    """Raised when the fixture text violates a validation rule.

    `code` is the machine-readable error code VPL expects, e.g.
    'ROW_WIDTH_MISMATCH' or 'UNKNOWN_TOKEN'.
    """

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _is_valid_token(token):
    return token == EMPTY_TOKEN or bool(_VALID_TOKEN_PATTERN.match(token))


def parse_board(board_lines):
    """board_lines: list[str], each a raw row line from the 'Board:' section.

    Returns a validated Board. Raises BoardFormatError on invalid input.
    """
    rows = [line.split() for line in board_lines]

    if rows:
        width = len(rows[0])
        for row in rows:
            if len(row) != width:
                raise BoardFormatError("ROW_WIDTH_MISMATCH")

    for row in rows:
        for token in row:
            if not _is_valid_token(token):
                raise BoardFormatError("UNKNOWN_TOKEN")

    return Board(rows)


def to_canonical(board):
    """Render a Board back to the canonical text form (no trailing newline)."""
    return "\n".join(" ".join(row) for row in board.rows())