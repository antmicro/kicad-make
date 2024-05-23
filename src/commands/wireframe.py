import argparse
import logging
import os

from kiutils.board import Board

from common.kicad_project import KicadProject
from common.kmake_helper import run_kicad_cli

log = logging.getLogger(__name__)


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "wireframe", help="Split outline layer to top/bottom and optionally export it as .png and .gbr files."
    )
    parser.add_argument(
        "-r",
        "--reset",
        action="store_true",
        help="Reset layer of outline items to User.9 .",
    )
    parser.add_argument(
        "-e",
        "--export",
        action="store_true",
        help="Exports board wireframe as .svg and .gbr files.",
    )
    parser.set_defaults(func=run)


def run(ki_pro: KicadProject, args: argparse.Namespace) -> None:
    if not len(ki_pro.pcb_file):
        log.error("PCB file was not detected or does not exists")
        return

    log.info("Loading PCB")
    board = Board.from_file(ki_pro.pcb_file)

    for footprint in board.footprints:
        log.debug(f"Processing footprint {footprint.path}")

        target_layer = "User.8" if footprint.layer == "F.Cu" else "User.9"

        if args.reset:
            target_layer = "User.9"

        outline_items = [item for item in footprint.graphicItems if item.layer == "User.9" or item.layer == "User.8"]

        for item in outline_items:
            item.layer = target_layer

    log.info("Finished changing layer of outline items for all footprints")
    log.info("Saving PCB")
    board.to_file()

    if args.export:
        export_wireframe_gerbers(ki_pro)
        export_wireframe_svg(ki_pro)


def __export_svg(ki_pro: KicadProject, layers: str, output_file: str) -> None:
    log.info(f"Exporting {layers} svg to {output_file}")

    svg_export_cli_command = [
        "pcb",
        "export",
        "svg",
        ki_pro.pcb_file,
        "-o",
        output_file,
        "-l",
        layers,
        "--black-and-white",
        "--exclude-drawing-sheet",
        "--page-size-mode",
        "2",
    ]
    run_kicad_cli(svg_export_cli_command, True)


def export_wireframe_svg(ki_pro: KicadProject) -> None:
    output_folder = os.path.join(ki_pro.fab_dir, "wireframe/")
    os.makedirs(output_folder, exist_ok=True)

    __export_svg(
        ki_pro,
        "User.8,Edge.Cuts",
        os.path.join(output_folder, "wireframe_top.svg"),
    )
    __export_svg(
        ki_pro,
        "User.9,Edge.Cuts",
        os.path.join(output_folder, "wireframe_bottom.svg"),
    )


def __export_gerber(ki_pro: KicadProject, layers: str, output_file: str) -> None:
    log.info(f"Exporting {layers} gerber to {output_file}")

    gerber_export_cli_command = [
        "pcb",
        "export",
        "gerber",
        ki_pro.pcb_file,
        "-o",
        output_file,
        "--precision",
        "6",
        "-l",
        layers,
    ]
    run_kicad_cli(gerber_export_cli_command, False)


def export_wireframe_gerbers(ki_pro: KicadProject) -> None:
    output_folder = os.path.join(ki_pro.fab_dir, "wireframe/")
    os.makedirs(output_folder, exist_ok=True)

    __export_gerber(
        ki_pro,
        "User.8,Edge.Cuts",
        os.path.join(output_folder, "wireframe_top.gbr"),
    )
    __export_gerber(
        ki_pro,
        "User.9,Edge.Cuts",
        os.path.join(output_folder, "wireframe_bottom.gbr"),
    )
