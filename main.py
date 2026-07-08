
import sys
 
from serialization.board_serializer import parse_board, to_canonical, BoardFormatError
 
SECTION_BOARD = "Board:"
SECTION_COMMANDS = "Commands:"
COMMAND_PRINT_BOARD = "print board"
 
 
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
 
 
def run(text, out):
    board_lines, command_lines = split_sections(text)
 
    try:
        board = parse_board(board_lines)
    except BoardFormatError as error:
        out.write(f"ERROR {error.code}\n")
        return
 
    for command in command_lines:
        if command == COMMAND_PRINT_BOARD:
            out.write(to_canonical(board) + "\n")
 
 
def main():
    run(sys.stdin.read(), sys.stdout)
 
 
if __name__ == "__main__":
    main()