"""Config-driven, per-piece legal-move definitions: movement patterns,
occupancy requirements, promotion triggers, and piece values. Adding or
changing a piece means editing the data at the bottom of this file,
never rule_engine or engine code.

Movement patterns are built from generic primitives (StepPattern,
SlidePattern, PawnDoubleStepPattern) - adding a new piece, standard or a
user-defined custom one later, means composing a config entry from these,
never writing a new pattern class or touching rule_engine.
"""

from dataclasses import dataclass

from kungfu_chess.model.piece import (
    KING_TYPE,
    QUEEN_TYPE,
    ROOK_TYPE,
    BISHOP_TYPE,
    KNIGHT_TYPE,
    PAWN_TYPE,
    WHITE,
    BLACK,
)

# --- occupancy requirements -------------------------------------------
#
# Most pieces can land on an empty square or capture an enemy piece -
# that's ANY (still subject to the universal "never capture your own
# color" rule enforced by RuleEngine). The pawn is the first piece whose
# quiet move and its capture are two genuinely different patterns:
# MOVE_ONLY (must be empty - no forward captures) and CAPTURE_ONLY (must
# hold an enemy piece - no diagonal moves into empty squares).

ANY = "any"
MOVE_ONLY = "move_only"
CAPTURE_ONLY = "capture_only"


# --- generic movement pattern primitives -------------------------------

class StepPattern:
    """A single fixed offset hop (e.g. a king's one square, a knight's
    L-shape). Exactly one candidate destination per offset. There is no
    "path" to block for a single hop - that's why a knight jumps over
    blockers - so this pattern never looks at occupancy, only bounds.
    """

    def __init__(self, offsets):
        self._offsets = offsets  # list of (delta_row, delta_col)

    def destinations(self, board, row, col):
        results = []
        for delta_row, delta_col in self._offsets:
            target_row, target_col = row + delta_row, col + delta_col
            if board.in_bounds(target_row, target_col):
                results.append((target_row, target_col))
        return results


class SlidePattern:
    """Repeated movement along a direction until the board edge OR until
    an occupied cell is reached. The occupied cell itself is included as
    a candidate (a capture may be legal there); nothing past it is, since
    another piece is in the way. Whether landing on that occupied cell is
    *actually* legal (same color = no) is decided by RuleEngine, not
    here - this class only knows geometry + occupancy, not whose piece is
    whose.
    """

    def __init__(self, directions):
        self._directions = directions  # list of (delta_row, delta_col)

    def destinations(self, board, row, col):
        results = []
        for delta_row, delta_col in self._directions:
            target_row, target_col = row + delta_row, col + delta_col
            while board.in_bounds(target_row, target_col):
                results.append((target_row, target_col))
                if board.get(target_row, target_col) is not None:
                    break  # path blocked beyond this cell
                target_row += delta_row
                target_col += delta_col
        return results


class PawnDoubleStepPattern:
    """A pawn's two-square initial push. Legal only when the pawn is on
    its start row AND the square immediately in front is empty (path must
    be clear). Whether the destination itself is empty is enforced by
    RuleEngine via MOVE_ONLY, not here.

    forward_delta: (delta_row, delta_col) for one step forward.
    start_row_fn:  callable(board) -> int - the row the pawn must occupy
                   to be eligible for this move.
    """

    def __init__(self, forward_delta, start_row_fn):
        self._forward_delta = forward_delta
        self._start_row_fn = start_row_fn

    def destinations(self, board, row, col):
        if row != self._start_row_fn(board):
            return []

        delta_row, delta_col = self._forward_delta
        step_row, step_col = row + delta_row, col + delta_col
        if not board.in_bounds(step_row, step_col):
            return []
        if board.get(step_row, step_col) is not None:
            return []  # path is blocked

        dest_row, dest_col = step_row + delta_row, step_col + delta_col
        if not board.in_bounds(dest_row, dest_col):
            return []
        return [(dest_row, dest_col)]


