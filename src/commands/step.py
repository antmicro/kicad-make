"""Simple KiCad CLI Python wrapper"""

import argparse
import logging

from common.kicad_project import KicadProject
from common.kmake_helper import run_kicad_cli

log = logging.getLogger(__name__)


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    step_parser = subparsers.add_parser("step", help="Export 3D models of PCB in STEP format.")
    step_parser.set_defaults(func=run)


def run(kicad_project: KicadProject, args: argparse.Namespace) -> None:
    kicad_project.create_step_model3d_dir()

    step_file_name = f"{kicad_project.name}.step"
    output_file_path = f"{kicad_project.step_model3d_dir}/{step_file_name}"

    log.info("Exporting 3D STEP as %s", output_file_path)

    export_step(
        kicad_project.pcb_file,
        output_file_path,
        verbose=args.debug,
    )


def export_step(
    input_pcb_file: str,
    output_file_name: str = '""',
    verbose: bool = False,
) -> None:
    """Generate 3D STEP model from the given PCB file."""

    step_export_cli_command = ["pcb", "export", "step", input_pcb_file, "-o", output_file_name]

    run_kicad_cli(step_export_cli_command, verbose)
