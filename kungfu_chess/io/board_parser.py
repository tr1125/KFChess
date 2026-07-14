"""Text -> model: parses the fixture board-text format into a validated
Board. The only place that knows the on-disk/stdin text format's parsing
direction. If the format ever changes (e.g. a binary board later), only
this file (and its board_printer sibling) needs to change - Board and
the rest of the engine stay untouched.
"""

import re

from kungfu_chess.model.board import Board, EMPTY_TOKEN
from kungfu_chess.model.piece import Piece
from kungfu_chess.model.position import Position

_VALID_TOKEN_PATTERN = re.compile(r"^[wb][KQRBNP]$")


class BoardFormatError(Exception):
    """Raised when the fixture text violates a validation rule.

    `code` is the machine-readable error code callers expect, e.g.
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

    piece_rows = [
        [_token_to_piece(token, row_index, col_index) for col_index, token in enumerate(row)]
        for row_index, row in enumerate(rows)
    ]
    return Board(piece_rows)


def _token_to_piece(token, row, col):
    if token == EMPTY_TOKEN:
        return None
    return Piece(color=token[0], kind=token[1], cell=Position(row, col))