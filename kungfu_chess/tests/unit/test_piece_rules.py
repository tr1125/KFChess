"""Unit tests for the pure config-driven layer: pattern primitives in
isolation, the PromotionRule trigger lookup, and the PieceRules facade.
Whether a *whole* move is legal (color/occupancy orchestration) is
RuleEngine's job and is tested in test_rule_engine.py instead.
"""

from kungfu_chess.model.board import Board
from kungfu_chess.model.piece import Piece
from kungfu_chess.rules.piece_rules import (
    StepPattern,
    SlidePattern,
    PawnDoubleStepPattern,
    PromotionRule,
    PieceRules,
    ANY,
    MOVE_ONLY,
    CAPTURE_ONLY,
    PIECE_MOVEMENT_PATTERNS,
    PROMOTION_RULES,
    PIECE_VALUES,
    default_piece_rules,
)


def empty_board(size=5):
    return Board([[None] * size for _ in range(size)])


def piece(color, kind):
    return Piece(color=color, kind=kind)


# --- StepPattern ---

def test_step_pattern_returns_in_bounds_offsets_only():
    board = empty_board()
    pattern = StepPattern([(-1, 0), (1, 0), (0, -10)])
    assert pattern.destinations(board, 2, 2) == [(1, 2), (3, 2)]


def test_step_pattern_ignores_occupancy():
    rows = [
        [piece("w", "N"), piece("w", "N"), piece("w", "N")],
        [piece("w", "N"), piece("w", "K"), piece("w", "N")],
        [piece("w", "N"), piece("w", "N"), piece("w", "N")],
    ]
    board = Board(rows)
    pattern = StepPattern([(-1, 0)])
    assert pattern.destinations(board, 1, 1) == [(0, 1)]


# --- SlidePattern ---

def test_slide_pattern_covers_full_direction_when_unblocked():
    board = empty_board()
    pattern = SlidePattern([(0, 1)])
    assert pattern.destinations(board, 0, 0) == [(0, 1), (0, 2), (0, 3), (0, 4)]


def test_slide_pattern_stops_at_and_includes_first_blocker():
    rows = [[piece("w", "R"), None, piece("b", "N"), None, None]]
    board = Board(rows)
    pattern = SlidePattern([(0, 1)])
    assert pattern.destinations(board, 0, 0) == [(0, 1), (0, 2)]


def test_slide_pattern_handles_multiple_directions_independently():
    board = empty_board()
    pattern = SlidePattern([(0, 1), (0, -1)])
    assert pattern.destinations(board, 0, 2) == [(0, 3), (0, 4), (0, 1), (0, 0)]


# --- PawnDoubleStepPattern ---

def test_pawn_double_step_legal_from_start_row_when_clear():
    board = empty_board(size=4)
    pattern = PawnDoubleStepPattern((-1, 0), start_row_fn=lambda b: b.height - 1)
    assert pattern.destinations(board, 3, 1) == [(1, 1)]


def test_pawn_double_step_illegal_off_start_row():
    board = empty_board(size=4)
    pattern = PawnDoubleStepPattern((-1, 0), start_row_fn=lambda b: b.height - 1)
    assert pattern.destinations(board, 2, 1) == []


def test_pawn_double_step_blocked_by_piece_on_intermediate_cell():
    rows = [[None, None], [piece("b", "R"), None], [piece("w", "P"), None]]
    board = Board(rows)
    pattern = PawnDoubleStepPattern((-1, 0), start_row_fn=lambda b: b.height - 1)
    assert pattern.destinations(board, 2, 0) == []


def test_pawn_double_step_destination_off_board_is_excluded():
    board = empty_board(size=1)
    pattern = PawnDoubleStepPattern((-1, 0), start_row_fn=lambda b: 0)
    assert pattern.destinations(board, 0, 0) == []


def test_pawn_double_step_destination_off_board_when_intermediate_cell_is_in_bounds():
    """The intermediate cell can be in bounds while the final destination
    still falls off the board - a distinct off-board case from the
    intermediate-cell check above.
    """
    board = empty_board(size=2)
    pattern = PawnDoubleStepPattern((-1, 0), start_row_fn=lambda b: 1)
    assert pattern.destinations(board, 1, 0) == []


# --- PromotionRule ---

def test_promotion_rule_fixed_rank():
    rule = PromotionRule("P", "w", 0, ("Q",))
    assert rule.rank_for(empty_board()) == 0


def test_promotion_rule_callable_rank_resolves_against_board():
    rule = PromotionRule("P", "b", lambda board: board.height - 1, ("Q",))
    assert rule.rank_for(empty_board(size=5)) == 4


def test_promotion_rule_default_choice_falls_back_to_first_choice_when_unset():
    rule = PromotionRule("P", "w", 0, ("Q", "R", "B", "N"))
    assert rule.default_for() == "Q"


