import argparse
import json
import logging
import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Any

from askiff.board import Board, Layer
from askiff.common import Effects, Font, Justify, Position, Size
from askiff.common_pcb import BoardSide

from common.kicad_project import KicadProject
from common.kmake_helper import run_kicad_cli

from .pcb_filter import pcb_filter_run

log = logging.getLogger(__name__)

# (name, filter_args, side)
PRESETS = [
    (
        "simple",
        dict(
            stackup=True,
            dimensions=True,
            references=True,
            values=True,
            std_edge=True,
            std_graphics=True,
            ref_filter="-M-A-N-REF**",
            allowed_layers="User.9,Edge.Cuts",
            mirror_bottom=True,
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
            std_edge=True,
            std_graphics=True,
            ref_filter="+J+MH+H+MP",
            ref_filter_other="+MH+H+MP",
            allowed_layers="User.9,Edge.Cuts",
            mirror_bottom=True,
        ),
        ["top", "bottom", ""],
        ["User.9,Edge.Cuts,User.Drawings", "User.9,Edge.Cuts,User.6", "User.9,Edge.Cuts,User.7"],
    ),
    (
        "descriptions",
        dict(
            stackup=True,
            references=True,
            dimensions=True,
            values=True,
            std_edge=True,
            std_graphics=True,
            ref_filter="+J+MH+H+MP+SW+TP+D+S",
            allowed_layers="User.9,Edge.Cuts,User.Comments,User.Eco1,User.Eco2",
            mirror_bottom=True,
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
            std_edge=True,
            std_graphics=True,
            ref_filter="-TP-MP-M-A-N-REF**",
            allowed_layers="User.9,Edge.Cuts,F.SilkS,B.SilkS",
        ),
        ["top", "bottom"],
        "User.9,Edge.Cuts,$side.Fab,$side.Paste".split(","),
    ),
    (
        "margin_frame",
        dict(std_edge=True, ref_filter="-REF", generate_frame=True),
        [""],
        ["Margin"],
    ),
    (
        "first_pads_only",
        dict(
            stackup=True,
            dimensions=True,
            vias=True,
            zones=True,
            std_edge=True,
            tracks=True,
            ref_filter="-TP-MP-SP-H-N-REF**",
            allowed_layers_full="Edge.Cuts",
            first_pads_only=True,
        ),
        ["top", "bottom"],
        ["$side.Cu"],
    ),
]


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
        choices=["simple", "dimensions", "descriptions", "assembly_drawing", "margin_frame", "first_pads_only"],
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
        "-f",
        "--pcb-filter-args",
        type=json.loads,
        default={},
        help="""Additional arguments to be passed to pcb-filter;
        (overrides argument value from preset, unless `--pcb-filter-args-append` specified)
        eg. `-f '{"allowed_layers":"+J+D-D1"}'` """,
    )
    parser.add_argument(
        "-a",
        "--pcb-filter-args-append",
        action="store_true",
        help="""Lists/strings, that are passed to pcb-filter (`pcb-filter-args`, `ref-filter`, `ref-filter-other`) 
        will be appended to ones defined in preset""",
    )
    parser.add_argument(
        "-x",
        "--ref-filter",
        action="store",
        help="""Argument passed to pcb-filter: Pattern based component filter
         eg. `-x "+J+D-D1"` - remove components other than connectors(J) and diodes(D), diode D1 will also be removed,
         eg. `-x="-J-D+D1"` - remove connectors(J) and diodes(D), other components and diode D1 will left untouched
         (note `=` when first character is `-`)
         """,
    )
    parser.add_argument(
        "-xo",
        "--ref-filter-other",
        action="store",
        help="Argument passed to pcb-filter: `--ref-filter` filter  used on side opposite to `--side`",
    )
    parser.add_argument("--svg", action="store_true", help="Output SVG")
    parser.add_argument("--gerber", action="store_true", help="Output Gerber")
    parser.set_defaults(func=run)


def run(pro: KicadProject, args: argparse.Namespace) -> None:
    if args.input is None and pro.pcb_root:
        args.input = pro.pcb_root.fs_path
    if not args.input or not Path(args.input).exists():
        log.error("PCB file was not detected or does not exists")
        return

    if not args.svg and not args.gerber:
        args.svg, args.gerber = True, True

    if args.reset:
        log.info("Loading PCB")
        board = Board.from_file(Path(args.input))
        log.info("Reseting wireframes layer")

        for footprint in board.footprints:
            log.debug(f"Processing footprint {footprint.path}")

            outline_items = [item for item in footprint.graphic_items if item.layer in {Layer.USER(9), Layer.USER(8)}]

            for item in outline_items:
                item.layer = Layer.USER(9)

        log.info("Finished changing layer of outline items for all footprints")
        log.info("Saving PCB")
        board.to_file()
        return

    for preset in PRESETS:
        if preset[0] == args.preset:
            break
    else:
        preset = (
            args.input.removesuffix(".kicad_pcb") + "_wireframe",
            dict(allowed_layers="User.9,Edge.Cuts"),
            ["top", "bottom"],
            ["User.9,Edge.Cuts"],
        )

    if args.pcb_filter_args_append:

        def append_dict_val(key: str) -> None:
            if pres := preset[1].get(key, None):
                args.pcb_filter_args[key] = pres + args.pcb_filter_args.get(key, "")

        if args.ref_filter:
            args.pcb_filter_args["ref_filter"] = args.ref_filter
        if args.ref_filter_other:
            args.pcb_filter_args["ref_filter_other"] = args.ref_filter_other

        append_dict_val("ref_filter")
        append_dict_val("ref_filter_other")
        append_dict_val("allowed_layers")
        append_dict_val("allowed_layers_full")
        preset[1].update(args.pcb_filter_args)
    else:
        preset[1].update(args.pcb_filter_args)

        if args.ref_filter:
            preset[1].update({"ref_filter": args.ref_filter})
        if args.ref_filter_other:
            preset[1].update({"ref_filter_other": args.ref_filter_other})

    generate_wireframe(preset[0], preset[1], preset[2], preset[3], pro, args)


