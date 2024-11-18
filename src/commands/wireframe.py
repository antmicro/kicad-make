import argparse
import logging
import os
import json

from kiutils.board import Board
from kiutils.footprint import Footprint
from kiutils.items.common import Effects, Stroke, Position
from kiutils.items.fpitems import FpText
from kiutils.items.gritems import GrText, GrLine, GrArc, GrCircle, GrPoly, GrRect

from common.kicad_project import KicadProject
from common.kmake_helper import run_kicad_cli

from .pcb_filter import pcb_filter_run

from tempfile import NamedTemporaryFile
from typing import List, Dict, Any
from pathlib import Path

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
    parser.add_argument(
        "--generate-frame",
        action="store_true",
        help="""Generate output that is rectangle created from board outline b-box expanded by 60mm""",
    )
    parser.add_argument(
        "-f",
        "--pcb-filter-args",
        type=json.loads,
        help="""Additional arguments to be passed to pcb-filter; 
        eg. `-f '{"ref_filter":"+J+D-D1"}'` """,
    )
    parser.add_argument(
        "-a",
        "--pcb-filter-args-append",
        type=json.loads,
        help="""Additional arguments to be passed to pcb-filter
        (lists/string will be appended to default ones)
        eg. `-p simple -a '{"ref_filter":"+M1"}'` (results in `"ref_filter":"-M-A+M1"`)""",
    )
    parser.set_defaults(func=run)


def run(ki_pro: KicadProject, args: argparse.Namespace) -> None:
    if args.input is None:
        args.input = ki_pro.pcb_file
    if not len(args.input):
        log.error("PCB file was not detected or does not exists")
        return

    if args.generate_frame:
        generate_frame(ki_pro)
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
                keep_edge=True,
                ref_filter="-M-A",
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
                keep_edge=True,
                ref_filter="+J+MH+H+MP",
                ref_filter_other="+MH+H+MP",
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
                keep_edge=True,
                ref_filter="+J+MH+H+MP+SW+TP+D+S",
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
                keep_edge=True,
                ref_filter="-TP-MP-M-A-REF**",
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
    preset[1].update(args.pcb_filter_args if args.pcb_filter_args is not None else {})

    def append_dict_val(key: str) -> None:
        pres = preset[1].get(key)
        if pres is not None:
            args.pcb_filter_args_append[key] = pres + args.pcb_filter_args_append.get(key, "")

    if args.pcb_filter_args_append is not None:
        append_dict_val("ref_filter")
        append_dict_val("ref_filter_other")
        append_dict_val("allowed_layers")
        append_dict_val("allowed_layers_full")
        preset[1].update(args.pcb_filter_args_append)

    generate_wireframe(preset[0], preset[1], preset[2], preset[3], ki_pro, args.input, args.set_ref)


def mirror_text_justify(effects: Effects) -> Effects:
    effects.justify.mirror = True
    if effects.justify.horizontally == "right":
        effects.justify.horizontally = "left"
    elif effects.justify.horizontally == "left":
        effects.justify.horizontally = "right"
    return effects


def mirror_footprint_text(fp: Footprint) -> Footprint:
    fpp = []
    for p in fp.properties:
        if p.effects is None:
            p.effects = Effects()
        p.effects = mirror_text_justify(p.effects)
        fpp.append(p)
    fp.properties = fpp

    fpgi = []
    for g in fp.graphicItems:
        if isinstance(g, FpText):
            g.effects = mirror_text_justify(g.effects)
        fpgi.append(g)
    fp.graphicItems = fpgi
    return fp


def mirror_texts(board: Board) -> Board:
    board.footprints = [mirror_footprint_text(fp) for fp in board.footprints]

    brdgi = []
    for g in board.graphicItems:
        if isinstance(g, GrText):
            g.effects = mirror_text_justify(g.effects)
        brdgi.append(g)
    board.graphicItems = brdgi

    brdd = []
    for d in board.dimensions:
        if d.grText is not None:
            d.grText = GrText()
        d.grText.effects = mirror_text_justify(d.grText.effects)
        brdd.append(d)
    board.dimensions = brdd
    return board


def board_process(brd_path: str, side: str) -> None:
    board = Board.from_file(brd_path)

    # set all lines to same width
    bgi = []
    for g in board.graphicItems:
        if (
            isinstance(g, GrArc)
            or isinstance(g, GrLine)
            or isinstance(g, GrCircle)
            or isinstance(g, GrPoly)
            or isinstance(g, GrRect)
        ) and g.layer == "Edge.Cuts":
            g.stroke = Stroke(width=0.12)
        bgi.append(g)
    board.graphicItems = bgi

    if side == "bottom":
        board = mirror_texts(board)

    board.to_file()


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

            board_process(filter_args["outfile"], side)

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
                do_exports(fp.name, output_folder, oname_side_l, layer, side)


def do_exports(ifile: str, output_folder: str, oname_side_l: str, layer: str, side: str) -> None:
    # SVG
    outfile = os.path.join(output_folder, "wireframe_" + oname_side_l + ".svg")
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
    if side == "bottom":
        svg_export_cli_command.append("--mirror")

    run_kicad_cli(svg_export_cli_command, True)

    # GERBER
    outfile = os.path.join(output_folder, "wireframe_" + oname_side_l + ".gbr")
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


def generate_frame(kpro: KicadProject) -> None:
    with NamedTemporaryFile(suffix=".kicad_pcb") as fp:

        filter_args = {"outfile": fp.name, "infile": kpro.pcb_file, "keep_edge": True, "allowed_layers": "Edge.Cuts"}

        log.info("Run PCB filter")
        pcb_filter_run(kpro, **filter_args)
        board = Board.from_file(fp.name)
        x = []
        y = []
        for item in board.graphicItems:
            if item.layer != "Edge.Cuts":
                continue
            if hasattr(item, "start"):
                x.append(item.start.X)
                y.append(item.start.Y)
            if hasattr(item, "end"):
                x.append(item.end.X)
                y.append(item.end.Y)
            if hasattr(item, "mid"):
                x.append(item.mid.X)
                y.append(item.mid.Y)
            if hasattr(item, "coordinates"):
                x.append([c.X for c in item.coordinates])
                y.append([c.Y for c in item.coordinates])
        border = 60
        board.graphicItems.append(
            GrRect(
                Position(min(x) - border, min(y) - border), Position(max(x) + border, max(y) + border), layer="Margin"
            )
        )
        board.to_file()

        outfile = Path(kpro.fab_dir) / "wireframe" / "margin.gbr"
        log.info(f"Exporting `Margin` gerber to {outfile}")
        gerber_export_cli_command = [
            "pcb",
            "export",
            "gerber",
            fp.name,
            "-o",
            str(outfile),
            "--precision",
            "6",
            "-l",
            "Margin",
        ]
        run_kicad_cli(gerber_export_cli_command, True)
