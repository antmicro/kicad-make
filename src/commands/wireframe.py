import argparse
import logging
import os
import json

from kiutils.board import Board
from kiutils.footprint import Footprint
from kiutils.items.common import Effects, Stroke, Position, Font, Justify
from kiutils.items.fpitems import FpText
from kiutils.items.gritems import GrText, GrLine, GrArc, GrCircle, GrPoly, GrRect
from kiutils.items.dimensions import Dimension, DimensionFormat, DimensionStyle

from common.kicad_project import KicadProject
from common.kmake_helper import run_kicad_cli

from .pcb_filter import pcb_filter_run

from tempfile import NamedTemporaryFile
from typing import List, Dict, Any, Self
from pathlib import Path
from math import inf

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
    parser.add_argument(
        "--skip-dimension-mod",
        action="store_true",
        help="Do not modify main dimensions",
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

    generate_wireframe(
        preset[0], preset[1], preset[2], preset[3], ki_pro, args.input, args.set_ref, args.skip_dimension_mod
    )


def mirror_text_justify(effects: Effects) -> Effects:
    """Set text mirrored & flip its justification"""
    effects.justify.mirror = True
    if effects.justify.horizontally == "right":
        effects.justify.horizontally = "left"
    elif effects.justify.horizontally == "left":
        effects.justify.horizontally = "right"
    return effects


def mirror_footprint_text(fp: Footprint) -> Footprint:
    """Mirror texts inside footprint (property & standalone texts)"""
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
    """Mirror all text in pcb (footprint, dimension & standalone texts)"""
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


def standardize_main_dimensions(board: Board, side: str) -> List[Dimension]:
    """Remove largest dimensions and add new standardized ones
    (new dimensions will be on right board side for top and on left for bottom w text mirrored)"""

    dims = board.dimensions
    vertical = []
    horizontal = []
    rest = []
    (maxlen_x, maxlen_y) = (0, 0)
    # remove largest dimensions
    for d in dims:
        len_x = abs(d.pts[0].X - d.pts[1].X)
        len_y = abs(d.pts[0].Y - d.pts[1].Y)
        if (d.type == "aligned" and len_x * 10 < len_y) or (d.type == "orthogonal" and d.orientation == 1):
            vertical.append(d)
            if maxlen_y < len_y:
                maxlen_y = len_y
        elif (d.type == "aligned" and len_x > 10 * len_y) or (d.type == "orthogonal" and d.orientation == 0):
            horizontal.append(d)
            if maxlen_x < len_x:
                maxlen_x = len_x
        else:
            rest.append(d)
    vertical = [d for d in vertical if maxlen_y - abs(d.pts[0].Y - d.pts[1].Y) > 0.01]
    horizontal = [d for d in horizontal if maxlen_x - abs(d.pts[0].X - d.pts[1].X) > 0.01]

    # Add new vertical dimension based on outline
    [minx, maxx, miny, maxy] = get_outline_bbox(board)
    if side == "bottom":
        dim_pts = [Position(miny.aux_min, miny.main), Position(maxy.aux_min, maxy.main)]
        height = minx.main - miny.aux_min - 8
        mirror = True
        tpos = Position(miny.aux_min + height + 1.25, (miny.main + maxy.main) / 2, 90)
    else:
        dim_pts = [Position(miny.aux_max, miny.main), Position(maxy.aux_max, maxy.main)]
        height = maxx.main - miny.aux_max + 8
        mirror = False
        tpos = Position(miny.aux_max + height - 1.25, (miny.main + maxy.main) / 2, 270)

    new_dim_x = Dimension(
        type="orthogonal",
        layer="Dwgs.User",
        pts=[Position(minx.main, minx.aux_max), Position(maxx.main, maxx.aux_max)],
        height=maxy.main - minx.aux_max + 8,
        orientation=0,
        grText=GrText(effects=Effects(font=Font(width=1, height=1, thickness=0.15), justify=Justify(mirror=mirror))),
        format=DimensionFormat(precision=1, suppressZeroes=True),
        style=DimensionStyle(thickness=0.15, arrowLength=1.27, extensionOffset=0.5, extensionHeight=0.58),
    )
    new_dim_y = new_dim_x
    new_dim_y.style.textPositionMode = 3
    new_dim_y.grText.position = tpos
    new_dim_y.pts = dim_pts
    new_dim_y.height = height

    return vertical + rest + [new_dim_x, new_dim_y]


def board_process(brd_path: str, side: str, skip_dim: bool) -> None:
    """Unify edge.cuts thickness, mirror texts, Standardize main dimensions"""
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

    if not skip_dim:
        board.dimensions = standardize_main_dimensions(board, side)

    board.to_file()


def generate_wireframe(
    oname: str,
    filter_args: Dict[str, Any],
    sides: List[str],
    export_layers: List[str],
    kpro: KicadProject,
    ifile: str,
    set_ref: bool,
    skip_dim: bool,
) -> None:
    """Preprocess board and export it to SVG & GBR"""
    output_folder = os.path.join(kpro.fab_dir, "wireframe/")
    os.makedirs(output_folder, exist_ok=True)
    skip_dim = skip_dim or filter_args.get("dimensions", False) is True

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

            board_process(filter_args["outfile"], side, skip_dim)
            # import subprocess

            # subprocess.run(["pcbnew", fp.name])
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
    """Run kicad-cli and do exports to SVG and gerber"""
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
    """Reset footprint value property settings (font, position, visibility, ..)"""
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


class BBoxPoint:
    """Class representing limiting position value, together with related span of other dimension"""

    main: float
    """Position in main direction"""
    aux_min: float
    """Minimal other axis value for main axis == self.main"""
    aux_max: float
    """Maximal other axis value for main axis == self.main"""

    def __init__(self, main: float, aux_min: float = inf, aux_max: float = -inf) -> None:
        self.main = main
        self.aux_min = aux_min
        self.aux_max = aux_max

    def update(self, ismin: bool, main: float, aux: float) -> Self:
        """Compare `(main,aux)` point with limits stored in self, return more extreme value"""
        op = min if ismin else max

        if (ismin and main - self.main > 0.1) or (not ismin and main - self.main < -0.1):
            return self

        if abs(main - self.main) < 0.1:
            self.aux_min = min(aux, self.aux_min)
            self.aux_max = max(aux, self.aux_max)
        else:
            self.aux_min = aux
            self.aux_max = aux

        self.main = op(main, self.main)

        return self


def get_outline_bbox(board: Board) -> List[BBoxPoint]:
    """Returns board outline bbox coordinates together with ranges where board touches bbox"""

    pts = []
    (minx, maxx, miny, maxy) = (BBoxPoint(inf), BBoxPoint(-inf), BBoxPoint(inf), BBoxPoint(-inf))
    for item in board.graphicItems:
        if item.layer != "Edge.Cuts":
            continue
        if hasattr(item, "start"):
            pts.append(item.start)
        if hasattr(item, "end"):
            pts.append(item.end)
        if hasattr(item, "mid"):
            pts.append(item.mid)
        if hasattr(item, "coordinates"):
            pts.append(item.coordinates)

    for p in pts:
        minx = minx.update(True, p.X, p.Y)
        miny = miny.update(True, p.Y, p.X)
        maxx = maxx.update(False, p.X, p.Y)
        maxy = maxy.update(False, p.Y, p.X)
    return [minx, maxx, miny, maxy]


def generate_frame(kpro: KicadProject) -> None:
    """Add graphical rectangle to pcb, that is expanded outline bbox"""

    with NamedTemporaryFile(suffix=".kicad_pcb") as fp:

        filter_args = {"outfile": fp.name, "infile": kpro.pcb_file, "keep_edge": True, "allowed_layers": "Edge.Cuts"}

        log.info("Run PCB filter")
        pcb_filter_run(kpro, **filter_args)
        board = Board.from_file(fp.name)
        border = 60
        [minx, maxx, miny, maxy] = get_outline_bbox(board)
        board.graphicItems.append(
            GrRect(
                Position(minx.main - border, miny.main - border),
                Position(maxx.main + border, maxy.main + border),
                layer="Margin",
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
