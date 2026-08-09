"""GameState <-> wire-payload conversion: the Adapter boundary for the
networked `state` message (see KFChess_Server_Plan.md's wire protocol
reference and its Sec 6.1 extensibility note), the same role
board_parser.py/board_printer.py play for the `.kfc` text format. Nothing
outside model/, rules/, and io/ may read Board/Piece internals directly -
this is the one place that builds/reads the `state` message's board
representation, so a future binary board representation only touches this
file (plus board_parser.py/board_printer.py), not server or client code.

Piece animation timing (state_entered_at) is deliberately NOT round-tripped
here - the receiving side's own clock has no fixed relationship to the
server's, so a piece's rest-animation frame may be a beat off after a
`state` message lands. In-flight glide timing is unaffected by this: that's
carried by the separate `move_started` message and the receiving side's own
local timer (see net/remote_engine.py), not by this snapshot.
"""

from kungfu_chess.model.board import Board
from kungfu_chess.model.game_state import GameState
from kungfu_chess.model.piece import Piece, PieceState
from kungfu_chess.model.position import Position


def to_wire_state(game_state):
    """GameState snapshot -> a JSON-safe dict for the `state` message."""
    return {
        "board": [[_piece_to_wire(piece) for piece in row] for row in game_state.board_rows()],
        "scores": game_state.scores(),
        "move_history": [
            {"color": color, "notation": notation} for color, notation in game_state.history_entries()
        ],
        "pending_promotions": [
            {
                "row": pending.position.row,
                "col": pending.position.col,
                "color": pending.color,
                "choices": list(pending.choices),
            }
            for pending in game_state.pending_promotions()
        ],
    }


def _piece_to_wire(piece):
    if piece is None:
        return None
    return {"color": piece.color, "kind": piece.kind, "state": piece.state.name}


def from_wire_state(payload):
    """The `state` message's payload -> a fresh, fully-populated GameState
    with a Board attached, for the client to render exactly like a locally-
    computed one.
    """
    rows = [
        [_wire_to_piece(cell, row_index, col_index) for col_index, cell in enumerate(row)]
        for row_index, row in enumerate(payload["board"])
    ]
    board = Board(rows)

    game_state = GameState()
    game_state.attach_board(board)

    for color, value in payload["scores"].items():
        if value:
            game_state.record_capture(color, value)

    game_state.restore_history(
        [(entry["color"], entry["notation"]) for entry in payload["move_history"]]
    )

    for entry in payload["pending_promotions"]:
        position = Position(entry["row"], entry["col"])
        game_state.schedule_promotion(
            position, entry["color"], tuple(entry["choices"]), board.get(position.row, position.col)
        )

    return game_state


def _wire_to_piece(cell, row, col):
    if cell is None:
        return None
    return Piece(
        color=cell["color"], kind=cell["kind"], cell=Position(row, col), state=PieceState[cell["state"]]
    )