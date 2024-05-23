import argparse
import logging
import os
import tempfile

from kiutils.board import Board

from common.kicad_project import KicadProject
from common.kmake_helper import run_kicad_cli

log = logging.getLogger(__name__)


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Adds pnp subparser to passed parser"""

    pnp_parser = subparsers.add_parser("pnp", help="Create footprint position files.")
    pnp_parser.add_argument(
        "-t",
        "--tht",
        action="store_true",
        help="Include `THT` components in output.",
    )
    pnp_parser.add_argument(
        "-v",
        "--virtual",
        action="store_true",
        help="Include `Virtual` components in output.",
    )
    pnp_parser.add_argument(
        "-o",
        "--other",
        action="store_true",
        help="Include `Other` type components in output.",
    )
    pnp_parser.add_argument(
        "-e",
        "--excluded",
        action="store_true",
        help="Include components excluded from position files in output.",
    )
    pnp_parser.set_defaults(func=run)


def convert_other_to_smd(board: Board) -> Board:
    """Converts components of type `undefined` to `smd` type"""
    for footprint in board.footprints:
        if footprint.attributes.type is None:
            footprint.attributes.type = "smd"
    return board


def convert_virual_to_smd(board: Board) -> Board:
    """Converts components of type `virtual` to `smd` type"""
    for footprint in board.footprints:
        if footprint.attributes.type == "virtual":
            footprint.attributes.type = "smd"
    return board


def unset_exclude_from_position_file(board: Board) -> Board:
    """Unsets `Exclude from position file` field on the components"""
    for footprint in board.footprints:
        if footprint.attributes.excludeFromPosFiles is True:
            footprint.attributes.excludeFromPosFiles = False
    return board


def export_pnp(
    board: str,
    output_file_name: str = '""',
    side: str = "both",
    output_format: str = "csv",
    units: str = "mm",
    bottom_negate_x: bool = False,
    drill_origin: bool = False,
    smd_only: bool = True,
    exclude_fp_th: bool = False,
    gerber_board_edge: bool = False,
    verbose: bool = False,
) -> None:
    """Generate pick and place position file from the given PCB file."""

    assert board != "", "Empty board filename"
    assert output_file_name != "", "Empty output file name"

    pnp_export_cli_command = ["pcb", "export", "pos"]

    if gerber_board_edge:
        assert output_format == "gerber", "gerber_board_edge supported only in gerber format"

    pnp_export_cli_command.extend(
        [board, "-o", output_file_name, "--format", output_format, "--units", units, "--side", side]
    )

    if bottom_negate_x:
        pnp_export_cli_command.extend(["--bottom-negate-x"])
    if drill_origin:
        pnp_export_cli_command.extend(["--use-drill-file-origin"])
    if smd_only:
        pnp_export_cli_command.extend(["--smd-only"])
    if exclude_fp_th:
        pnp_export_cli_command.extend(["--exclude-fp-th"])
    if gerber_board_edge:
        pnp_export_cli_command.extend(["--gerber-board-edge"])

    run_kicad_cli(pnp_export_cli_command, verbose)
    log.info("Saved to %s", output_file_name.replace(os.getcwd(), ""))


def run(kicad_project: KicadProject, args: argparse.Namespace) -> None:
    """Run pnp command"""
    board_path = kicad_project.pcb_file
    kicad_project.create_fab_dir()
    temporary_board_file = None

    if args.tht:
        log.info("Added 'tht' flag. Through hole components treated as SMD.")

    if args.virtual or args.excluded or args.other:
        log.info("Loading PCB")
        board = Board.from_file(kicad_project.pcb_file)
        log.info("Creating tmp PCB for manipulation and using it for output generation")
        temporary_board_file = tempfile.NamedTemporaryFile(suffix=".kicad_pcb")
        board.filePath = temporary_board_file.name

        if args.virtual:
            convert_virual_to_smd(board)
        if args.other:
            convert_other_to_smd(board)
        if args.excluded:
            unset_exclude_from_position_file(board)

        board.to_file(temporary_board_file.name)
        board_path = temporary_board_file.name

    pnp_path_base = f"{kicad_project.fab_dir}/{kicad_project.name}"

    combinations = [
        ("front", "ascii", "-top.pos"),
        ("back", "ascii", "-bottom.pos"),
        ("front", "csv", "-top-pos.csv"),
        ("back", "csv", "-bottom-pos.csv"),
    ]
    for side, output_format, suffix in combinations:
        export_pnp(
            board_path,
            output_file_name=pnp_path_base + suffix,
            side=side,
            output_format=output_format,
            drill_origin=True,
            smd_only=not args.tht,
            bottom_negate_x=True,
            verbose=args.debug,
        )

    if temporary_board_file:
        log.info("Removing tmp PCB file")
        temporary_board_file.close()
