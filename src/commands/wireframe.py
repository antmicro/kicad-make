import argparse
import logging
import os

from kiutils.board import Board

from common.kicad_project import KicadProject
from common.kmake_helper import run_kicad_cli

from .pcb_filter import pcb_filter_run

from tempfile import NamedTemporaryFile
from typing import List, Dict, Any

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
        "-i",
        "--input",
        action="store",
        help="Use specified *.kicad_pcb file as input",
    )
    parser.add_argument(
        "-p",
        "--preset",
        choices=["simple", "dimensions", "descriptions"],
        action="store",
        help="Generate SVG according to preset",
    )
    parser.set_defaults(func=run)


def run(ki_pro: KicadProject, args: argparse.Namespace) -> None:
    if args.input is None:
        args.input = ki_pro.pcb_file
    if not len(args.input):
        log.error("PCB file was not detected or does not exists")
        return

    if args.reset:
        log.info("Loading PCB")
        board = Board.from_file(args.input)
        log.info("Reseting wireframes layer")

        for footprint in board.footprints:
            log.debug(f"Processing footprint {footprint.path}")

            outline_items = [
                item for item in footprint.graphicItems if item.layer == "User.9" or item.layer == "User.8"
            ]

            for item in outline_items:
                item.layer = "User.9"

        log.info("Finished changing layer of outline items for all footprints")
        log.info("Saving PCB")
        board.to_file(args.input)
        return

    # (name, filter_args, side)
    presets = [
        (
            "simple",
            dict(
                stackup=True,
                dimensions=True,
                references=True,
                values=True,
                exclude=["M", "A"],
                allowed_layers="User.9,Edge.Cuts",
            ),
            ["top", "bottom"],
        ),
        (
            "dimensions",
            dict(
                stackup=True,
                references=True,
                values=True,
                allow="J MH H MP".split(),
                allow_other="MH H MP".split(),
                allowed_layers="User.9,Edge.Cuts,User.Comments",
            ),
            ["top", "bottom", ""],
        ),
        (
            "descriptions",
            dict(
                stackup=True,
                references=True,
                values=True,
                allow="J MH H MP SW TP D S".split(),
                allowed_layers="User.9,Edge.Cuts,User.Drawings",
            ),
            ["top", "bottom"],
        ),
    ]
    for preset in presets:
        if preset[0] == args.preset:
            break
    else:
        preset = (
            args.input.removesuffix(".kicad_pcb") + "_wireframe",
            dict(allowed_layers="User.9,Edge.Cuts"),
            ["top", "bottom"],
        )

    export_wireframe(preset[0], preset[1], preset[2], ki_pro, args.input)


def export_wireframe(oname: str, filter_args: Dict[str, Any], sides: List[str], kpro: KicadProject, ifile: str) -> None:
    output_folder = os.path.join(kpro.fab_dir, "wireframe/")
    os.makedirs(output_folder, exist_ok=True)

    layers = filter_args["allowed_layers"]

    for side in sides:
        with NamedTemporaryFile(suffix=".kicad_pcb") as fp:
            if side != "":
                oname_side = f"{oname}_{side}"
            else:
                oname_side = f"{oname}"

            filter_args["outfile"] = fp.name
            filter_args["infile"] = ifile
            filter_args["side"] = side
            pcb_filter_run(kpro, **filter_args)

            # SVG
            outfile = os.path.join(output_folder, oname_side + ".svg")
            log.info(f"Exporting {layers} svg to {outfile}")
            svg_export_cli_command = [
                "pcb",
                "export",
                "svg",
                fp.name,
                "-o",
                outfile,
                "-l",
                layers,
                "--black-and-white",
                "--exclude-drawing-sheet",
                "--page-size-mode",
                "2",
            ]
            run_kicad_cli(svg_export_cli_command, True)

            # GERBER
            outfile = os.path.join(output_folder, oname_side + ".gbr")
            log.info(f"Exporting {layers} gerber to {outfile}")
            gerber_export_cli_command = [
                "pcb",
                "export",
                "gerber",
                fp.name,
                "-o",
                outfile,
                "--precision",
                "6",
                "-l",
                layers,
            ]
            run_kicad_cli(gerber_export_cli_command, True)
