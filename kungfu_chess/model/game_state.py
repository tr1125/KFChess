"""The single source-of-truth snapshot: move history, scores, pending
promotions, and game-over status. Mutated by the rules layer as moves
settle; read-only for the view layer.

Move notation is algebraic (SAN-style) - the same square-and-piece-letter
format used to record real chess games, adapted to this board's
arbitrary width/height instead of assuming a fixed 8x8. Disambiguation
(e.g. "Nbd2" when two knights could reach the same square) is not
implemented - this is a readable move log, not a fully PGN-compliant
exporter.

Each history entry is internally tagged with the color of whoever acted,
so a UI can filter to one player's own moves (`moves_for_color`) - this
matters because moves in this real-time variant are not strictly
alternating white/black, unlike a turn-based game where that could be
inferred from list position. `move_history()`/`history_text()` still
expose the plain notation strings only, unchanged.

Only settled moves are recorded. A cancelled/no-op move never happened
from the game's point of view, so it leaves no entry - matching how real
chess notation only records completed moves. This variant's king-capture
end condition has no equivalent in real chess (a real game ends at
checkmate, one move earlier) - it's recorded as an ordinary capture with
a trailing "#", reusing the checkmate marker for "this move ended the
game". The airborne-capture mechanic has no standard notation at all, so
it's logged as a PGN-style {comment} instead of invented move syntax.

GameState knows nothing about piece values or promotion configuration -
those are rules-layer concerns (see rules/piece_rules.py). Whoever
credits a capture (rule_engine) looks up the value and passes it in.
"""

from dataclasses import dataclass

from kungfu_chess.model.position import square_name


@dataclass(frozen=True)
class PendingPromotion:
    position: object  # Position
    color: str
    choices: tuple
    piece: object  # Piece - the exact instance this choice was scheduled for
    # (see RuleEngine.apply_promotion_choice's identity check: `position`
    # alone goes stale the moment this piece moves away or is replaced by
    # another occupant, so resolving the choice must reconfirm identity,
    # not just re-read the square).


class GameState:
    def __init__(self):
        self._history_entries = []
        self._scores = {"w": 0, "b": 0}
        self._pending_promotions = []
        self._game_over = False
        self._board = None

    # --- board snapshot ---------------------------------------------------
    #
    # GameState is the single read model the view draws from, so it also
    # exposes the board it was attached to (by whoever owns it - see
    # engine/game_engine.py) - a read-only view into the same Board the
    # rules layer mutates, not a separate copy that could drift out of
    # sync.

    def attach_board(self, board):
        self._board = board

    def board_rows(self):
        return self._board.rows()

    def board_height(self):
        return self._board.height

    def board_width(self):
        return self._board.width

    # --- move history -------------------------------------------------

    def record_move(
        self,
        board,
        mover_piece,
        from_position,
        to_position,
        captured_piece=None,
        promoted_piece=None,
        ends_game=False,
    ):
        is_capture = captured_piece is not None
        destination = square_name(to_position, board.height)
        origin_file = square_name(from_position, board.height)[0]
        prefix = mover_piece.notation_prefix(origin_file, is_capture)

        notation = f"{prefix}{destination}"
        if promoted_piece is not None:
            notation += f"={promoted_piece.kind}"
        if ends_game:
            notation += "#"

        self._history_entries.append((mover_piece.color, notation))

    def record_promotion(self, board, promoted_piece, position):
        """Record a user's promotion choice, resolved some time after the
        triggering move settled - so, like the airborne-capture case, it
        can't be folded into that move's own entry and is logged as its
        own "=X" entry instead.
        """
        square = square_name(position, board.height)
        self._history_entries.append((promoted_piece.color, f"{square}={promoted_piece.kind}"))

    def record_airborne_capture(self, board, attacker_piece, defender_piece, position):
        """`defender_piece` is credited as the mover of this entry - it's
        the one that acted (landed and captured), matching the accompanying
        `record_capture(defender_piece.color, ...)` call. `attacker_piece`
        is the one that got captured, not the actor.
        """
        square = square_name(position, board.height)
        self._history_entries.append(
            (defender_piece.color, f"{{{attacker_piece} captured mid-air by {defender_piece} at {square}}}")
        )

    def move_history(self):
        return [notation for _color, notation in self._history_entries]

    def moves_for_color(self, color):
        return [notation for entry_color, notation in self._history_entries if entry_color == color]

    def history_text(self):
        return " ".join(notation for _color, notation in self._history_entries)

    def history_entries(self):
        """The raw (color, notation) tuples, color included - unlike
        move_history()/history_text(), which discard it. Exists so a
        full-fidelity snapshot (see io/state_codec.py) can round-trip
        moves_for_color() correctly on the receiving end, not just the
        flattened notation strings.
        """
        return list(self._history_entries)

    def restore_history(self, entries):
        """Replace history wholesale with already-recorded (color,
        notation) entries - the counterpart to history_entries(), used
        only when rebuilding a GameState from a wire snapshot (see
        io/state_codec.py), never during normal play (record_move/
        record_promotion/record_airborne_capture are how live play
        appends entries one at a time).
        """
        self._history_entries = list(entries)

    # --- scores ---------------------------------------------------------

    def record_capture(self, capturing_color, value):
        self._scores[capturing_color] += value

    def scores(self):
        return dict(self._scores)

    # --- pending promotions ---------------------------------------------

    def schedule_promotion(self, position, color, choices, piece):
        self._pending_promotions.append(PendingPromotion(position, color, choices, piece))

    def get_pending_promotion(self, position):
        """Return the pending promotion at `position` without removing it, or None."""
        for pending in self._pending_promotions:
            if pending.position == position:
                return pending
        return None

    def take_pending_promotion(self, position):
        """Remove and return the pending promotion at `position`, or None."""
        pending = self.get_pending_promotion(position)
        if pending is not None:
            self._pending_promotions.remove(pending)
        return pending

    def has_pending_promotion(self):
        return len(self._pending_promotions) > 0

    def pending_promotions(self):
        return list(self._pending_promotions)

    # --- game over --------------------------------------------------------

    def set_game_over(self):
        self._game_over = True

    def is_game_over(self):
        return self._game_over