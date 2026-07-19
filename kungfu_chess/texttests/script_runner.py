"""Composition root for the text-command protocol: wires model/rules/
realtime/engine/input/io together and executes a parsed script against
them, writing command output. This is where the timing/pixel constants
that used to live in an orphaned config/settings.py are actually
consumed, since this is the one place that constructs the engine and the
board mapper.
"""

from kungfu_chess.io.board_parser import parse_board, BoardFormatError
from kungfu_chess.io.board_printer import to_canonical
from kungfu_chess.rules.piece_rules import default_piece_rules
from kungfu_chess.rules.rule_engine import RuleEngine
from kungfu_chess.engine.game_engine import GameEngine
from kungfu_chess.input.board_mapper import BoardMapper
from kungfu_chess.input.controller import Controller
from kungfu_chess.texttests.script_parser import (
    parse_script,
    CMD_CLICK,
    CMD_JUMP,
    CMD_WAIT,
    CMD_PROMOTE,
    CMD_PRINT_BOARD,
    CMD_PRINT_SCORE,
    CMD_PRINT_PROMOTIONS,
)

CELL_SIZE_PX = 100

# Duration is per cell of Chebyshev distance traveled - a 2-cell rook
# move takes exactly 2000ms to settle, not 1000ms.
MOVE_DURATION_PER_CELL_MS = 1000

# A jump keeps the piece on its own cell but makes it "airborne" for this
# long. If an enemy's move lands on that cell during the window, the
# airborne piece captures the arriving enemy instead of being captured.
JUMP_DURATION_MS = 1000

# After a move settles or a jump lands, the piece rests and cannot be
# selected again until the rest elapses - long after a move, short after
# a jump.
LONG_REST_DURATION_MS = 1000
SHORT_REST_DURATION_MS = 500


def _dispatch(command, controller, engine, out):
    if command.name == CMD_CLICK:
        x_px, y_px = (int(arg) for arg in command.args)
        controller.click(x_px, y_px)
    elif command.name == CMD_JUMP:
        x_px, y_px = (int(arg) for arg in command.args)
        controller.jump(x_px, y_px)
    elif command.name == CMD_WAIT:
        (ms,) = command.args
        controller.wait(int(ms))
    elif command.name == CMD_PROMOTE:
        row, col, piece_type = command.args
        controller.choose_promotion(int(row), int(col), piece_type)
    elif command.name == CMD_PRINT_BOARD:
        out.write(to_canonical(engine.board()) + "\n")
    elif command.name == CMD_PRINT_SCORE:
        scores = engine.scores()
        out.write(f"w {scores['w']} b {scores['b']}\n")
    elif command.name == CMD_PRINT_PROMOTIONS:
        for pending in engine.pending_promotions():
            choices = "".join(pending["choices"])
            out.write(f"{pending['row']} {pending['col']} {pending['color']} {choices}\n")


def build_engine(board):
    """Wire a GameEngine from a parsed Board using the standard timing
    config. Exposed separately from run_script so other callers (e.g. a
    future live app.py view loop) can reuse the same wiring.
    """
    rule_engine = RuleEngine(default_piece_rules())
    return GameEngine(
        board,
        rule_engine,
        move_duration_per_cell_ms=MOVE_DURATION_PER_CELL_MS,
        jump_duration_ms=JUMP_DURATION_MS,
        long_rest_duration_ms=LONG_REST_DURATION_MS,
        short_rest_duration_ms=SHORT_REST_DURATION_MS,
    )


def run_script(text, out):
    """Parse and execute a .kfc script's text against a freshly wired
    engine, writing every command's output to `out`.
    """
    board_lines, commands = parse_script(text)

    try:
        board = parse_board(board_lines)
    except BoardFormatError as error:
        out.write(f"ERROR {error.code}\n")
        return

    engine = build_engine(board)
    controller = Controller(engine, BoardMapper(CELL_SIZE_PX))

    for command in commands:
        _dispatch(command, controller, engine, out)