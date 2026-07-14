from kungfu_chess.model.board import Board
from kungfu_chess.model.piece import Piece
from kungfu_chess.model.position import Position
from kungfu_chess.realtime.motion import MotionTracker, PendingMove
from kungfu_chess.realtime.real_time_arbiter import RealTimeArbiter, CollisionKind


def board_from(rows):
    return Board([[None if cell == "." else Piece(color=cell[0], kind=cell[1]) for cell in row] for row in rows])


def classify(board, move, motion=None):
    motion = motion if motion is not None else MotionTracker()
    return RealTimeArbiter().classify(board, motion, move)


def test_mover_gone_when_source_is_empty():
    board = board_from([[".", "."]])  # the piece the move refers to is no longer at (0, 0)
    mover = Piece(color="w", kind="R")  # never placed on the board
    move = PendingMove(Position(0, 0), Position(0, 1), complete_at_ms=0, piece=mover)
    outcome = classify(board, move)
    assert outcome.kind == CollisionKind.MOVER_GONE


def test_mover_gone_when_a_different_piece_now_occupies_the_source():
    """Identity, not just color+kind, decides whether the mover is still
    there - a second, otherwise-identical white rook at the same cell is
    not the piece this move was scheduled for.
    """
    board = board_from([["wR", "."]])
    impostor = Piece(color="w", kind="R")  # same color/kind as board.get(0, 0), different object
    move = PendingMove(Position(0, 0), Position(0, 1), complete_at_ms=0, piece=impostor)
    outcome = classify(board, move)
    assert outcome.kind == CollisionKind.MOVER_GONE


def test_friendly_cancel_when_destination_occupied_by_same_color():
    board = board_from([["wR", "wN"]])
    move = PendingMove(Position(0, 0), Position(0, 1), complete_at_ms=0, piece=board.get(0, 0))
    outcome = classify(board, move)
    assert outcome.kind == CollisionKind.FRIENDLY_CANCEL


def test_airborne_capture_when_destination_enemy_is_airborne():
    board = board_from([["wR", "bN"]])
    motion = MotionTracker()
    motion.schedule_jump(Position(0, 1), piece=board.get(0, 1), land_at_ms=100)
    move = PendingMove(Position(0, 0), Position(0, 1), complete_at_ms=0, piece=board.get(0, 0))
    outcome = classify(board, move, motion=motion)
    assert outcome.kind == CollisionKind.AIRBORNE_CAPTURE
    assert outcome.defender_piece is board.get(0, 1)


def test_clear_for_a_normal_capture_of_a_grounded_enemy():
    board = board_from([["wR", "bN"]])
    move = PendingMove(Position(0, 0), Position(0, 1), complete_at_ms=0, piece=board.get(0, 0))
    outcome = classify(board, move)
    assert outcome.kind == CollisionKind.CLEAR


def test_clear_for_a_move_to_an_empty_destination():
    board = board_from([["wR", "."]])
    move = PendingMove(Position(0, 0), Position(0, 1), complete_at_ms=0, piece=board.get(0, 0))
    outcome = classify(board, move)
    assert outcome.kind == CollisionKind.CLEAR


def test_mover_gone_takes_priority_over_friendly_occupied_destination():
    board = board_from([[".", "wN"]])  # mover vanished; destination happens to be friendly
    mover = Piece(color="w", kind="R")
    move = PendingMove(Position(0, 0), Position(0, 1), complete_at_ms=0, piece=mover)
    outcome = classify(board, move)
    assert outcome.kind == CollisionKind.MOVER_GONE


def test_friendly_occupied_takes_priority_over_airborne():
    """An airborne friendly piece is still just a friendly-occupied
    destination - airborne only matters for enemy defenders."""
    board = board_from([["wR", "wN"]])
    motion = MotionTracker()
    motion.schedule_jump(Position(0, 1), piece=board.get(0, 1), land_at_ms=100)
    move = PendingMove(Position(0, 0), Position(0, 1), complete_at_ms=0, piece=board.get(0, 0))
    outcome = classify(board, move, motion=motion)
    assert outcome.kind == CollisionKind.FRIENDLY_CANCEL