def generate_wireframe(
    oname: str,
    filter_args: dict[str, Any],
    sides: list[str],
    export_layers: list[str],
    pro: KicadProject,
    args: argparse.Namespace,
) -> None:
    """Preprocess board and export it to SVG & GBR"""
    output_folder = pro.fab_dir / "wireframe"
    output_folder.mkdir(parents=True, exist_ok=True)

    for side in sides:
        with NamedTemporaryFile(suffix=".kicad_pcb", delete=not args.debug) as fp:
            oname_side = f"{oname}_{side}" if side != "" else oname

            filter_args["outfile"] = fp.name
            filter_args["infile"] = args.input
            filter_args["side"] = side

            log.info("Run PCB filter")
            pcb_filter_run(pro, **filter_args)

            if args.set_ref:
                reset_footprint_val_props(fp.name)

            for layer in export_layers:
                slayer = layer.split(",")
                slayer = [substitute_layer_vars(sl, side) for sl in slayer]
                layer = ",".join(slayer)

                if len(export_layers) == 1:
                    oname_side_l = oname_side
                else:
                    oname_side_l = oname_side + "_" + layer.split(",")[-1].replace(".", "_")

                if args.svg:
                    export_svg(fp.name, output_folder, oname_side_l, layer, side)
                if args.gerber:
                    export_gerber(fp.name, output_folder, oname_side_l, layer)


def export_svg(ifile: str, output_folder: Path, oname_side_l: str, layer: str, side: str) -> None:
    """Run kicad-cli and do exports to SVG"""
    # SVG
    outfile = output_folder / ("wireframe_" + oname_side_l + ".svg")
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
        "--crossout-DNP-footprints-on-fab-layers",
        "--page-size-mode",
        "2",
        "--drill-shape-opt",
        "2",  # this prints black filled circle for each non-via hole
        "--mode-single",
    ]
    if side == "bottom":
        svg_export_cli_command.append("--mirror")

    run_kicad_cli(svg_export_cli_command, True)

    svg = outfile.read_text()
    svg = svg.replace("<circle ", '<circle fill="none" stroke="#000000" stroke-width="0.05" stroke-opacity="1" ')
    outfile.write_text(svg)


def export_gerber(ifile: str, output_folder: Path, oname_side_l: str, layer: str) -> None:
    """Run kicad-cli and do exports to gerber"""
    outfile = output_folder / ("wireframe_" + oname_side_l + ".gbr")
    base_layer, _, common_layers = layer.partition(",")
    log.info(f"Exporting {layer} gerber to {outfile}")

    with TemporaryDirectory() as tempdir:
        gerber_export_cli_command = [
            "pcb",
            "export",
            "gerbers",
            ifile,
            "-o",
            tempdir,
            "--precision",
            "6",
            "--no-protel-ext",
            "--crossout-DNP-footprints-on-fab-layers",
            "--layers",
            base_layer,
            "--common-layers",
            common_layers,
        ]
        run_kicad_cli(gerber_export_cli_command, True)
        shutil.move(next(Path(tempdir).glob("*.gbr")), outfile)


def reset_footprint_val_props(file: str) -> None:
    """Reset footprint value property settings (font, position, visibility, ..)"""
    log.info("Reset footprint reference properties")

    board = Board.from_file(Path(file))
    for fp in board.footprints:
        ref = fp.properties.ref
        ref.hide = False
        ref.effects = Effects(Font(None, Size(0.35, 0.35), 0.07), Justify(), unlocked=None)
        ref.position = Position(angle=fp.position.angle)
        ref.layer = Layer.FAB_F if fp.side == BoardSide.FRONT else Layer.FAB_B
    board.to_file()


def substitute_layer_vars(layer: str, side: str) -> str:
    """Substitute `$side` and `$numside` in string"""
    if side == "top":
        layer = layer.replace("$side", "F")
        layer = layer.replace("$numside", "1")
    elif side == "bottom":
        layer = layer.replace("$side", "B")
        layer = layer.replace("$numside", "2")
    else:  # side==""
        layer = layer.replace("$side", "F") + "," + layer.replace("$side", "B") if "$side" in layer else layer
        layer = layer.replace("$numside", "1") + "," + layer.replace("$numside", "2") if "$numside" in layer else layer
    return layer
