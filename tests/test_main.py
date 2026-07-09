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
    input_text = (
        "Board:\n"
        "wR . bK\n"
        ". . .\n"
        ". . .\n"
        "Commands:\n"
        "click 50 50\n"
        "click 250 50\n"
        "wait 2000\n"
        "print board\n"
    )
    expected = ". . wR\n. . .\n. . .\n"
    assert run_and_capture(input_text) == expected


def test_premove_is_blocked_while_enemy_is_in_transit():
    input_text = (
        "Board:\n"
        "bR . .\n"
        ". . .\n"
        ". . wK\n"
        "Commands:\n"
        "click 50 50\n"
        "click 50 250\n"
        "wait 500\n"
        "click 250 250\n"
        "click 150 150\n"
        "wait 2000\n"
        "print board\n"
    )
    expected = ". . .\n. . .\nbR . wK\n"
    assert run_and_capture(input_text) == expected


def test_friendly_piece_at_destination_cancels_in_transit_move():
    input_text = (
        "Board:\n"
        "wR . .\n"
        ". . wK\n"
        "Commands:\n"
        "click 250 150\n"
        "click 250 50\n"
        "click 50 50\n"
        "click 250 50\n"
        "wait 2000\n"
        "print board\n"
    )
    expected = "wR . wK\n. . .\n"
    assert run_and_capture(input_text) == expected


def test_movement_conflict_first_registered_piece_wins_destination():
    input_text = (
        "Board:\n"
        "wR . .\n"
        ". . .\n"
        ". . wK\n"
        "Commands:\n"
        "click 50 50\n"
        "click 250 50\n"
        "click 250 250\n"
        "click 250 50\n"
        "wait 2000\n"
        "print board\n"
    )
    expected = ". . wR\n. . .\n. . wK\n"
    assert run_and_capture(input_text) == expected


# --- Iteration 8: game-over on king capture ---

def test_capturing_enemy_king_ends_the_game():
    input_text = (
        "Board:\n"
        "wR . bK\n"
        ". . .\n"
        "Commands:\n"
        "click 50 50\n"
        "click 250 50\n"
        "wait 2000\n"
        "print board\n"
    )
    expected = ". . wR\n. . .\n"
    assert run_and_capture(input_text) == expected


def test_move_commands_ignored_after_game_over():
    input_text = (
        "Board:\n"
        "wR . bK\n"
        ". wK .\n"
        "Commands:\n"
        "click 50 50\n"
        "click 250 50\n"
        "wait 2000\n"
        "click 150 150\n"
        "click 50 150\n"
        "wait 1000\n"
        "print board\n"
    )
    expected = ". . wR\n. wK .\n"
    assert run_and_capture(input_text) == expected


# --- Iteration 9: pawn promotion and two-square initial push ---
#
# Promotion is no longer automatic: reaching the far rank pauses the
# whole engine (click/jump/wait become no-ops) until a "promote" command
# supplies the piece to promote into.

def test_white_pawn_reaching_row_zero_awaits_user_choice_instead_of_auto_queening():
    input_text = (
        "Board:\n"
        "wK . . bK\n"
        ". wP . .\n"
        ". . . .\n"
        "Commands:\n"
        "click 150 150\n"
        "click 150 50\n"
        "wait 1000\n"
        "print board\n"
    )
    expected = "wK wP . bK\n. . . .\n. . . .\n"
    assert run_and_capture(input_text) == expected


def test_white_pawn_promotes_to_the_chosen_piece_once_selected():
    input_text = (
        "Board:\n"
        "wK . . bK\n"
        ". wP . .\n"
        ". . . .\n"
        "Commands:\n"
        "click 150 150\n"
        "click 150 50\n"
        "wait 1000\n"
        "promote 0 1 Q\n"
        "print board\n"
    )
    expected = "wK wQ . bK\n. . . .\n. . . .\n"
    assert run_and_capture(input_text) == expected


def test_engine_is_paused_while_a_promotion_choice_is_pending():
    input_text = (
        "Board:\n"
        "wK . . bK\n"
        ". wP . bR\n"
        ". . . .\n"
        "Commands:\n"
        "click 150 150\n"
        "click 150 50\n"
        "wait 1000\n"
        "click 350 150\n"
        "click 250 150\n"
        "wait 2000\n"
        "print board\n"
    )
    # The bR click/move attempt is a no-op: the engine paused for wP's
    # pending promotion before the bR move could ever be scheduled.
    expected = "wK wP . bK\n. . . bR\n. . . .\n"
    assert run_and_capture(input_text) == expected


