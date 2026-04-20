import argparse
import logging

from askiff import Project

log = logging.getLogger(__name__)


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("prettify", help="Prettify files to conform with KiCad formatter")
    parser.set_defaults(func=run)


def run(pro: Project, _args: argparse.Namespace) -> None:
    log.info("Prettifying KiCad files")
    for file in (*pro.pcb, *pro.sch):
        # askiff saves properly formatted files
        file.to_file()
