"""These tests check movement legality against the real rules of chess,
not against any specific VPL fixture. They exist to validate the design
on its own terms - if VPL tests are added later, they verify the same
logic from a different angle, they don't define it.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from domain.board import Board
from domain.movement.movement_rules import MovementRules
from config.piece_definitions import PIECE_MOVEMENT_PATTERNS


def make_rules():
    return MovementRules(PIECE_MOVEMENT_PATTERNS)


def empty_board(size=5):
    return Board([["."] * size for _ in range(size)])


# --- King: one square, any direction ---

def test_king_one_step_orthogonal_is_legal():
    board = empty_board()
    assert make_rules().is_legal("K", board, 2, 2, 2, 3)


def test_king_one_step_diagonal_is_legal():
    board = empty_board()
    assert make_rules().is_legal("K", board, 2, 2, 3, 3)


def test_king_two_squares_is_illegal():
    board = empty_board()
    assert not make_rules().is_legal("K", board, 2, 2, 2, 4)


# --- Rook: any distance, orthogonal only ---

def test_rook_straight_line_is_legal():
    board = empty_board()
    assert make_rules().is_legal("R", board, 0, 0, 0, 4)


def test_rook_diagonal_is_illegal():
    board = empty_board()
    assert not make_rules().is_legal("R", board, 0, 0, 2, 2)


# --- Bishop: any distance, diagonal only ---

def test_bishop_diagonal_is_legal():
    board = empty_board()
    assert make_rules().is_legal("B", board, 0, 0, 3, 3)


def test_bishop_straight_line_is_illegal():
    board = empty_board()
    assert not make_rules().is_legal("B", board, 0, 0, 0, 3)


# --- Queen: any distance, straight or diagonal ---

def test_queen_straight_line_is_legal():
    board = empty_board()
    assert make_rules().is_legal("Q", board, 1, 1, 1, 4)


def test_queen_diagonal_is_legal():
    board = empty_board()
    assert make_rules().is_legal("Q", board, 1, 1, 3, 3)


def test_queen_knight_shape_is_illegal():
    board = empty_board()
    assert not make_rules().is_legal("Q", board, 1, 1, 3, 2)


# --- Knight: L-shape only ---

def test_knight_l_shape_is_legal():
    board = empty_board()
    assert make_rules().is_legal("N", board, 2, 2, 0, 1)


def test_knight_straight_line_is_illegal():
    board = empty_board()
    assert not make_rules().is_legal("N", board, 2, 2, 2, 4)


def test_knight_diagonal_is_illegal():
    board = empty_board()
    assert not make_rules().is_legal("N", board, 2, 2, 4, 4)


# --- Off-board destinations are never legal ---

def test_destination_off_board_is_illegal():
    board = empty_board()
    assert not make_rules().is_legal("R", board, 0, 0, 0, 10)