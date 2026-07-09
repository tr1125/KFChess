import io
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import run


def run_and_capture(input_text):
    out = io.StringIO()
    run(input_text, out)
    return out.getvalue()


# --- Iteration 1: parsing & validation ---

def test_parse_rectangular_board_3x4():
    input_text = (
        "Board:\n"
        "wK . . bK\n"
        ". . . . \n"
        "wR . . bR\n"
        "Commands:\n"
        "print board\n"
    )
    expected = "wK . . bK\n. . . .\nwR . . bR\n"
    assert run_and_capture(input_text) == expected


def test_parse_piece_tokens_and_colors():
    input_text = (
        "Board:\n"
        "wK . bQ\n"
        ". wN .\n"
        "bP . wR\n"
        "Commands:\n"
        "print board\n"
    )
    expected = "wK . bQ\n. wN .\nbP . wR\n"
    assert run_and_capture(input_text) == expected


def test_reject_unknown_token():
    input_text = "Board:\nwK xZ\n. .\nCommands:\n"
    assert run_and_capture(input_text) == "ERROR UNKNOWN_TOKEN\n"


def test_reject_row_width_mismatch():
    input_text = "Board:\nwK . .\n. bK\nCommands:\n"
    assert run_and_capture(input_text) == "ERROR ROW_WIDTH_MISMATCH\n"


# --- Iteration 2: click / wait / print board ---

def test_select_piece_by_center_click():
    input_text = (
        "Board:\n"
        "wK . .\n"
        ". . .\n"
        ". . .\n"
        "Commands:\n"
        "click 50 50\n"
        "click 150 150\n"
        "wait 1000\n"
        "print board\n"
    )
    expected = ". . .\n. wK .\n. . .\n"
    assert run_and_capture(input_text) == expected


def test_click_empty_cell_does_not_select():
    input_text = (
        "Board:\n"
        "wK . .\n"
        ". . .\n"
        ". . .\n"
        "Commands:\n"
        "click 150 150\n"
        "click 250 250\n"
        "wait 1000\n"
        "print board\n"
    )
    expected = "wK . .\n. . .\n. . .\n"
    assert run_and_capture(input_text) == expected


def test_click_outside_board_is_ignored():
    input_text = (
        "Board:\n"
        "wK . .\n"
        ". . .\n"
        ". . .\n"
        "Commands:\n"
        "click 350 50\n"
        "click -10 50\n"
        "print board\n"
    )
    expected = "wK . .\n. . .\n. . .\n"
    assert run_and_capture(input_text) == expected


def test_clicking_another_friendly_piece_replaces_selection():
    input_text = (
        "Board:\n"
        "wR . wK\n"
        ". . .\n"
        "Commands:\n"
        "click 50 50\n"
        "click 250 50\n"
        "click 250 150\n"
        "wait 1000\n"
        "print board\n"
    )
    expected = "wR . .\n. . wK\n"
    assert run_and_capture(input_text) == expected


def test_move_not_yet_settled_before_duration_elapses():
    """Not one of the failing VPL cases, but documents the design intent:
    a requested move only appears on the board once enough time has
    passed (see config.settings.MOVE_DURATION_MS)."""
    input_text = (
        "Board:\n"
        "wK . .\n"
        ". . .\n"
        ". . .\n"
        "Commands:\n"
        "click 50 50\n"
        "click 150 150\n"
        "wait 1\n"
        "print board\n"
    )
    expected = "wK . .\n. . .\n. . .\n"
    assert run_and_capture(input_text) == expected


# --- Iteration 5: movement over time, duration proportional to distance ---
# Confirmed by VPL: a 2-cell move takes 2000ms, not a flat 1000ms.

def test_multi_cell_slide_not_settled_just_before_duration_elapses():
    input_text = (
        "Board:\n"
        "wR . . .\n"
        ". . . .\n"
        ". . . .\n"
        "Commands:\n"
        "click 50 50\n"
        "click 350 50\n"
        "wait 2999\n"
        "print board\n"
    )
    expected = "wR . . .\n. . . .\n. . . .\n"
    assert run_and_capture(input_text) == expected


def test_two_cell_move_before_and_after_arrival():
    """Exact VPL case: a 2-cell rook move must NOT be settled after only
    1000ms (1 cell's worth) - only after the full 2000ms (2 cells)."""
    input_text = (
        "Board:\n"
        "wR . .\n"
        "Commands:\n"
        "click 50 50\n"
        "click 250 50\n"
        "wait 1000\n"
        "print board\n"
        "wait 1000\n"
        "print board\n"
    )
    expected = "wR . .\n. . wR\n"
    assert run_and_capture(input_text) == expected


def test_multi_cell_slide_settled_once_duration_elapses():
    input_text = (
        "Board:\n"
        "wR . . .\n"
        ". . . .\n"
        ". . . .\n"
        "Commands:\n"
        "click 50 50\n"
        "click 350 50\n"
        "wait 3000\n"
        "print board\n"
    )
    expected = ". . . wR\n. . . .\n. . . .\n"
    assert run_and_capture(input_text) == expected


