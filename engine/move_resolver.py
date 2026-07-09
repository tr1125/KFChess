"""Applies settlement rules to one due move: is the mover still there, is
the destination friendly/airborne/enemy, does this trigger a promotion
or end the game. MoveScheduler's job ends the moment it hands over a due
move; everything about what settling *means* lives here instead of
GameEngine, mirroring the Board/MovementRules/*Scheduler split. Every
settled move (or airborne capture) is also recorded to MoveHistory as it
happens - that's the one place resolution outcomes are known, so it's
also the one place that can describe them.

Promotion is never decided here: reaching a configured rank only
registers a pending choice on PromotionScheduler. The piece itself stays
on the board unchanged until GameEngine.choose_promotion applies the
user's pick - see engine/promotion_scheduler.py and
domain/promotion_rules.py for why that split exists.
"""

from domain.board import EMPTY_TOKEN
from domain.piece_token import color_of, type_of, KING_TYPE
from domain.promotion_rules import PromotionRules
from config.piece_definitions import PROMOTION_RULES
from engine.score_tracker import ScoreTracker
from engine.promotion_scheduler import PromotionScheduler


class MoveResolver:
    def __init__(self, board, jumps, history, score=None, promotions=None, promotion_rules=None):
        self._board = board
        self._jumps = jumps
        self._history = history
        self._score = score if score is not None else ScoreTracker()
        self._promotions = promotions if promotions is not None else PromotionScheduler()
        self._promotion_rules = (
            promotion_rules if promotion_rules is not None else PromotionRules(PROMOTION_RULES)
        )

    def resolve(self, move):
        """Apply the game rules for one due move. Returns True if this move
        ends the game (a king was captured), False otherwise.
        """
        current_token = self._board.get(move.from_row, move.from_col)
        if current_token != move.mover_token:
            return False  # the mover itself is gone - nothing to move

        target_token = self._board.get(move.to_row, move.to_col)

        if target_token != EMPTY_TOKEN and color_of(target_token) == color_of(move.mover_token):
            return False  # destination is friendly-occupied - cancel silently

        if target_token != EMPTY_TOKEN and self._jumps.is_airborne(move.to_row, move.to_col):
            # The defender is airborne and the arriver is an enemy (the
            # friendly case was already handled above): the airborne piece
            # captures the arriver instead of being captured.
            self._history.record_airborne_capture(
                self._board, move.mover_token, target_token, move.to_row, move.to_col
            )
            self._score.record_capture(color_of(target_token), move.mover_token)
            self._board.remove(move.from_row, move.from_col)
            return False

        captured_token = target_token if target_token != EMPTY_TOKEN else None
        ends_game = captured_token is not None and type_of(captured_token) == KING_TYPE

        if captured_token is not None:
            self._score.record_capture(color_of(move.mover_token), captured_token)

        self._board.apply_move(move.from_row, move.from_col, move.to_row, move.to_col)
        self._maybe_schedule_promotion(move.mover_token, move.to_row, move.to_col)

        self._history.record_move(
            self._board,
            move.mover_token,
            move.from_row,
            move.from_col,
            move.to_row,
            move.to_col,
            captured_token=captured_token,
            ends_game=ends_game,
        )

        return ends_game

    def _maybe_schedule_promotion(self, mover_token, to_row, to_col):
        """Register a pending promotion if this piece's arrival at
        (to_row, to_col) matches a configured PromotionRule. The piece
        itself is left as-is on the board - GameEngine.choose_promotion
        applies the user's eventual choice, not this method.
        """
        rule = self._promotion_rules.trigger_for(mover_token, to_row, self._board)
        if rule is not None:
            self._promotions.schedule(to_row, to_col, color_of(mover_token), rule.choices)