def test_engine_resumes_after_promotion_choice_is_made():
    input_text = (
        "Board:\n"
        "wK . . bK\n"
        ". wP . bR\n"
        ". . . .\n"
        "Commands:\n"
        "click 150 150\n"
        "click 150 50\n"
        "wait 1000\n"
        "promote 0 1 N\n"
        "click 350 150\n"
        "click 250 150\n"
        "wait 2000\n"
        "print board\n"
    )
    expected = "wK wN . bK\n. . bR .\n. . . .\n"
    assert run_and_capture(input_text) == expected


def test_promote_with_invalid_choice_is_a_no_op_and_stays_paused():
    input_text = (
        "Board:\n"
        "wK . . bK\n"
        ". wP . .\n"
        ". . . .\n"
        "Commands:\n"
        "click 150 150\n"
        "click 150 50\n"
        "wait 1000\n"
        "promote 0 1 K\n"
        "print board\n"
        "print promotions\n"
    )
    expected = "wK wP . bK\n. . . .\n. . . .\n0 1 w QRBN\n"
    assert run_and_capture(input_text) == expected


def test_black_pawn_reaching_last_row_awaits_user_choice_instead_of_auto_queening():
    input_text = (
        "Board:\n"
        "wK . . bK\n"
        ". . . .\n"
        ". bP . .\n"
        ". . . .\n"
        "Commands:\n"
        "click 150 250\n"
        "click 150 350\n"
        "wait 1000\n"
        "print board\n"
    )
    expected = "wK . . bK\n. . . .\n. . . .\n. bP . .\n"
    assert run_and_capture(input_text) == expected


def test_black_pawn_promotes_to_the_chosen_piece_once_selected():
    input_text = (
        "Board:\n"
        "wK . . bK\n"
        ". . . .\n"
        ". bP . .\n"
        ". . . .\n"
        "Commands:\n"
        "click 150 250\n"
        "click 150 350\n"
        "wait 1000\n"
        "promote 3 1 R\n"
        "print board\n"
    )
    expected = "wK . . bK\n. . . .\n. . . .\n. bR . .\n"
    assert run_and_capture(input_text) == expected


def test_white_pawn_two_square_push_from_start_row():
    input_text = (
        "Board:\n"
        "wK . . bK\n"
        ". . . .\n"
        ". . . .\n"
        ". . . .\n"
        ". wP . .\n"
        "Commands:\n"
        "click 150 450\n"
        "click 150 250\n"
        "wait 2000\n"
        "print board\n"
    )
    expected = "wK . . bK\n. . . .\n. wP . .\n. . . .\n. . . .\n"
    assert run_and_capture(input_text) == expected


def test_white_pawn_two_square_push_blocked_by_piece_on_path():
    input_text = (
        "Board:\n"
        "wK . . bK\n"
        ". . . .\n"
        ". . . .\n"
        ". bN . .\n"
        ". wP . .\n"
        "Commands:\n"
        "click 150 450\n"
        "click 150 250\n"
        "wait 3000\n"
        "print board\n"
    )
    expected = "wK . . bK\n. . . .\n. . . .\n. bN . .\n. wP . .\n"
    assert run_and_capture(input_text) == expected


# --- Iteration 10: jumping ---

def test_jump_with_no_arriving_enemy_leaves_board_unchanged():
    input_text = (
        "Board:\n"
        ". . .\n"
        ". wK .\n"
        ". . .\n"
        "Commands:\n"
        "jump 150 150\n"
        "wait 1000\n"
        "print board\n"
    )
    expected = ". . .\n. wK .\n. . .\n"
    assert run_and_capture(input_text) == expected


def test_airborne_piece_captures_arriving_enemy():
    input_text = (
        "Board:\n"
        ". . .\n"
        ". wK bR\n"
        ". . .\n"
        "Commands:\n"
        "jump 150 150\n"
        "click 250 150\n"
        "click 150 150\n"
        "wait 1000\n"
        "print board\n"
    )
    expected = ". . .\n. wK .\n. . .\n"
    assert run_and_capture(input_text) == expected


def test_piece_is_normal_target_again_after_jump_window_ends():
    input_text = (
        "Board:\n"
        ". . .\n"
        ". wK bR\n"
        ". . .\n"
        "Commands:\n"
        "jump 150 150\n"
        "wait 1000\n"
        "click 250 150\n"
        "click 150 150\n"
        "wait 1000\n"
        "print board\n"
    )
    expected = ". . .\n. bR .\n. . .\n"
    assert run_and_capture(input_text) == expected


def test_moving_piece_cannot_jump():
    input_text = (
        "Board:\n"
        "wR . .\n"
        ". . .\n"
        "Commands:\n"
        "click 50 50\n"
        "click 250 50\n"
        "jump 50 50\n"
        "wait 2000\n"
        "print board\n"
    )
    expected = ". . wR\n. . .\n"
    assert run_and_capture(input_text) == expected