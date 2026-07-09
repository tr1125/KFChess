"""Human-readable move log in algebraic (SAN-style) notation - the same
square-and-piece-letter format used to record real chess games (PGN/SAN),
adapted to this board's arbitrary width/height instead of assuming a
fixed 8x8.

Disambiguation (e.g. "Nbd2" when two knights could reach the same
square) is not implemented - this is a readable move log, not a fully
PGN-compliant exporter.

Only settled moves are recorded. A cancelled/no-op move (blocked by a
friendly piece, or the mover having vanished before the move came due)
never happened from the game's point of view, so it leaves no entry -
matching how real chess notation only records completed moves. This
variant's king-capture end condition has no equivalent in real chess
(a real game ends at checkmate, one move earlier) - it's recorded as an
ordinary capture with a trailing "#", reusing the checkmate marker for
"this move ended the game". The airborne-capture mechanic has no
standard notation at all, so it's logged as a PGN-style {comment}
instead of invented move syntax.
"""

from domain.piece_token import type_of, PAWN_TYPE


def _square_name(board, row, col):
    file_letter = chr(ord("a") + col)
    rank_number = board.height - row
    return f"{file_letter}{rank_number}"


class MoveHistory:
    def __init__(self):
        self._entries = []

    def record_move(
        self,
        board,
        mover_token,
        from_row,
        from_col,
        to_row,
        to_col,
        captured_token=None,
        promoted_token=None,
        ends_game=False,
    ):
        piece_type = type_of(mover_token)
        is_capture = captured_token is not None
        destination = _square_name(board, to_row, to_col)

        if piece_type == PAWN_TYPE:
            origin_file = _square_name(board, from_row, from_col)[0]
            prefix = f"{origin_file}x" if is_capture else ""
        else:
            prefix = f"{piece_type}x" if is_capture else piece_type

        notation = f"{prefix}{destination}"
        if promoted_token is not None:
            notation += f"={type_of(promoted_token)}"
        if ends_game:
            notation += "#"

        self._entries.append(notation)

    def record_promotion(self, board, promoted_token, row, col):
        """Record a user's promotion choice, resolved some time after the
        triggering move settled (see PromotionScheduler) - so, like the
        airborne-capture case, it can't be folded into that move's own
        entry and is logged as its own "=X" entry instead.
        """
        square = _square_name(board, row, col)
        self._entries.append(f"{square}={type_of(promoted_token)}")

    def record_airborne_capture(self, board, attacker_token, defender_token, row, col):
        square = _square_name(board, row, col)
        self._entries.append(
            f"{{{attacker_token} captured mid-air by {defender_token} at {square}}}"
        )

    def entries(self):
        return list(self._entries)

    def __str__(self):
        return " ".join(self._entries)
