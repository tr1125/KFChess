import sys

from serialization.board_serializer import parse_board, to_canonical, BoardFormatError
from engine.clock import ManualClock
from engine.game_engine import GameEngine
from domain.movement.movement_rules import MovementRules
from config.piece_definitions import PIECE_MOVEMENT_PATTERNS

SECTION_BOARD = "Board:"
SECTION_COMMANDS = "Commands:"

CMD_CLICK = "click"
CMD_WAIT = "wait"
CMD_PRINT_BOARD = "print board"


def split_sections(text):
    """Split raw input text into (board_lines, command_lines)."""
    board_lines = []
    command_lines = []
    section = None

    for line in text.splitlines():
        stripped = line.strip()
        if stripped == SECTION_BOARD:
            section = "board"
            continue
        if stripped == SECTION_COMMANDS:
            section = "commands"
            continue
        if stripped == "":
            continue
        if section == "board":
            board_lines.append(line)
        elif section == "commands":
            command_lines.append(stripped)

    return board_lines, command_lines


def _dispatch(command_line, engine, out):
    parts = command_line.split()
    command = parts[0]

    if command == CMD_CLICK and len(parts) == 3:
        engine.click(int(parts[1]), int(parts[2]))
    elif command == CMD_WAIT and len(parts) == 2:
        engine.wait(int(parts[1]))
    elif command_line == CMD_PRINT_BOARD:
        out.write(to_canonical(engine.board()) + "\n")


def run(text, out):
    board_lines, command_lines = split_sections(text)

    try:
        board = parse_board(board_lines)
    except BoardFormatError as error:
        out.write(f"ERROR {error.code}\n")
        return

    movement_rules = MovementRules(PIECE_MOVEMENT_PATTERNS)
    engine = GameEngine(board, ManualClock(), movement_rules)

    for command_line in command_lines:
        _dispatch(command_line, engine, out)


def main():
    run(sys.stdin.read(), sys.stdout)


if __name__ == "__main__":
    main()