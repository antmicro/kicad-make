import argparse
import logging

from common.kicad_project import KicadProject
from common.kmake_helper import run_kicad_cli

log = logging.getLogger(__name__)


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    sch_parser = subparsers.add_parser("sch", help="Generate schematics in PDF format.")
    sch_parser.add_argument(
        "-t",
        "--theme",
        nargs="?",
        action="store",
        type=str,
        default="",
        help="Theme to use for the schematic (default: schematic settings).",
    )
    sch_parser.set_defaults(func=run)


def run(kicad_project: KicadProject, args: argparse.Namespace) -> None:
    kicad_project.create_doc_dir()
    log.info("Generating schematic")
    export_schematic(kicad_project.sch_root, f"{kicad_project.doc_dir}/{kicad_project.name}-schematic.pdf", args.theme)


def export_schematic(
    input_sch_file: str,
    output: str = '""',  # default: project_dir/project_name.pdf
    theme: str = '""',  # default: schematic settings
) -> None:
    """Exports KiCad schematic file to PDF format.

    Includes all nested sheets (subsheets) from given file."""

    sch_export_cli_command = ["sch", "export", "pdf", input_sch_file]
    if len(output):
        sch_export_cli_command.extend(["-o", output])
    if len(theme):
        sch_export_cli_command.extend(["-t", theme])

    run_kicad_cli(sch_export_cli_command, True)
