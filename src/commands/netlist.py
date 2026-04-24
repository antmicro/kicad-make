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

    sch_export_cli_command = ["sch", "export", "netlist", "-o", output_netlist_file, input_sch_file]

    run_kicad_cli(sch_export_cli_command, True)
    log.info(f"Saved to {output_netlist_file}")


def run(pro: KicadProject, args: argparse.Namespace) -> None:
    pro.fab_dir.mkdir(exist_ok=True, parents=True)
    generate_netlist(pro.sch_root.fs_path, pro.fab_dir / "netlist.net")
