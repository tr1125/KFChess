"""Unit tests for ScoreTracker's standard chess piece values, direct tests
of MoveResolver crediting captures to the right color (including the
mid-air capture case, where the airborne defender - not the mover - is
the one who scores), and end-to-end checks through GameEngine and the
text protocol.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from domain.board import Board
from domain.movement.movement_rules import MovementRules
from config.piece_definitions import PIECE_MOVEMENT_PATTERNS
from engine.clock import ManualClock
from engine.game_engine import GameEngine
from engine.score_tracker import ScoreTracker
from engine.move_history import MoveHistory
from engine.move_scheduler import MoveScheduler, PendingMove
from engine.jump_scheduler import JumpScheduler
from engine.move_resolver import MoveResolver
from main import run


def empty_board(size=8):
    return Board([["."] * size for _ in range(size)])


# --- ScoreTracker: standard values, credited to the capturing color ---

def test_new_tracker_starts_at_zero_for_both_colors():
    score = ScoreTracker()
    assert score.scores() == {"w": 0, "b": 0}


def test_record_capture_credits_the_capturing_color_with_piece_value():
    score = ScoreTracker()
    score.record_capture("w", "bN")  # knight is worth 3
    assert score.scores() == {"w": 3, "b": 0}


def test_record_capture_accumulates_across_multiple_captures():
    score = ScoreTracker()
    score.record_capture("w", "bP")  # 1
    score.record_capture("w", "bQ")  # 9
    score.record_capture("b", "wR")  # 5
    assert score.scores() == {"w": 10, "b": 5}


def test_king_capture_is_worth_zero_points():
    score = ScoreTracker()
    score.record_capture("w", "bK")
    assert score.scores() == {"w": 0, "b": 0}


# --- MoveResolver: captures are credited as they're recorded ---

def make_resolver(rows):
    board = Board(rows)
    jumps = JumpScheduler()
    history = MoveHistory()
    score = ScoreTracker()
    return MoveResolver(board, jumps, history, score), board, jumps, history, score


def test_resolver_credits_mover_color_on_normal_capture():
    rows = [["wQ", "bR"]]
    resolver, board, jumps, history, score = make_resolver(rows)
    move = PendingMove(0, 0, 0, 1, complete_at_ms=0, mover_token="wQ")
    resolver.resolve(move)
    assert score.scores() == {"w": 5, "b": 0}  # rook is worth 5


def test_resolver_does_not_credit_anyone_on_non_capturing_move():
    rows = [["wR", "."]]
    resolver, board, jumps, history, score = make_resolver(rows)
    move = PendingMove(0, 0, 0, 1, complete_at_ms=0, mover_token="wR")
    resolver.resolve(move)
    assert score.scores() == {"w": 0, "b": 0}


def test_resolver_does_not_credit_a_friendly_cancel():
    rows = [["wR", "wN"]]
    resolver, board, jumps, history, score = make_resolver(rows)
    move = PendingMove(0, 0, 0, 1, complete_at_ms=0, mover_token="wR")
    resolver.resolve(move)
    assert score.scores() == {"w": 0, "b": 0}


def test_resolver_credits_airborne_defender_not_the_arriving_mover():
    rows = [["wR", "bN"]]  # bN at (0,1) is airborne; wR arrives there
    resolver, board, jumps, history, score = make_resolver(rows)
    jumps.schedule(0, 1, token="bN", land_at_ms=100)
    move = PendingMove(0, 0, 0, 1, complete_at_ms=0, mover_token="wR")
    resolver.resolve(move)
    assert score.scores() == {"w": 0, "b": 5}  # bN captures wR (worth 5) mid-air


# --- End-to-end: GameEngine and the text protocol ---

def click_cell(engine, row, col):
    engine.click(col * 100 + 50, row * 100 + 50)


def test_engine_scores_start_at_zero():
    rows = [
        ["bK", ".", "."],
        [".", ".", "."],
        [".", ".", "wR"],
    ]
    engine = GameEngine(Board(rows), ManualClock(), MovementRules(PIECE_MOVEMENT_PATTERNS))
    assert engine.scores() == {"w": 0, "b": 0}


def test_engine_credits_capture_via_score_tracker():
    rows = [
        ["bR", ".", "."],
        [".", ".", "."],
        [".", ".", "wR"],
    ]
    engine = GameEngine(Board(rows), ManualClock(), MovementRules(PIECE_MOVEMENT_PATTERNS))
    click_cell(engine, 2, 2)  # select wR
    click_cell(engine, 0, 2)  # move up column 2, not yet capturing
    engine.wait(2000)
    click_cell(engine, 0, 2)  # select wR again
    click_cell(engine, 0, 0)  # capture bR
    engine.wait(2000)
    assert engine.scores() == {"w": 5, "b": 0}


def test_print_score_reports_zero_before_any_capture():
    input_text = (
        "Board:\n"
        "wK . bK\n"
        "Commands:\n"
        "print score\n"
    )
    out = _run(input_text)
    assert out == "w 0 b 0\n"


def test_print_score_after_a_capture():
    input_text = (
        "Board:\n"
        "wR . bN\n"
        "Commands:\n"
        "click 50 50\n"
        "click 250 50\n"
        "wait 2000\n"
        "print score\n"
    )
    out = _run(input_text)
    assert out == "w 3 b 0\n"  # knight captured, worth 3


def _run(input_text):
    import io

    out = io.StringIO()
    run(input_text, out)
    return out.getvalue()