# --- promotion trigger --------------------------------------------------

@dataclass(frozen=True)
class PromotionRule:
    """A single promotion trigger: a piece of a given color reaching a
    given rank becomes eligible to promote into one of `choices`.

    `rank` may be a fixed row index, or a callable(board) -> row index for
    ranks defined relative to board size (e.g. "the far edge row").

    `default_choice` is what the piece is auto-promoted to the instant the
    rank is reached, so play is never blocked on a human decision. It must
    be one of `choices`; when omitted it falls back to `choices[0]`. A
    player can still override it afterwards (see RuleEngine.apply_promotion_choice).
    """

    piece_type: str
    color: str
    rank: object  # int, or callable(board) -> int
    choices: tuple
    default_choice: object = None

    def rank_for(self, board):
        return self.rank(board) if callable(self.rank) else self.rank

    def default_for(self):
        return self.default_choice if self.default_choice is not None else self.choices[0]


# --- per-piece config data ----------------------------------------------

_ORTHOGONAL_DIRECTIONS = [(-1, 0), (1, 0), (0, -1), (0, 1)]
_DIAGONAL_DIRECTIONS = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
_KING_OFFSETS = _ORTHOGONAL_DIRECTIONS + _DIAGONAL_DIRECTIONS
_KNIGHT_OFFSETS = [
    (-2, -1), (-2, 1), (2, -1), (2, 1),
    (-1, -2), (-1, 2), (1, -2), (1, 2),
]

# White moves toward row 0, black moves toward higher row indices
# (confirmed convention - see test_piece_rules.py).
_WHITE_PAWN_FORWARD = [(-1, 0)]
_WHITE_PAWN_CAPTURES = [(-1, -1), (-1, 1)]
_BLACK_PAWN_FORWARD = [(1, 0)]
_BLACK_PAWN_CAPTURES = [(1, -1), (1, 1)]

# Start row for the two-square push: one row in from each color's edge -
# the row real chess pawns start on, not the back rank shared with the
# other pieces. White's edge is the last row (height - 1), so its pawns
# start on height - 2; black's edge is row 0, so its pawns start on row 1.
_WHITE_PAWN_START_ROW = lambda board: board.height - 2
_BLACK_PAWN_START_ROW = lambda board: 1

# Standard chess piece values, used for score display. The king's value
# is never actually awarded - capturing it ends the game first - but 0
# keeps the lookup total for every piece type.
PIECE_VALUES = {
    KING_TYPE: 0,
    QUEEN_TYPE: 9,
    ROOK_TYPE: 5,
    BISHOP_TYPE: 3,
    KNIGHT_TYPE: 3,
    PAWN_TYPE: 1,
}

# Which captured piece type(s) end the game instantly. Standard chess has
# exactly one (the king), but this is data, not an "if piece_type == king"
# check baked into RuleEngine - a custom ruleset could name a different
# piece, or several, as its game-ending target by editing this set alone.
GAME_ENDING_CAPTURE_TYPES = {KING_TYPE}

# Every piece type in `choices` a promotion may become. Kept separate
# from PROMOTION_RULES below so multiple rules can share it.
_STANDARD_PROMOTION_CHOICES = (QUEEN_TYPE, ROOK_TYPE, BISHOP_TYPE, KNIGHT_TYPE)

# Which piece becomes eligible to promote, on which rank, what it may
# become, and what it's auto-promoted to instantly (before any human
# chooses). To change the trigger (e.g. a knight promoting on the 4th
# rank instead) or the auto-promotion default (e.g. a rook by default),
# add/edit an entry here - PieceRules and RuleEngine never hardcode a
# piece type, rank, or default choice, so no other file needs to change.
PROMOTION_RULES = [
    PromotionRule(PAWN_TYPE, WHITE, 0, _STANDARD_PROMOTION_CHOICES, default_choice=QUEEN_TYPE),
    PromotionRule(
        PAWN_TYPE, BLACK, lambda board: board.height - 1, _STANDARD_PROMOTION_CHOICES, default_choice=QUEEN_TYPE
    ),
]

