"""A token is a 2-character string: color (w/b) + piece type (K/Q/R/B/N/P).
Centralizing the split here means if the token format ever changes,
this is the only file that needs to change.
"""


def color_of(token):
    return token[0]


def type_of(token):
    return token[1]