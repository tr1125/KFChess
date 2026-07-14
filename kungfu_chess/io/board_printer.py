"""Model -> text: renders a Board back to the canonical fixture text
format. The only place that knows the printing direction of the format.
"""

from kungfu_chess.model.board import EMPTY_TOKEN


def to_canonical(board):
    """Render a Board back to the canonical fixture text form (no trailing newline)."""
    return "\n".join(
        " ".join(_piece_to_token(piece) for piece in row) for row in board.rows()
    )


def _piece_to_token(piece):
    return EMPTY_TOKEN if piece is None else f"{piece.color}{piece.kind}"
