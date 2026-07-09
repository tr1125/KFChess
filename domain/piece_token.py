"""A token is a 2-character string: color (w/b) + piece type (K/Q/R/B/N/P).
Centralizing the split here means if the token format ever changes,
this is the only file that needs to change.

Piece-type letters are also centralized here so engine and config code
share one source of truth instead of each hardcoding "K"/"P"/"Q".
"""

KING_TYPE = "K"
QUEEN_TYPE = "Q"
ROOK_TYPE = "R"
BISHOP_TYPE = "B"
KNIGHT_TYPE = "N"
PAWN_TYPE = "P"


def color_of(token):
    return token[0]


def type_of(token):
    return token[1]