"""Read-only, pull-based transform from a GameState snapshot into what a
score/move-list side panel needs to draw - the Observer of UI_PLAN.md
Sec 9/Sec 11.3. Never invoked from inside RuleEngine/GameEngine
settlement code (there is no push/notify mechanism anywhere in the
engine - see game_engine.py), only ever called once per render tick from
the view-composition layer, the same pull-per-frame treatment the UI
already gives PieceState for animation (Sec 5). This structurally keeps
it decoupled from the core move-resolution path: it cannot block or slow
down anything it is never called from.

Pure Python - no cv2, no model imports. Takes plain "w"/"b" strings
rather than importing model.piece's WHITE/BLACK constants, matching the
boundary discipline that only Controller may import model internals.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PanelData:
    color: str
    score: int
    moves: list  # list[str] - the FULL per-color move list, not pre-truncated
    rating: int = None  # Stage 3 - a player's persisted ELO rating, or None if unknown


def snapshot_for_color(game_state, color, rating=None):
    return PanelData(
        color=color,
        score=game_state.scores()[color],
        moves=game_state.moves_for_color(color),
        rating=rating,
    )


def clamp_scroll_offset(scroll_offset, total_moves, viewport_lines):
    """Bounds `scroll_offset` (lines hidden below the viewport, see
    visible_slice) to [0, max(0, total_moves - viewport_lines)]. Always
    recomputed against the *current* total_moves, so a previously-valid
    offset is re-clamped correctly as the move list grows during live
    play - never allowed to point past either end.
    """
    max_offset = max(0, total_moves - viewport_lines)
    return max(0, min(scroll_offset, max_offset))


def visible_slice(moves, scroll_offset, viewport_lines):
    """The window of `moves` a panel should draw. `scroll_offset` counts
    lines hidden below the viewport (bottom-anchored): offset 0 always
    shows the most recent moves, larger offsets reveal older ones -
    chat-scrollback semantics, not a hard truncation of the data.
    """
    offset = clamp_scroll_offset(scroll_offset, len(moves), viewport_lines)
    end = len(moves) - offset
    start = max(0, end - viewport_lines)
    return moves[start:end]