PIECE_MOVEMENT_PATTERNS = {
    KING_TYPE: [(StepPattern(_KING_OFFSETS), ANY)],
    QUEEN_TYPE: [(SlidePattern(_ORTHOGONAL_DIRECTIONS + _DIAGONAL_DIRECTIONS), ANY)],
    ROOK_TYPE: [(SlidePattern(_ORTHOGONAL_DIRECTIONS), ANY)],
    BISHOP_TYPE: [(SlidePattern(_DIAGONAL_DIRECTIONS), ANY)],
    KNIGHT_TYPE: [(StepPattern(_KNIGHT_OFFSETS), ANY)],
    PAWN_TYPE: {
        WHITE: [
            (StepPattern(_WHITE_PAWN_FORWARD), MOVE_ONLY),
            (StepPattern(_WHITE_PAWN_CAPTURES), CAPTURE_ONLY),
            (PawnDoubleStepPattern((-1, 0), _WHITE_PAWN_START_ROW), MOVE_ONLY),
        ],
        BLACK: [
            (StepPattern(_BLACK_PAWN_FORWARD), MOVE_ONLY),
            (StepPattern(_BLACK_PAWN_CAPTURES), CAPTURE_ONLY),
            (PawnDoubleStepPattern((1, 0), _BLACK_PAWN_START_ROW), MOVE_ONLY),
        ],
    },
}


# --- config-driven lookup facade -----------------------------------------

class PieceRules:
    """Query facade over the movement/promotion/value config above (or an
    injected variant of it - e.g. a test double with a custom piece).
    Knows nothing about *how* a shape is validated against the board or
    what settling a move should do - that orchestration is RuleEngine's
    job; this class only answers "what is configured".
    """

    def __init__(self, movement_patterns, promotion_rules, piece_values, game_ending_capture_types=None):
        self._movement_patterns = movement_patterns
        self._promotion_rules = promotion_rules
        self._piece_values = piece_values
        self._game_ending_capture_types = frozenset(game_ending_capture_types or ())

    def patterns_for(self, piece_type, color):
        entry = self._movement_patterns.get(piece_type, [])
        if isinstance(entry, dict):
            # Color-dependent movement (e.g. pawns move opposite directions).
            return entry.get(color, [])
        return entry

    @staticmethod
    def requirement_satisfied(requirement, target_piece, mover_color):
        """Whether a candidate destination's occupancy satisfies one of
        the three requirement kinds defined above (ANY/MOVE_ONLY/
        CAPTURE_ONLY). Capturing your own color is never satisfied by any
        requirement.
        """
        is_empty = target_piece is None
        if requirement == MOVE_ONLY:
            return is_empty
        if requirement == CAPTURE_ONLY:
            return not is_empty and target_piece.color != mover_color
        return is_empty or target_piece.color != mover_color

    def promotion_trigger_for(self, piece, to_row, board):
        """Return the PromotionRule matching this piece's arrival at
        to_row, or None if this landing doesn't trigger a promotion.
        """
        for rule in self._promotion_rules:
            if rule.piece_type == piece.kind and rule.color == piece.color and rule.rank_for(board) == to_row:
                return rule
        return None

    def value_of(self, piece):
        return self._piece_values[piece.kind]

    def ends_game_on_capture(self, captured_piece):
        """Whether capturing this piece ends the game outright (standard
        chess: only the king). Config-driven so RuleEngine never hardcodes
        a piece type here - see GAME_ENDING_CAPTURE_TYPES above.
        """
        return captured_piece.kind in self._game_ending_capture_types


def default_piece_rules():
    """The standard chess piece set, as configured above."""
    return PieceRules(PIECE_MOVEMENT_PATTERNS, PROMOTION_RULES, PIECE_VALUES, GAME_ENDING_CAPTURE_TYPES)