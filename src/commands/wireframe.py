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
        "wireframe", help="Split outline layer to top/bottom and optionally export it as .svg and .gbr files."
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
        choices=["simple", "dimensions", "descriptions", "assembly_drawing"],
        action="store",
        help="Generate SVG according to preset",
    )
    parser.add_argument(
        "-sr",
        "--set-ref",
        action="store_true",
        help="Set footprint references to certain state (reset position, set size, ..)",
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
            ["User.9,Edge.Cuts"],
        ),
        (
            "dimensions",
            dict(
                stackup=True,
                references=True,
                values=True,
                allow="J MH H MP".split(),
                allow_other="MH H MP".split(),
                allowed_layers="User.9,Edge.Cuts,User.Drawings",
            ),
            ["top", "bottom", ""],
            ["User.9,Edge.Cuts,User.Drawings"],
        ),
        (
            "descriptions",
            dict(
                stackup=True,
                references=True,
                dimensions=True,
                values=True,
                allow="J MH H MP SW TP D S".split(),
                allowed_layers="User.9,Edge.Cuts,User.Comments,User.Eco1,User.Eco2",
            ),
            ["top", "bottom"],
            ["User.9,Edge.Cuts,User.Comments,User.Eco$numside"],
        ),
        (
            "assembly_drawing",
            dict(
                stackup=True,
                dimensions=True,
                vias=True,
                zones=True,
                exclude="TP MP M A REF**".split(),
                allowed_layers="User.9,Edge.Cuts,F.SilkS,B.SilkS",
            ),
            ["top", "bottom"],
            "User.9,Edge.Cuts,$side.Fab,$side.Paste".split(","),
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
            ["User.9,Edge.Cuts"],
        )

    generate_wireframe(preset[0], preset[1], preset[2], preset[3], ki_pro, args.input, args.set_ref)


def generate_wireframe(
    oname: str,
    filter_args: Dict[str, Any],
    sides: List[str],
    export_layers: List[str],
    kpro: KicadProject,
    ifile: str,
    set_ref: bool,
) -> None:
    output_folder = os.path.join(kpro.fab_dir, "wireframe/")
    os.makedirs(output_folder, exist_ok=True)

    for side in sides:
        with NamedTemporaryFile(suffix=".kicad_pcb") as fp:
            if side != "":
                oname_side = f"{oname}_{side}"
            else:
                oname_side = f"{oname}"

            filter_args["outfile"] = fp.name
            filter_args["infile"] = ifile
            filter_args["side"] = side

            log.info("Run PCB filter")
            pcb_filter_run(kpro, **filter_args)

            if set_ref:
                reset_footprint_val_props(fp.name)

            for layer in export_layers:
                slayer = layer.split(",")
                for idx, sl in enumerate(slayer):
                    if side == "top":
                        slayer[idx] = sl.replace("$side", "F")
                        slayer[idx] = sl.replace("$numside", "1")
                    elif side == "bottom":
                        slayer[idx] = sl.replace("$side", "B")
                        slayer[idx] = sl.replace("$numside", "2")
                    else:  # side==""
                        slayer[idx] = sl.replace("$side", "F") + "," + sl.replace("$side", "B")
                        slayer[idx] = sl.replace("$numside", "1") + "," + sl.replace("$numside", "2")
                layer = ",".join(slayer)

                if len(export_layers) == 1:
                    oname_side_l = oname_side
                else:
                    oname_side_l = oname_side + "_" + layer.replace(".", "_")
                do_exports(fp.name, output_folder, oname_side_l, layer)


def do_exports(ifile: str, output_folder: str, oname_side_l: str, layer: str) -> None:
    # SVG
    outfile = os.path.join(output_folder, oname_side_l + ".svg")
    log.info(f"Exporting {layer} svg to {outfile}")
    svg_export_cli_command = [
        "pcb",
        "export",
        "svg",
        ifile,
        "-o",
        outfile,
        "-l",
        layer,
        "--black-and-white",
        "--exclude-drawing-sheet",
        "--page-size-mode",
        "2",
    ]
    run_kicad_cli(svg_export_cli_command, True)

    # GERBER
    outfile = os.path.join(output_folder, oname_side_l + ".gbr")
    log.info(f"Exporting {layer} gerber to {outfile}")
    gerber_export_cli_command = [
        "pcb",
        "export",
        "gerber",
        ifile,
        "-o",
        outfile,
        "--precision",
        "6",
        "-l",
        layer,
    ]
    run_kicad_cli(gerber_export_cli_command, True)


def reset_footprint_val_props(file: str) -> None:
    try:
        import pcbnew

        log.info("Reset footprint reference properties")

        board = pcbnew.LoadBoard(file)
        # board = pcbnew.GetBoard() # Used in KiCad scripting console
        modules = board.GetFootprints()
        for m in modules:
            m.Reference().SetVisible(True)
            m.Reference().SetKeepUpright(True)
            m.Reference().SetPosition(m.GetPosition())
            m.Reference().SetVertJustify(0)
            m.Reference().SetHorizJustify(0)
            m.Reference().SetTextSize(pcbnew.VECTOR2I(350000, 350000))
            m.Reference().SetTextThickness(70000)
        for m in [m for m in board.GetFootprints() if "F" in board.GetLayerName(m.GetLayer())]:
            m.Reference().SetLayer(pcbnew.F_Fab)
        for m in [m for m in board.GetFootprints() if "B" in board.GetLayerName(m.GetLayer())]:
            m.Reference().SetLayer(pcbnew.B_Fab)
        board.Save(file)
        # pcbnew.Refresh() # Used in KiCad scripting console
    except ModuleNotFoundError:
        log.error("Module `pcbnew`(KiCad API) can not be found!")
        log.warning("Add `pcbnew.py` to paths recognized by python")
        log.warning("OR run above block code in KiCad scripting console")
        log.error("Footprint value properties has not be set!")
