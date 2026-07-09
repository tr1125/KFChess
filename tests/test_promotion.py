"""Unit tests for the configurable, user-driven promotion pipeline:
PromotionRule/PromotionRules (the config lookup), PromotionScheduler
(pending-choice tracking), MoveResolver registering a pending choice
instead of auto-promoting, and GameEngine pausing/resuming around it.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from domain.board import Board
from domain.movement.movement_rules import MovementRules
from domain.promotion_rule import PromotionRule
from domain.promotion_rules import PromotionRules
from config.piece_definitions import PIECE_MOVEMENT_PATTERNS, PROMOTION_RULES
from engine.clock import ManualClock
from engine.game_engine import GameEngine
from engine.jump_scheduler import JumpScheduler
from engine.move_history import MoveHistory
from engine.move_resolver import MoveResolver
from engine.move_scheduler import PendingMove
from engine.promotion_scheduler import PromotionScheduler


def empty_board(size=8):
    return Board([["."] * size for _ in range(size)])


# --- PromotionRule / PromotionRules: configurable trigger lookup ---

def test_fixed_rank_rule_matches_only_its_own_row():
    rule = PromotionRule("P", "w", 0, ("Q",))
    rules = PromotionRules([rule])
    board = empty_board()
    assert rules.trigger_for("wP", 0, board) is rule
    assert rules.trigger_for("wP", 1, board) is None


def test_callable_rank_rule_resolves_relative_to_board_height():
    rule = PromotionRule("P", "b", lambda board: board.height - 1, ("Q",))
    rules = PromotionRules([rule])
    board = empty_board(size=5)
    assert rules.trigger_for("bP", 4, board) is rule
    assert rules.trigger_for("bP", 3, board) is None


def test_rule_is_specific_to_piece_type_and_color():
    rule = PromotionRule("P", "w", 0, ("Q",))
    rules = PromotionRules([rule])
    board = empty_board()
    assert rules.trigger_for("bP", 0, board) is None  # wrong color
    assert rules.trigger_for("wN", 0, board) is None  # wrong piece type


def test_rules_are_a_flat_config_list_not_hardcoded_to_pawns():
    """The user's stated requirement: retargeting promotion to a
    different piece/rank is a config change, not a code change - e.g. a
    knight promoting on the 4th rank of an 8-row board (row index 4).
    """
    knight_rule = PromotionRule("N", "w", 4, ("Q",))
    rules = PromotionRules([knight_rule])
    board = empty_board(size=8)
    assert rules.trigger_for("wN", 4, board) is knight_rule
    assert rules.trigger_for("wP", 0, board) is None  # pawn is no longer configured at all


def test_default_promotion_rules_cover_both_pawn_colors():
    rules = PromotionRules(PROMOTION_RULES)
    board = empty_board(size=8)
    assert rules.trigger_for("wP", 0, board) is not None
    assert rules.trigger_for("bP", 7, board) is not None
    assert rules.trigger_for("wP", 7, board) is None
    assert rules.trigger_for("bP", 0, board) is None


# --- PromotionScheduler: pending-choice tracking ---

def test_scheduled_promotion_is_pending_at_its_square():
    scheduler = PromotionScheduler()
    scheduler.schedule(0, 1, "w", ("Q", "R", "B", "N"))
    assert scheduler.get(0, 1) is not None
    assert scheduler.get(1, 1) is None


def test_has_any_reflects_whether_anything_is_pending():
    scheduler = PromotionScheduler()
    assert not scheduler.has_any()
    scheduler.schedule(0, 1, "w", ("Q",))
    assert scheduler.has_any()


def test_take_removes_the_pending_entry():
    scheduler = PromotionScheduler()
    scheduler.schedule(0, 1, "w", ("Q",))
    taken = scheduler.take(0, 1)
    assert taken.color == "w"
    assert not scheduler.has_any()
    assert scheduler.take(0, 1) is None


def test_clear_removes_every_pending_promotion():
    scheduler = PromotionScheduler()
    scheduler.schedule(0, 1, "w", ("Q",))
    scheduler.schedule(3, 1, "b", ("Q",))
    scheduler.clear()
    assert not scheduler.has_any()


# --- MoveResolver: registers a pending choice, never auto-promotes ---

def make_resolver(rows, promotion_rules=None):
    board = Board(rows)
    jumps = JumpScheduler()
    history = MoveHistory()
    promotions = PromotionScheduler()
    resolver = MoveResolver(board, jumps, history, promotions=promotions, promotion_rules=promotion_rules)
    return resolver, board, promotions, history


def test_resolver_registers_a_pending_promotion_instead_of_auto_promoting():
    rows = [
        ["wK", ".", ".", "bK"],
        [".", "wP", ".", "."],
        [".", ".", ".", "."],
    ]
    resolver, board, promotions, history = make_resolver(rows)
    move = PendingMove(1, 1, 0, 1, complete_at_ms=0, mover_token="wP")
    resolver.resolve(move)

    assert board.get(0, 1) == "wP"  # not auto-promoted to wQ
    pending = promotions.get(0, 1)
    assert pending.color == "w"
    assert pending.choices == ("Q", "R", "B", "N")
    assert history.entries() == ["b3"]  # settled move recorded without "=Q"


def test_resolver_does_not_schedule_a_promotion_for_a_non_triggering_move():
    rows = [["wR", "."]]
    resolver, board, promotions, history = make_resolver(rows)
    move = PendingMove(0, 0, 0, 1, complete_at_ms=0, mover_token="wR")
    resolver.resolve(move)
    assert not promotions.has_any()


def test_resolver_honors_injected_custom_promotion_rules():
    """A custom PromotionRules (e.g. knight-on-4th-rank) changes what
    triggers a promotion without any change to MoveResolver itself.
    """
    rows = [
        ["wK", ".", "bK"],
        [".", ".", "."],
        [".", "wN", "."],
        [".", ".", "."],
    ]
    custom_rules = PromotionRules([PromotionRule("N", "w", 0, ("Q", "R"))])
    resolver, board, promotions, history = make_resolver(rows, promotion_rules=custom_rules)
    move = PendingMove(2, 1, 0, 1, complete_at_ms=0, mover_token="wN")
    resolver.resolve(move)
    pending = promotions.get(0, 1)
    assert pending is not None
    assert pending.choices == ("Q", "R")


# --- MoveHistory: recording a resolved promotion choice ---

def test_record_promotion_logs_square_and_new_type():
    history = MoveHistory()
    history.record_promotion(empty_board(), "wQ", 0, 1)
    assert history.entries() == ["b8=Q"]


# --- GameEngine: pause on pending promotion, resume on valid choice ---

def click_cell(engine, row, col):
    engine.click(col * 100 + 50, row * 100 + 50)


def make_engine(rows):
    board = Board(rows)
    clock = ManualClock()
    movement_rules = MovementRules(PIECE_MOVEMENT_PATTERNS)
    return GameEngine(board, clock, movement_rules), board, clock


def test_engine_reports_pending_promotion_after_pawn_reaches_far_rank():
    rows = [
        ["wK", ".", "bK"],
        [".", "wP", "."],
        [".", ".", "."],
    ]
    engine, board, clock = make_engine(rows)
    click_cell(engine, 1, 1)
    click_cell(engine, 0, 1)
    engine.wait(1000)

    pending = engine.pending_promotions()
    assert len(pending) == 1
    assert pending[0] == {"row": 0, "col": 1, "color": "w", "choices": ("Q", "R", "B", "N")}
    assert board.get(0, 1) == "wP"


def test_engine_ignores_clicks_and_wait_while_promotion_pending():
    rows = [
        ["wK", ".", "bK"],
        [".", "wP", "bR"],
        [".", ".", "."],
    ]
    engine, board, clock = make_engine(rows)
    click_cell(engine, 1, 1)
    click_cell(engine, 0, 1)
    engine.wait(1000)  # wP settles into a pending promotion; engine now paused

    click_cell(engine, 1, 2)  # attempt to select bR - ignored while paused
    click_cell(engine, 1, 1)
    engine.wait(5000)  # clock advance is also a no-op while paused

    assert board.get(1, 2) == "bR"  # never moved
    assert engine.pending_promotions()  # still pending


def test_engine_applies_choice_and_resumes_normal_play():
    rows = [
        ["wK", ".", "bK"],
        [".", "wP", "bR"],
        [".", ".", "."],
    ]
    engine, board, clock = make_engine(rows)
    click_cell(engine, 1, 1)
    click_cell(engine, 0, 1)
    engine.wait(1000)

    engine.choose_promotion(0, 1, "N")
    assert board.get(0, 1) == "wN"
    assert not engine.pending_promotions()
    assert engine.move_history()[-1] == "b3=N"

    # Play resumes: a move that was blocked by the pause now goes through.
    click_cell(engine, 1, 2)
    click_cell(engine, 1, 1)
    engine.wait(1000)
    assert board.get(1, 1) == "bR"


def test_engine_ignores_an_invalid_promotion_choice_and_stays_paused():
    rows = [
        ["wK", ".", "bK"],
        [".", "wP", "."],
        [".", ".", "."],
    ]
    engine, board, clock = make_engine(rows)
    click_cell(engine, 1, 1)
    click_cell(engine, 0, 1)
    engine.wait(1000)

    engine.choose_promotion(0, 1, "K")  # King is not among the configured choices
    assert board.get(0, 1) == "wP"
    assert engine.pending_promotions()