def test_promotion_rule_default_choice_is_configurable():
    rule = PromotionRule("P", "w", 0, ("Q", "R", "B", "N"), default_choice="R")
    assert rule.default_for() == "R"


# --- PieceRules.patterns_for ---

def test_patterns_for_flat_list_entry():
    rules = PieceRules({"R": [("pattern", ANY)]}, [], {})
    assert rules.patterns_for("R", "w") == [("pattern", ANY)]


def test_patterns_for_color_dependent_entry():
    rules = PieceRules({"P": {"w": ["white-pattern"], "b": ["black-pattern"]}}, [], {})
    assert rules.patterns_for("P", "w") == ["white-pattern"]
    assert rules.patterns_for("P", "b") == ["black-pattern"]


def test_patterns_for_unknown_piece_type_is_empty():
    rules = PieceRules({}, [], {})
    assert rules.patterns_for("Z", "w") == []


# --- PieceRules.promotion_trigger_for ---

def test_promotion_trigger_for_matches_piece_color_and_rank():
    rule = PromotionRule("P", "w", 0, ("Q",))
    rules = PieceRules({}, [rule], {})
    assert rules.promotion_trigger_for(piece("w", "P"), 0, empty_board()) is rule
    assert rules.promotion_trigger_for(piece("w", "P"), 1, empty_board()) is None


def test_promotion_trigger_for_is_specific_to_piece_type_and_color():
    rule = PromotionRule("P", "w", 0, ("Q",))
    rules = PieceRules({}, [rule], {})
    assert rules.promotion_trigger_for(piece("b", "P"), 0, empty_board()) is None  # wrong color
    assert rules.promotion_trigger_for(piece("w", "N"), 0, empty_board()) is None  # wrong piece type


def test_promotion_trigger_for_arbitrary_piece_and_rank_is_config_only():
    """Retargeting promotion to a different piece/rank is a config
    change, not a code change - e.g. a knight promoting on the 4th rank
    of an 8-row board (row index 4).
    """
    knight_rule = PromotionRule("N", "w", 4, ("Q",))
    rules = PieceRules({}, [knight_rule], {})
    board = empty_board(size=8)
    assert rules.promotion_trigger_for(piece("w", "N"), 4, board) is knight_rule
    assert rules.promotion_trigger_for(piece("w", "P"), 0, board) is None  # pawn not configured at all


# --- PieceRules.value_of ---

def test_value_of_looks_up_piece_type_value():
    rules = PieceRules({}, [], {"Q": 9, "P": 1})
    assert rules.value_of(piece("w", "Q")) == 9
    assert rules.value_of(piece("b", "P")) == 1


# --- PieceRules.ends_game_on_capture ---

def test_ends_game_on_capture_is_true_only_for_configured_types():
    rules = PieceRules({}, [], {}, game_ending_capture_types={"K"})
    assert rules.ends_game_on_capture(piece("w", "K")) is True
    assert rules.ends_game_on_capture(piece("b", "Q")) is False


def test_ends_game_on_capture_defaults_to_no_game_ending_captures():
    rules = PieceRules({}, [], {})
    assert rules.ends_game_on_capture(piece("w", "K")) is False


# --- default config sanity checks ---

def test_default_piece_values_are_standard_chess_values():
    assert PIECE_VALUES == {"K": 0, "Q": 9, "R": 5, "B": 3, "N": 3, "P": 1}


def test_default_win_condition_is_capturing_the_king():
    rules = default_piece_rules()
    assert rules.ends_game_on_capture(piece("w", "K")) is True
    assert rules.ends_game_on_capture(piece("b", "Q")) is False


def test_default_promotion_rules_cover_both_pawn_colors():
    rules = default_piece_rules()
    board = empty_board(size=8)
    assert rules.promotion_trigger_for(piece("w", "P"), 0, board) is not None
    assert rules.promotion_trigger_for(piece("b", "P"), 7, board) is not None
    assert rules.promotion_trigger_for(piece("w", "P"), 7, board) is None
    assert rules.promotion_trigger_for(piece("b", "P"), 0, board) is None


def test_default_promotion_rules_default_to_queen():
    rules = default_piece_rules()
    board = empty_board(size=8)
    assert rules.promotion_trigger_for(piece("w", "P"), 0, board).default_for() == "Q"
    assert rules.promotion_trigger_for(piece("b", "P"), 7, board).default_for() == "Q"


def test_default_movement_patterns_cover_every_standard_piece():
    assert set(PIECE_MOVEMENT_PATTERNS.keys()) == {"K", "Q", "R", "B", "N", "P"}


def test_default_pawn_patterns_are_color_dependent():
    assert set(PIECE_MOVEMENT_PATTERNS["P"].keys()) == {"w", "b"}


def test_default_piece_rules_returns_a_usable_facade():
    rules = default_piece_rules()
    assert rules.patterns_for("K", "w") != []
    assert rules.value_of(piece("w", "R")) == 5
