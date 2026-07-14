from kungfu_chess.texttests.script_parser import (
    Command,
    split_sections,
    parse_command,
    parse_script,
    CMD_CLICK,
    CMD_WAIT,
    CMD_PROMOTE,
    CMD_PRINT_BOARD,
    CMD_PRINT_SCORE,
    CMD_PRINT_PROMOTIONS,
)


# --- split_sections ---

def test_split_sections_separates_board_and_command_lines():
    text = "Board:\nwK . .\n. . .\nCommands:\nclick 50 50\nwait 1000\n"
    board_lines, command_lines = split_sections(text)
    assert board_lines == ["wK . .", ". . ."]
    assert command_lines == ["click 50 50", "wait 1000"]


def test_split_sections_skips_blank_lines():
    text = "Board:\nwK . .\n\nCommands:\n\nclick 50 50\n"
    board_lines, command_lines = split_sections(text)
    assert board_lines == ["wK . ."]
    assert command_lines == ["click 50 50"]


def test_split_sections_strips_command_line_whitespace():
    text = "Board:\nwK\nCommands:\n  wait 1000  \n"
    _, command_lines = split_sections(text)
    assert command_lines == ["wait 1000"]


def test_split_sections_with_no_commands_section():
    text = "Board:\nwK .\n"
    board_lines, command_lines = split_sections(text)
    assert board_lines == ["wK ."]
    assert command_lines == []


def test_split_sections_ignores_lines_before_any_section_marker():
    text = "stray preamble line\nBoard:\nwK .\nCommands:\nwait 1000\n"
    board_lines, command_lines = split_sections(text)
    assert board_lines == ["wK ."]
    assert command_lines == ["wait 1000"]


# --- parse_command ---

def test_parse_command_click_has_two_args():
    assert parse_command("click 50 150") == Command(CMD_CLICK, ("50", "150"))


def test_parse_command_wait_has_one_arg():
    assert parse_command("wait 1000") == Command(CMD_WAIT, ("1000",))


def test_parse_command_promote_has_three_args():
    assert parse_command("promote 0 1 Q") == Command(CMD_PROMOTE, ("0", "1", "Q"))


def test_parse_command_print_board_is_a_single_command_with_no_args():
    assert parse_command("print board") == Command(CMD_PRINT_BOARD, ())


def test_parse_command_print_score_is_a_single_command_with_no_args():
    assert parse_command("print score") == Command(CMD_PRINT_SCORE, ())


def test_parse_command_print_promotions_is_a_single_command_with_no_args():
    assert parse_command("print promotions") == Command(CMD_PRINT_PROMOTIONS, ())


# --- parse_script ---

def test_parse_script_combines_board_lines_and_parsed_commands():
    text = "Board:\nwK . .\nCommands:\nclick 50 50\nprint board\n"
    board_lines, commands = parse_script(text)
    assert board_lines == ["wK . ."]
    assert commands == [Command(CMD_CLICK, ("50", "50")), Command(CMD_PRINT_BOARD, ())]


def test_parse_script_with_empty_text_yields_nothing():
    board_lines, commands = parse_script("")
    assert board_lines == []
    assert commands == []