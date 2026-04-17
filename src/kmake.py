"""KiCad automation scripts"""

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Callable, List

from rich.logging import RichHandler

import commands
from common.kicad_project import KicadProject

external_modules_loaded = False
if os.path.isdir(os.path.join(os.path.dirname(__file__), "ext_modules")):
    import ext_modules

    external_modules_loaded = True


######## ARGUMENT PARSING ########
def get_help_formatter() -> Callable:
    """Returns help formatter"""
    return lambda prog: argparse.HelpFormatter(prog, max_help_position=35)


def dir_path(string: str) -> str:
    if os.path.isdir(string):
        return string

    raise NotADirectoryError(string)


def get_parser() -> argparse.ArgumentParser:
    """Create parser, import subparsers from commands/ext_modules and parse them
    Returns parsed arguments"""
    formatter = get_help_formatter()
    parser = argparse.ArgumentParser(
        prog="kmake",
        prefix_chars="-",
        formatter_class=formatter,
        description="kmake - collection of command line KiCad automation utilites. \
Program must be run in project workdir.",
    )

    parser.add_argument(
        "--debug",
        "--verbose",
        "--dbg",
        action="store_true",
        dest="debug",
        help="increase verbosity, keep temp files",
    )

    parser.add_argument(
        "--share-path", type=dir_path, action="store", default=None, help="path to local shared directory"
    )

    subparsers = parser.add_subparsers(
        title="Subcommands",
        dest="subcommand",
        help='To display help for specific subcommand use "kmake SUBCOMMAND -h"',
        required=True,
    )

    commands_names = list(
        filter(
            lambda f: ".py" in f,
            os.listdir(os.path.join(os.path.dirname(__file__), "commands")),
        )
    )

    for module_dir in dir(commands):
        if "__" in module_dir:
            continue
        if module_dir + ".py" in commands_names:
            getattr(commands, module_dir).add_subparser(subparsers)

    if external_modules_loaded is False:
        return parser

    ext_modules_names = list(
        filter(
            lambda f: ".py" in f,
            os.listdir(os.path.join(os.path.dirname(__file__), "ext_modules")),
        )
    )

    for module_dir in dir(ext_modules):
        if "__" in module_dir:
            continue
        if module_dir + ".py" in ext_modules_names:
            getattr(ext_modules, module_dir).add_subparser(subparsers)

    return parser


def parse_arguments(args: List[str]) -> argparse.Namespace:
    parser = get_parser()
    return parser.parse_args(args)


######## MAIN ########


def main() -> None:
    """Main kmake function"""
    args = parse_arguments(sys.argv[1:])

    ######## LOGGING SETUP ########

    log_level = logging.DEBUG if args.debug else logging.INFO

    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            RichHandler(
                level=log_level,
                show_time=True,
                show_level=True,
                show_path=args.debug,  # show file:line only in debug
                rich_tracebacks=True,
            )
        ],
    )

    log = logging.getLogger("kmake")
    log.debug("Running in debug mode")

    pro_path = Path.cwd()
    no_log_subcommands = ["init-project"]
    disable_logging = args.subcommand in no_log_subcommands

    kpro = KicadProject(path=pro_path, disable_logging=disable_logging, local_share_path=args.share_path).load()

    # Run selected tool
    args.func(kpro, args)


if __name__ == "__main__":
    main()