def test_illegal_shape_move_is_never_scheduled_even_after_waiting():
    # A rook cannot move diagonally - the click should be a no-op, so no
    # amount of waiting should ever move it.
    input_text = (
        "Board:\n"
        "wR . .\n"
        ". . .\n"
        ". . .\n"
        "Commands:\n"
        "click 50 50\n"
        "click 250 250\n"
        "wait 5000\n"
        "print board\n"
    )
    expected = "wR . .\n. . .\n. . .\n"
    assert run_and_capture(input_text) == expected


# --- Iteration 6: no redirecting a piece mid-route; no cooldown after arrival ---

def test_piece_cannot_be_reselected_while_still_in_transit():
    # wR moves (0,0) -> (0,2): 2 cells = 2000ms. While in transit, clicking
    # its (still-displayed) origin square must not select it, so a second
    # click elsewhere must not redirect it either.
    input_text = (
        "Board:\n"
        "wR . .\n"
        ". . .\n"
        "Commands:\n"
        "click 50 50\n"
        "click 250 50\n"
        "wait 500\n"
        "click 50 50\n"
        "click 50 150\n"
        "wait 1500\n"
        "print board\n"
    )
    # If redirection were possible, the rook would end up at (1,0) instead.
    expected = ". . wR\n. . .\n"
    assert run_and_capture(input_text) == expected


def test_piece_can_move_again_immediately_after_arrival_no_cooldown():
    input_text = (
        "Board:\n"
        "wR . .\n"
        ". . .\n"
        "Commands:\n"
        "click 50 50\n"
        "click 250 50\n"
        "wait 2000\n"
        "click 250 50\n"
        "click 250 150\n"
        "wait 1000\n"
        "print board\n"
    )
    expected = ". . .\n. . wR\n"
    assert run_and_capture(input_text) == expected


# --- Iteration 7: advanced real-time interaction cases ---

def test_enemy_collision_capture_on_arrival():
    """A piece that arrives at a square occupied by an enemy captures it.
    The captured token is simply overwritten; no special capture logic is
    needed beyond applying the move."""
    input_text = (
        "Board:\n"
        "wR . bK\n"
        ". . .\n"
        ". . .\n"
        "Commands:\n"
        "click 50 50\n"   # select wR (row=0, col=0)
        "click 250 50\n"  # move wR to (row=0, col=2) - 2 cells, 2000ms
        "wait 2000\n"
        "print board\n"
    )
    expected = ". . wR\n. . .\n. . .\n"
    assert run_and_capture(input_text) == expected


def test_premove_is_blocked_while_enemy_is_in_transit():
    """While an enemy piece is in flight the local player cannot queue a
    new move.  The attempted click sequence must be a complete no-op."""
    input_text = (
        "Board:\n"
        "bR . .\n"
        ". . .\n"
        ". . wK\n"
        "Commands:\n"
        "click 50 50\n"    # select bR (row=0, col=0)
        "click 50 250\n"   # move bR to (row=2, col=0) - 2 cells, 2000ms
        "wait 500\n"       # bR still in transit
        "click 250 250\n"  # try to select wK (row=2, col=2)
        "click 150 150\n"  # try to move wK to (row=1, col=1) - must be blocked
        "wait 2000\n"      # bR settles; wK never moved
        "print board\n"
    )
    expected = ". . .\n. . .\nbR . wK\n"
    assert run_and_capture(input_text) == expected


def test_friendly_piece_at_destination_cancels_in_transit_move():
    """If a friendly piece occupies the destination by the time a second
    piece arrives there, the second move is silently cancelled - the piece
    stays at its origin rather than overwriting its teammate."""
    input_text = (
        "Board:\n"
        "wR . .\n"
        ". . wK\n"
        "Commands:\n"
        "click 250 150\n"  # select wK (row=1, col=2)
        "click 250 50\n"   # queue wK -> (row=0, col=2): 1 cell, arrives 1000ms
        "click 50 50\n"    # select wR (row=0, col=0)
        "click 250 50\n"   # queue wR -> (row=0, col=2): 2 cells, arrives 2000ms
        "wait 2000\n"      # wK arrives first; wR's move is cancelled at landing
        "print board\n"
    )
    # wK moved to (0,2).  wR stayed at (0,0) because (0,2) was already
    # friendly-occupied when wR arrived.
    expected = "wR . wK\n. . .\n"
    assert run_and_capture(input_text) == expected


