"""Orchestrates rule checking: shape-legality of a requested move (using
whichever patterns PieceRules has configured for the mover's piece type),
and settling a due move's rule consequences once the real-time arbiter
has classified it as clear or as an airborne capture - captures,
promotion-trigger registration, game-over detection - recording every
outcome into GameState as it happens.

RuleEngine doesn't know what a king or a rook *is* - it only knows how to
ask PieceRules whether a destination is among a piece's legal ones,
whether that destination's occupancy satisfies what the pattern requires,
and (via PieceRules.ends_game_on_capture) whether a given capture ends
the game outright. Teaching it about a new piece type, or which capture(s)
end the game, means editing rules/piece_rules.py, never this file.

Promotion never blocks play: reaching a configured rank instantly turns
the piece into that rule's configured default (see PromotionRule.default_choice
in rules/piece_rules.py) so the game keeps running. A pending choice is
registered on GameState alongside that auto-promotion, so a human can
still override the default later - apply_promotion_choice replaces
whatever piece is currently there with the chosen one.
"""

from kungfu_chess.model.piece import passes_as_empty


class RuleEngine:
    def __init__(self, piece_rules):
        self._piece_rules = piece_rules

    def is_legal_move(self, mover_piece, board, from_position, to_position):
        return self._matching_pattern(mover_piece, board, from_position, to_position) is not None

    def path_for_move(self, mover_piece, board, from_position, to_position):
        """The cell-by-cell path (one entry per leg, in order) a move
        from `from_position` to `to_position` follows, as decided by
        whichever movement pattern matched it - a single leg for a
        step-shaped pattern (no path to check, e.g. the knight,
        regardless of distance), or the full intermediate cell sequence
        for a sliding/multi-cell pattern (see StepPattern.path_to /
        SlidePattern.path_to / PawnDoubleStepPattern.path_to). Only
        the matched pattern decides this - never a piece-kind check here.
        Assumes the move has already been established legal (e.g. via
        is_legal_move); this doesn't re-validate.
        """
        pattern = self._matching_pattern(mover_piece, board, from_position, to_position)
        return pattern.path_to(from_position.row, from_position.col, to_position.row, to_position.col)

    def _matching_pattern(self, mover_piece, board, from_position, to_position):
        patterns = self._piece_rules.patterns_for(mover_piece.kind, mover_piece.color)

        for pattern, requirement in patterns:
            destinations = pattern.destinations(board, from_position.row, from_position.col, mover_piece.color)
            if (to_position.row, to_position.col) not in destinations:
                continue

            target_piece = board.get(to_position.row, to_position.col)
            if self._piece_rules.requirement_satisfied(requirement, target_piece, mover_piece.color):
                return pattern

        return None

    def settle_clear_move(self, board, game_state, mover_piece, from_position, to_position):
        """Apply a move the real-time arbiter has classified as clear to
        proceed (destination is empty or enemy-occupied, and not
        airborne). Returns True if this move ends the game (a king was
        captured).
        """
        captured_piece = board.get(to_position.row, to_position.col)
        if captured_piece is not None and passes_as_empty(captured_piece, mover_piece.color):
            # An enemy piece currently AIRBORNE isn't captured by simply
            # arriving on its cell - only at its own landing instant (see
            # GameEngine._land_due_jumps / RuleEngine.settle_airborne_capture).
            # The move below still overwrites its stale grid slot.
            captured_piece = None
        ends_game = captured_piece is not None and self._piece_rules.ends_game_on_capture(captured_piece)

        if captured_piece is not None:
            game_state.record_capture(mover_piece.color, self._piece_rules.value_of(captured_piece))

        board.apply_move(from_position.row, from_position.col, to_position.row, to_position.col)

        game_state.record_move(
            board,
            mover_piece,
            from_position,
            to_position,
            captured_piece=captured_piece,
            ends_game=ends_game,
        )

        # After the arrival move itself is on the record, an auto-promotion
        # (if any) is logged as its own follow-up entry - same ordering as
        # a later human override via apply_promotion_choice.
        self._maybe_schedule_promotion(board, game_state, mover_piece, to_position)

        if ends_game:
            game_state.set_game_over()

        return ends_game

    def settle_stopped_move(self, board, game_state, mover_piece, from_position, stopped_at_position):
        """Record a multi-cell move that stopped short of its originally
        requested destination, blocked by a friendly piece mid-path (see
        GameEngine's cell-by-cell advance) - `mover_piece` already
        physically sits at `stopped_at_position` from its last completed
        leg, so unlike settle_clear_move this never touches the board,
        never captures, and never ends the game; it only records the
        history entry and checks for a promotion trigger at the cell it
        actually stopped on.
        """
        game_state.record_move(board, mover_piece, from_position, stopped_at_position, captured_piece=None)
        self._maybe_schedule_promotion(board, game_state, mover_piece, stopped_at_position)

    def _maybe_schedule_promotion(self, board, game_state, mover_piece, to_position):
        rule = self._piece_rules.promotion_trigger_for(mover_piece, to_position.row, board)
        if rule is None:
            return

        game_state.schedule_promotion(to_position, mover_piece.color, rule.choices, mover_piece)
        self._auto_promote_to_default(board, game_state, rule, to_position)

    def _auto_promote_to_default(self, board, game_state, rule, position):
        """Instantly promote to the rule's configured default so play is
        never blocked on a human decision. The pending choice scheduled
        above is left in place, so apply_promotion_choice can still
        override this default with the player's actual pick later.
        """
        board.promote(position.row, position.col, rule.default_for())
        game_state.record_promotion(board, board.get(position.row, position.col), position)

    def settle_airborne_capture(
        self, board, game_state, attacker_piece, defender_piece, position, from_position
    ):
        """The defender at `position` is airborne and discovers
        `attacker_piece` occupying its home cell at the exact instant it
        lands (having settled there via an ordinary, non-capturing move
        sometime during the defender's flight - see
        GameEngine._land_due_jumps): the airborne piece reclaims its
        cell, capturing the attacker instead of being captured.
        `from_position` is cleared and then `defender_piece` is placed at
        `position`, so this works whether the attacker is already sitting
        at `position` itself (from_position == position) or, in principle,
        still at a separate square of its own.

        Ending the game on this capture is checked the same way as any
        other capture (e.g. a wandering enemy king caught here still ends
        the game) - RuleEngine never hardcodes which piece type that is,
        see PieceRules.ends_game_on_capture.
        """
        ends_game = self._piece_rules.ends_game_on_capture(attacker_piece)
        game_state.record_airborne_capture(board, attacker_piece, defender_piece, position)
        game_state.record_capture(defender_piece.color, self._piece_rules.value_of(attacker_piece))
        board.remove(from_position.row, from_position.col)
        board.place(position.row, position.col, defender_piece)
        if ends_game:
            game_state.set_game_over()
        return ends_game

    def apply_promotion_choice(self, board, game_state, position, piece_type):
        """Resolve the pending promotion at `position` by turning the
        piece there into `piece_type` (e.g. "Q"). No-op (returns False,
        pending list left untouched) if there's no pending promotion
        there, piece_type isn't one of its configured choices, or the
        piece currently occupying `position` is no longer the exact
        instance the promotion was scheduled for - e.g. it has since
        moved away (leaving the square empty or occupied by someone
        else), which would otherwise crash on an empty square or
        silently overwrite an unrelated piece's kind. `position` alone
        is not a reliable key once time has passed, so identity is
        reconfirmed here rather than trusted from the caller - this
        can't be left to caller discipline (e.g. a UI only invoking this
        for a still-open menu) since a future caller (e.g. a networked
        client) can't be trusted to always get that right.
        """
        pending = game_state.get_pending_promotion(position)
        if pending is None or piece_type not in pending.choices:
            return False
        if board.get(position.row, position.col) is not pending.piece:
            return False

        game_state.take_pending_promotion(position)
        board.promote(position.row, position.col, piece_type)
        game_state.record_promotion(board, board.get(position.row, position.col), position)
        return True
