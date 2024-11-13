"""KiCad automation scripts"""

import argparse
import logging
import os
import sys
from typing import Callable, List

import coloredlogs

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

    if args.debug:
        coloredlogs.install(
            fmt="[%(asctime)s][%(name)15s:%(lineno)03d][%(levelname).4s] %(message)s",
            datefmt="%H:%M:%S",
            stream=sys.stdout,
            level=logging.DEBUG,
        )
    else:
        coloredlogs.install(
            fmt="[%(asctime)s][%(levelname).4s] %(message)s",
            datefmt="%H:%M:%S",
            stream=sys.stdout,
            level=logging.INFO,
        )

    log = logging.getLogger("kmake")
    log.debug("Running in debug mode")

    no_log_subcommands = ["init-project"]
    if args.subcommand in no_log_subcommands:
        kpro = KicadProject(disable_logging=True)
    else:
        kpro = KicadProject()
    assert float(kpro.kicad_version) >= 8.0, "Kmake requires KiCad 8.0+ project file"
    # Run selected tool
    args.func(kpro, args)


if __name__ == "__main__":
    main()
