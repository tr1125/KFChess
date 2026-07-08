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


def board_from(rows):
    return Board(rows)


def empty_board(size=5):
    return board_from([["."] * size for _ in range(size)])


# --- King: one square, any direction ---

def test_king_one_step_orthogonal_is_legal():
    board = empty_board()
    assert make_rules().is_legal("wK", board, 2, 2, 2, 3)


def test_king_one_step_diagonal_is_legal():
    board = empty_board()
    assert make_rules().is_legal("wK", board, 2, 2, 3, 3)


def test_king_two_squares_is_illegal():
    board = empty_board()
    assert not make_rules().is_legal("wK", board, 2, 2, 2, 4)


# --- Rook: any distance, orthogonal only ---

def test_rook_straight_line_is_legal():
    board = empty_board()
    assert make_rules().is_legal("wR", board, 0, 0, 0, 4)


def test_rook_diagonal_is_illegal():
    board = empty_board()
    assert not make_rules().is_legal("wR", board, 0, 0, 2, 2)


# --- Bishop: any distance, diagonal only ---

def test_bishop_diagonal_is_legal():
    board = empty_board()
    assert make_rules().is_legal("wB", board, 0, 0, 3, 3)


def test_bishop_straight_line_is_illegal():
    board = empty_board()
    assert not make_rules().is_legal("wB", board, 0, 0, 0, 3)


# --- Queen: any distance, straight or diagonal ---

def test_queen_straight_line_is_legal():
    board = empty_board()
    assert make_rules().is_legal("wQ", board, 1, 1, 1, 4)


def test_queen_diagonal_is_legal():
    board = empty_board()
    assert make_rules().is_legal("wQ", board, 1, 1, 3, 3)


def test_queen_knight_shape_is_illegal():
    board = empty_board()
    assert not make_rules().is_legal("wQ", board, 1, 1, 3, 2)


# --- Knight: L-shape only ---

def test_knight_l_shape_is_legal():
    board = empty_board()
    assert make_rules().is_legal("wN", board, 2, 2, 0, 1)


def test_knight_straight_line_is_illegal():
    board = empty_board()
    assert not make_rules().is_legal("wN", board, 2, 2, 2, 4)


def test_knight_diagonal_is_illegal():
    board = empty_board()
    assert not make_rules().is_legal("wN", board, 2, 2, 4, 4)


# --- Off-board destinations are never legal ---

def test_destination_off_board_is_illegal():
    board = empty_board()
    assert not make_rules().is_legal("wR", board, 0, 0, 0, 10)


# --- Blocking: sliding pieces cannot move through another piece ---

def test_rook_cannot_move_through_a_blocker():
    # wR at (0,0), a piece sitting at (0,2), destination (0,4) is past it.
    rows = [
        ["wR", ".", "wN", ".", "."],
        [".", ".", ".", ".", "."],
        [".", ".", ".", ".", "."],
        [".", ".", ".", ".", "."],
        [".", ".", ".", ".", "."],
    ]
    board = board_from(rows)
    assert not make_rules().is_legal("wR", board, 0, 0, 0, 4)


def test_rook_can_capture_enemy_piece_at_blocker_position():
    rows = [
        ["wR", ".", "bN", ".", "."],
        [".", ".", ".", ".", "."],
        [".", ".", ".", ".", "."],
        [".", ".", ".", ".", "."],
        [".", ".", ".", ".", "."],
    ]
    board = board_from(rows)
    assert make_rules().is_legal("wR", board, 0, 0, 0, 2)


def test_rook_cannot_land_on_own_piece():
    rows = [
        ["wR", ".", "wN", ".", "."],
        [".", ".", ".", ".", "."],
        [".", ".", ".", ".", "."],
        [".", ".", ".", ".", "."],
        [".", ".", ".", ".", "."],
    ]
    board = board_from(rows)
    assert not make_rules().is_legal("wR", board, 0, 0, 0, 2)


def test_bishop_cannot_move_through_a_blocker():
    rows = [
        ["wB", ".", ".", ".", "."],
        [".", "wN", ".", ".", "."],
        [".", ".", ".", ".", "."],
        [".", ".", ".", "bN", "."],
        [".", ".", ".", ".", "."],
    ]
    board = board_from(rows)
    assert not make_rules().is_legal("wB", board, 0, 0, 3, 3)


def test_knight_can_jump_over_blockers():
    rows = [
        ["wN", "bN", "."],
        ["bN", "bN", "."],
        [".", ".", "."],
    ]
    board = board_from(rows)
    # every square surrounding the knight is occupied; it still reaches (2, 1)
    assert make_rules().is_legal("wN", board, 0, 0, 2, 1)


# --- Capture rules apply the same way to every piece ---

def test_cannot_capture_own_color():
    rows = [
        ["wK", "wN"],
        [".", "."],
    ]
    board = board_from(rows)
    assert not make_rules().is_legal("wK", board, 0, 0, 0, 1)


def test_can_capture_enemy_color():
    rows = [
        ["wK", "bN"],
        [".", "."],
    ]
    board = board_from(rows)
    assert make_rules().is_legal("wK", board, 0, 0, 0, 1)