def test_movement_conflict_first_registered_piece_wins_destination():
    """When two friendly pieces are both headed for the same empty square
    and arrive at the same instant, the first-registered move is applied
    and the second is cancelled (piece stays at its origin)."""
    input_text = (
        "Board:\n"
        "wR . .\n"
        ". . .\n"
        ". . wK\n"
        "Commands:\n"
        "click 50 50\n"    # select wR (row=0, col=0)
        "click 250 50\n"   # queue wR -> (row=0, col=2): 2 cells, arrives 2000ms
        "click 250 250\n"  # select wK (row=2, col=2)
        "click 250 50\n"   # queue wK -> (row=0, col=2): 2 cells, arrives 2000ms
        "wait 2000\n"      # both complete; wR registered first, so wR wins
        "print board\n"
    )
    # wR occupies (0,2).  wK is cancelled, stays at (2,2).
    expected = ". . wR\n. . .\n. . wK\n"
    assert run_and_capture(input_text) == expected


# --- Iteration 8: game-over on king capture ---

def test_capturing_enemy_king_ends_the_game():
    """When a piece lands on the enemy king, the game is over and the
    board reflects the capture (the king token is gone)."""
    input_text = (
        "Board:\n"
        "wR . bK\n"
        ". . .\n"
        "Commands:\n"
        "click 50 50\n"   # select wR (row=0, col=0)
        "click 250 50\n"  # move wR -> (row=0, col=2): 2 cells, arrives 2000ms
        "wait 2000\n"
        "print board\n"
    )
    # wR has captured bK; bK is gone.
    expected = ". . wR\n. . .\n"
    assert run_and_capture(input_text) == expected


def test_move_commands_ignored_after_game_over():
    """Once the enemy king is captured, all subsequent click and wait
    commands are no-ops - no piece on the board moves."""
    input_text = (
        "Board:\n"
        "wR . bK\n"
        ". wK .\n"
        "Commands:\n"
        "click 50 50\n"   # select wR (row=0, col=0)
        "click 250 50\n"  # move wR -> (row=0, col=2): captures bK, 2000ms
        "wait 2000\n"     # bK captured; game over
        "click 150 150\n" # try to select wK (row=1, col=1) - ignored
        "click 50 150\n"  # try to move wK to (row=1, col=0) - ignored
        "wait 1000\n"     # ignored
        "print board\n"
    )
    # wR sits at (0,2) from the capture; wK remains at (1,1) unmoved.
    expected = ". . wR\n. wK .\n"
    assert run_and_capture(input_text) == expected


# --- Iteration 9: pawn promotion and two-square initial push ---

def test_white_pawn_reaching_row_zero_becomes_queen():
    """A white pawn that settles on row 0 is immediately replaced by a
    white queen on the same square."""
    input_text = (
        "Board:\n"
        "wK . . bK\n"
        ". wP . .\n"
        ". . . .\n"
        "Commands:\n"
        "click 150 150\n"  # select wP at (row=1, col=1)
        "click 150 50\n"   # move one step to (row=0, col=1): 1 cell, 1000ms
        "wait 1000\n"
        "print board\n"
    )
    expected = "wK wQ . bK\n. . . .\n. . . .\n"
    assert run_and_capture(input_text) == expected


def test_black_pawn_reaching_last_row_becomes_queen():
    """A black pawn that settles on the last row is immediately replaced by
    a black queen on the same square."""
    input_text = (
        "Board:\n"
        "wK . . bK\n"
        ". . . .\n"
        ". bP . .\n"
        ". . . .\n"
        "Commands:\n"
        "click 150 250\n"  # select bP at (row=2, col=1)
        "click 150 350\n"  # move one step to (row=3, col=1): 1 cell, 1000ms
        "wait 1000\n"
        "print board\n"
    )
    expected = "wK . . bK\n. . . .\n. . . .\n. bQ . .\n"
    assert run_and_capture(input_text) == expected


def test_white_pawn_two_square_push_from_start_row():
    """A white pawn on its start row (the board's last row, height - 1)
    can advance two squares if the path is clear."""
    input_text = (
        "Board:\n"
        "wK . . bK\n"
        ". . . .\n"
        ". . . .\n"
        ". . . .\n"
        ". wP . .\n"
        "Commands:\n"
        "click 150 450\n"  # select wP at (row=4, col=1); start row = height-1 = 4
        "click 150 250\n"  # move two squares to (row=2, col=1): 2 cells, 2000ms
        "wait 2000\n"
        "print board\n"
    )
    expected = "wK . . bK\n. . . .\n. wP . .\n. . . .\n. . . .\n"
    assert run_and_capture(input_text) == expected


def test_white_pawn_two_square_push_blocked_by_piece_on_path():
    """A two-square push is illegal when the intermediate square is
    occupied - the move should never be scheduled."""
    input_text = (
        "Board:\n"
        "wK . . bK\n"
        ". . . .\n"
        ". . . .\n"
        ". bN . .\n"
        ". wP . .\n"
        "Commands:\n"
        "click 150 450\n"  # select wP at (row=4, col=1); start row = height-1 = 4
        "click 150 250\n"  # attempt two-square push - blocked by bN at row=3
        "wait 3000\n"
        "print board\n"
    )
    # wP must not move - illegal push through blocker.
    expected = "wK . . bK\n. . . .\n. . . .\n. bN . .\n. wP . .\n"
    assert run_and_capture(input_text) == expected