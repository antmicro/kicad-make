"""Netlist generation script"""

import argparse
import logging

from common.kicad_project import KicadProject
from common.kmake_helper import run_kicad_cli

log = logging.getLogger(__name__)


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Register parser and its arguments as subparser"""
    netlist_parser = subparsers.add_parser("netlist", help="Create KiCad netlist file.")
    netlist_parser.set_defaults(func=run)


def generate_netlist(input_sch_file: str, output_netlist_file: str) -> None:
    """Exports netlist from schematic

    Creates netlist from root schematic.
    Default output format
    """

    sch_export_cli_command = "sch export netlist"
    options = f"-o {output_netlist_file} {input_sch_file}"

    command = f"{sch_export_cli_command} {options}"
    run_kicad_cli(command.split(), True)
    log.info(f"Saved to {output_netlist_file}")


def run(kicad_project: KicadProject, args: argparse.Namespace) -> None:
    kicad_project.create_fab_dir()
    generate_netlist(kicad_project.sch_root, f"{kicad_project.relative_fab_path}/netlist.net")
