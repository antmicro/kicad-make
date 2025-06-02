import argparse
import logging
from typing import Optional

from common.kicad_project import KicadProject

log = logging.getLogger(__name__)


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("prettify", help="Pretify files to conform with KiCad formatter")
    parser.set_defaults(func=run)


def run(kicad_project: KicadProject, args: argparse.Namespace) -> None:
    log.info("Prettyfying kicad files")
    formatted = ""
    with open(kicad_project.pcb_file, "r") as file:
        formatted = prettify(file.read())
    with open(kicad_project.pcb_file, "w") as file:
        file.write(formatted)
    for sch_file in kicad_project.all_sch_files:
        formatted = ""
        with open(sch_file, "r") as file:
            formatted = prettify(file.read())
        with open(sch_file, "w") as file:
            file.write(formatted)


def prettify(source: str, quote_char: str = '"') -> str:
    # Configuration
    indent_char = "\t"
    indent_size = 1

    # Special case handling for long (xy ...) lists.
    xy_special_case_column_limit = 99
    consecutive_token_wrap_threshold = 72

    formatted = []
    cursor = 0
    list_depth = 0
    last_non_whitespace = ""
    in_quote = False
    has_inserted_space = False
    in_multi_line_list = False
    in_xy = False
    column = 0
    backslash_count = 0

    def next_non_whitespace(index: int) -> Optional[tuple[str, int]]:
        seek = index
        while seek < len(source) and source[seek].isspace():
            seek += 1
        if seek == len(source):
            return None  # Reached the end of source
        return source[seek], seek

    def is_xy(index: int) -> bool:
        if index + 2 >= len(source):
            return False
        if (
            source[index + 1] == "x"
            and source[index + 2] == "y"
            and (index + 3 < len(source) and source[index + 3] == " ")
        ):
            return True
        return False

    while cursor < len(source):
        schar = source[cursor]
        if schar.isspace() and not in_quote:
            next_char_info = next_non_whitespace(cursor)
            if next_char_info is None:
                break
            next_char, _ = next_char_info
            if (
                not has_inserted_space
                and list_depth > 0
                and last_non_whitespace != "("
                and next_char != ")"
                and next_char != "("
            ):
                if in_xy or column < consecutive_token_wrap_threshold:
                    formatted.append(" ")
                    column += 1
                else:
                    # Ensure no trailing spaces before new lines
                    if formatted and formatted[-1] == " ":
                        formatted.pop()  # Remove trailing space
                    formatted.append("\n" + (indent_char * list_depth))
                    column = list_depth * indent_size
                    in_multi_line_list = True
                has_inserted_space = True
        else:
            has_inserted_space = False

            if schar == "(" and not in_quote:
                current_is_xy = is_xy(cursor)

                if list_depth == 0:
                    formatted.append("(")
                    column += 1
                elif in_xy and current_is_xy and column < xy_special_case_column_limit:
                    formatted.append(" (")
                    column += 2
                else:
                    # Ensure no trailing spaces before new lines
                    if formatted and formatted[-1] == " ":
                        formatted.pop()  # Remove trailing space
                    formatted.append("\n" + (indent_char * list_depth) + "(")
                    column = list_depth * indent_size + 1

                in_xy = current_is_xy
                list_depth += 1
            elif schar == ")" and not in_quote:
                if list_depth > 0:
                    list_depth -= 1

                # Remove space before closing parenthesis
                if formatted and formatted[-1] == " ":
                    formatted.pop()

                if last_non_whitespace == ")" or in_multi_line_list:
                    formatted.append("\n" + (indent_char * list_depth) + ")")
                    column = list_depth * indent_size + 1
                    in_multi_line_list = False
                else:
                    formatted.append(")")
                    column += 1
            else:
                if schar == "\\":
                    backslash_count += 1
                elif schar == quote_char and (backslash_count % 2) == 0:
                    in_quote = not in_quote

                if schar != "\\":
                    backslash_count = 0

                formatted.append(schar)
                column += 1

            last_non_whitespace = schar

        cursor += 1

    # Ensure no trailing spaces before appending the final newline
    if formatted and formatted[-1] == " ":
        formatted.pop()

    # newline required at end of file for POSIX compliance
    formatted.append("\n")

    return "".join(formatted)
