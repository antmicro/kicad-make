from importlib.metadata import version
from pip._internal.operations import freeze
import argparse
import logging
from common.kicad_project import KicadProject

log = logging.getLogger(__name__)


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Register parser and its arguments as subparser."""
    init_project_parser = subparsers.add_parser("version", help="Print kmake, kiutils & kicad version")
    init_project_parser.set_defaults(func=run)


def main(project: KicadProject, args: argparse.Namespace) -> None:
    """Main module function."""
    kiutils_ver = [pkg for pkg in freeze.freeze() if "kiutils" in pkg][0]
    print(f"kmake   : {version('kmake')}")
    print(f"kicad   : {project.kicad_version_full}")
    print(f"kiutils : {version('kiutils')} ({kiutils_ver})")


def run(project: KicadProject, args: argparse.Namespace) -> None:
    """Entry function for module."""
    main(project, args)
