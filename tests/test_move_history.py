"""Unit tests for MoveHistory's algebraic-notation formatting, direct
tests of MoveResolver's recording behavior (including the branches that
must NOT record anything), and a couple of end-to-end checks that
GameEngine wires everything together correctly.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from domain.board import Board
from domain.movement.movement_rules import MovementRules
from config.piece_definitions import PIECE_MOVEMENT_PATTERNS
from engine.clock import ManualClock
from engine.game_engine import GameEngine
from engine.move_history import MoveHistory
from engine.move_scheduler import MoveScheduler, PendingMove
from engine.jump_scheduler import JumpScheduler
from engine.move_resolver import MoveResolver


def empty_board(size=8):
    return Board([["."] * size for _ in range(size)])


# --- MoveHistory: square naming and move formatting ---

def test_pawn_move_has_no_prefix():
    history = MoveHistory()
    history.record_move(empty_board(), "wP", 6, 4, 4, 4)  # e2-e4
    assert history.entries() == ["e4"]


def test_pawn_capture_prefixes_origin_file():
    history = MoveHistory()
    history.record_move(empty_board(), "wP", 2, 4, 3, 3, captured_token="bP")  # exd5
    assert history.entries() == ["exd5"]


def test_piece_move_prefixes_piece_letter():
    history = MoveHistory()
    history.record_move(empty_board(), "wN", 7, 6, 5, 5)  # Nf3
    assert history.entries() == ["Nf3"]


def test_piece_capture_includes_x():
    history = MoveHistory()
    history.record_move(empty_board(), "wN", 7, 6, 5, 5, captured_token="bP")
    assert history.entries() == ["Nxf3"]


def test_promotion_appends_equals_new_type():
    history = MoveHistory()
    history.record_move(empty_board(), "wP", 1, 4, 0, 4, promoted_token="wQ")  # e8=Q
    assert history.entries() == ["e8=Q"]


def test_capture_promotion_combines_both():
    history = MoveHistory()
    history.record_move(
        empty_board(), "wP", 1, 3, 0, 4, captured_token="bR", promoted_token="wQ"
    )
    assert history.entries() == ["dxe8=Q"]


def test_ends_game_appends_hash():
    history = MoveHistory()
    history.record_move(empty_board(), "wQ", 4, 4, 0, 4, captured_token="bK", ends_game=True)
    assert history.entries() == ["Qxe8#"]


def test_airborne_capture_is_recorded_as_comment():
    history = MoveHistory()
    history.record_airborne_capture(empty_board(), "bN", "wK", 4, 4)
    assert history.entries() == ["{bN captured mid-air by wK at e4}"]


def test_entries_are_appended_in_order():
    history = MoveHistory()
    history.record_move(empty_board(), "wP", 6, 4, 4, 4)
    history.record_move(empty_board(), "bP", 1, 3, 3, 3)
    assert history.entries() == ["e4", "d5"]


def test_str_joins_entries_with_spaces():
    history = MoveHistory()
    history.record_move(empty_board(), "wP", 6, 4, 4, 4)
    history.record_move(empty_board(), "bP", 1, 3, 3, 3)
    assert str(history) == "e4 d5"


# --- MoveResolver: only genuinely settled outcomes get recorded ---

def make_resolver(rows):
    board = Board(rows)
    jumps = JumpScheduler()
    history = MoveHistory()
    return MoveResolver(board, jumps, history), board, jumps, history


def test_resolver_records_a_normal_move():
    rows = [["wR", "."]]
    resolver, board, jumps, history = make_resolver(rows)
    move = PendingMove(0, 0, 0, 1, complete_at_ms=0, mover_token="wR")
    assert resolver.resolve(move) is False
    assert history.entries() == ["Rb1"]


def test_resolver_records_a_capture_and_signals_game_over_on_king():
    rows = [["wQ", "bK"]]
    resolver, board, jumps, history = make_resolver(rows)
    move = PendingMove(0, 0, 0, 1, complete_at_ms=0, mover_token="wQ")
    assert resolver.resolve(move) is True
    assert history.entries() == ["Qxb1#"]


def test_resolver_does_not_record_when_mover_already_gone():
    rows = [[".", "."]]  # mover_token "wR" no longer at (0,0)
    resolver, board, jumps, history = make_resolver(rows)
    move = PendingMove(0, 0, 0, 1, complete_at_ms=0, mover_token="wR")
    assert resolver.resolve(move) is False
    assert history.entries() == []


def test_resolver_does_not_record_a_friendly_cancel():
    rows = [["wR", "wN"]]  # destination occupied by a friendly piece
    resolver, board, jumps, history = make_resolver(rows)
    move = PendingMove(0, 0, 0, 1, complete_at_ms=0, mover_token="wR")
    assert resolver.resolve(move) is False
    assert history.entries() == []


def test_resolver_records_airborne_capture_as_comment_not_a_move():
    rows = [["wR", "bN"]]
    resolver, board, jumps, history = make_resolver(rows)
    jumps.schedule(0, 1, token="bN", land_at_ms=100)  # bN is airborne at destination
    move = PendingMove(0, 0, 0, 1, complete_at_ms=0, mover_token="wR")
    assert resolver.resolve(move) is False
    assert history.entries() == ["{wR captured mid-air by bN at b1}"]
    assert board.get(0, 0) == "."  # the arriving wR was removed, not moved


# --- End-to-end: GameEngine wires MoveResolver/MoveHistory together ---

def click_cell(engine, row, col):
    engine.click(col * 100 + 50, row * 100 + 50)


def make_engine(rows):
    board = Board(rows)
    clock = ManualClock()
    movement_rules = MovementRules(PIECE_MOVEMENT_PATTERNS)
    return GameEngine(board, clock, movement_rules), clock


def test_engine_records_a_settled_move():
    rows = [
        ["bK", ".", "."],
        [".", ".", "."],
        [".", ".", "wR"],
    ]
    engine, clock = make_engine(rows)
    click_cell(engine, 2, 2)  # select wR
    click_cell(engine, 2, 0)  # request move to (2, 0)
    engine.wait(2000)  # 2-cell rook move settles
    assert engine.move_history() == ["Ra1"]


def test_engine_uses_injected_history_and_resolver():
    rows = [
        ["bK", ".", "."],
        [".", ".", "."],
        [".", ".", "wR"],
    ]
    board = Board(rows)
    clock = ManualClock()
    movement_rules = MovementRules(PIECE_MOVEMENT_PATTERNS)
    moves = MoveScheduler()
    jumps = JumpScheduler()
    history = MoveHistory()
    resolver = MoveResolver(board, jumps, history)

    engine = GameEngine(
        board, clock, movement_rules, moves=moves, jumps=jumps, history=history, resolver=resolver
    )
    click_cell(engine, 2, 2)
    click_cell(engine, 2, 0)
    engine.wait(2000)

    assert engine.move_history() == ["Ra1"]
    assert history.entries() == ["Ra1"]  # the injected instance itself was mutated
