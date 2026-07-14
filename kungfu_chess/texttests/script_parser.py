"""Parses raw .kfc script text into board lines and structured Command
objects. No execution, no I/O beyond the string it's given - running a
parsed script against a wired-up engine is script_runner's job.
"""

from dataclasses import dataclass

SECTION_BOARD = "Board:"
SECTION_COMMANDS = "Commands:"

CMD_CLICK = "click"
CMD_JUMP = "jump"
CMD_WAIT = "wait"
CMD_PROMOTE = "promote"
CMD_PRINT_BOARD = "print board"
CMD_PRINT_SCORE = "print score"
CMD_PRINT_PROMOTIONS = "print promotions"

_PRINT_COMMANDS = (CMD_PRINT_BOARD, CMD_PRINT_SCORE, CMD_PRINT_PROMOTIONS)


@dataclass(frozen=True)
class Command:
    name: str
    args: tuple


def split_sections(text):
    """Split raw script text into (board_lines, command_lines)."""
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


def parse_command(command_line):
    """Parse one command line into a Command. Multi-word print commands
    (e.g. "print board") are recognized as a single command name; every
    other command's first word is its name and the rest are its args.
    """
    for print_command in _PRINT_COMMANDS:
        if command_line == print_command:
            return Command(print_command, ())

    parts = command_line.split()
    return Command(parts[0], tuple(parts[1:]))


def parse_script(text):
    """Parse raw .kfc script text into (board_lines, list[Command])."""
    board_lines, command_lines = split_sections(text)
    commands = [parse_command(line) for line in command_lines]
    return board_lines, commands