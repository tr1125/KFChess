from kungfu_chess.model.board import Board
from kungfu_chess.model.piece import Piece, PieceState
from kungfu_chess.model.position import Position
from kungfu_chess.realtime.motion import PendingMove
from kungfu_chess.realtime.real_time_arbiter import RealTimeArbiter, CollisionKind


def board_from(rows):
    return Board([[None if cell == "." else Piece(color=cell[0], kind=cell[1]) for cell in row] for row in rows])


def leg(current_position, leg_target, piece, remaining_path=(), steps_completed=0):
    return PendingMove(
        current_position=current_position,
        leg_target=leg_target,
        remaining_path=tuple(remaining_path),
        leg_started_at_ms=0,
        complete_at_ms=0,
        piece=piece,
        steps_completed=steps_completed,
    )


def classify(board, move):
    return RealTimeArbiter().classify(board, move)


def test_mover_gone_when_current_position_is_empty():
    board = board_from([[".", "."]])  # the piece the leg refers to is no longer at (0, 0)
    mover = Piece(color="w", kind="R")  # never placed on the board
    move = leg(Position(0, 0), Position(0, 1), mover)
    outcome = classify(board, move)
    assert outcome.kind == CollisionKind.MOVER_GONE


def test_mover_gone_when_a_different_piece_now_occupies_current_position():
    """Identity, not just color+kind, decides whether the mover is still
    there - a second, otherwise-identical white rook at the same cell is
    not the piece this leg was scheduled for.
    """
    board = board_from([["wR", "."]])
    impostor = Piece(color="w", kind="R")  # same color/kind as board.get(0, 0), different object
    move = leg(Position(0, 0), Position(0, 1), impostor)
    outcome = classify(board, move)
    assert outcome.kind == CollisionKind.MOVER_GONE


def test_friendly_block_when_leg_target_occupied_by_same_color():
    board = board_from([["wR", "wN"]])
    move = leg(Position(0, 0), Position(0, 1), board.get(0, 0))
    outcome = classify(board, move)
    assert outcome.kind == CollisionKind.FRIENDLY_BLOCK


def test_enemy_capture_when_leg_target_holds_a_grounded_enemy():
    board = board_from([["wR", "bN"]])
    move = leg(Position(0, 0), Position(0, 1), board.get(0, 0))
    outcome = classify(board, move)
    assert outcome.kind == CollisionKind.ENEMY_CAPTURE


def test_clear_when_leg_target_holds_an_airborne_enemy():
    """An enemy currently AIRBORNE is safely passable - no collision here
    at all; any capture only happens at its own landing instant (see
    GameEngine._land_due_jumps), not when another piece arrives on its
    cell mid-flight.
    """
    board = board_from([["wR", "bN"]])
    board.get(0, 1).state = PieceState.AIRBORNE
    move = leg(Position(0, 0), Position(0, 1), board.get(0, 0))
    outcome = classify(board, move)
    assert outcome.kind == CollisionKind.CLEAR


def test_friendly_block_even_when_that_friendly_piece_is_airborne():
    """passes_as_empty only vacates a cell for an *enemy* of the mover -
    a friendly piece's own airborne teammate still blocks/stops normally,
    exactly like any other friendly occupant.
    """
    board = board_from([["wR", "wN"]])
    board.get(0, 1).state = PieceState.AIRBORNE
    move = leg(Position(0, 0), Position(0, 1), board.get(0, 0))
    outcome = classify(board, move)
    assert outcome.kind == CollisionKind.FRIENDLY_BLOCK


def test_clear_for_a_move_to_an_empty_leg_target():
    board = board_from([["wR", "."]])
    move = leg(Position(0, 0), Position(0, 1), board.get(0, 0))
    outcome = classify(board, move)
    assert outcome.kind == CollisionKind.CLEAR


def test_mover_gone_takes_priority_over_friendly_occupied_leg_target():
    board = board_from([[".", "wN"]])  # mover vanished; leg target happens to be friendly
    mover = Piece(color="w", kind="R")
    move = leg(Position(0, 0), Position(0, 1), mover)
    outcome = classify(board, move)
    assert outcome.kind == CollisionKind.MOVER_GONE
