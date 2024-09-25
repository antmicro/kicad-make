import argparse
import logging
import os

from kiutils.board import Board
from kiutils.footprint import Footprint
from kiutils.items.fpitems import FpText
from kiutils.items.gritems import GrText
from kiutils.items.brditems import Via

from common.kicad_project import KicadProject
from typing import List, Any, Optional

log = logging.getLogger(__name__)


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("pcb-filter", help="Create *.kicad_pcb ")
    parser.add_argument(
        "-o",
        "--outfile",
        action="store",
        default="filtred.kicad_pcb",
        help="Name of output file (defaults to filtred.kicad_pcb)",
    )
    parser.add_argument(
        "-i",
        "--infile",
        action="store",
        help="Name of input file (defaults to {$PRO_NAME}.kicad_pcb)",
    )
    parser.add_argument(
        "-c",
        "--cascade",
        action="store_true",
        help="If output file exists use it as input, simplifies cascaded calls",
    )
    parser.add_argument(
        "-a",
        "--allow",
        action="store",
        nargs="*",
        help="""Components with matching references will be left untouched
         (mutually exclusive with `--exclude`); 
         eg. `-a J MH SW`""",
    )
    parser.add_argument(
        "-e",
        "--exclude",
        action="store",
        nargs="*",
        help="Components with matching references will be left removed (mutually exclusive with `--allow`)",
    )
    parser.add_argument(
        "-ao",
        "--allow-other",
        action="store",
        nargs="*",
        help="`--allow` filter  used on side oposite to `--side`",
    )
    parser.add_argument(
        "-s",
        "--side",
        choices=["top", "bottom"],
        help="Leave only components from selected layer",
    )
    parser.add_argument(
        "-st",
        "--stackup",
        action="store_true",
        help="Remove stackup table",
    )
    parser.add_argument(
        "-d",
        "--dimensions",
        action="store_true",
        help="Remove dimensions (dimmensions should be added on `User.Drawings` layer)",
    )
    parser.add_argument(
        "-t",
        "--tracks",
        action="store_true",
        help="Remove tracks",
    )
    parser.add_argument(
        "-z",
        "--zones",
        action="store_true",
        help="Remove cooper & keepout zones",
    )
    parser.add_argument(
        "--vias",
        action="store_true",
        help="Remove vias",
    )
    parser.add_argument(
        "-r",
        "--references",
        action="store_true",
        help="Remove footprint references",
    )
    parser.add_argument(
        "-v",
        "--values",
        action="store_true",
        help="Remove footprint values",
    )
    parser.add_argument(
        "-l",
        "--allowed-layers",
        action="store",
        help="Remove all graphic/footprint elements except those on specified layers (leaves knockout text untouched)",
    )
    parser.add_argument(
        "-lf",
        "--allowed-layers-full",
        action="store",
        help="Remove all graphic/footprint elements except those on specified layers (removes also knockout text)",
    )
    parser.set_defaults(func=run)


def run(ki_pro: KicadProject, args: argparse.Namespace) -> None:
    argsf = vars(args)
    argsf = {
        k: v
        for k, v in argsf.items()
        if k
        in [
            "allowed_layers_full",
            "allowed_layers",
            "values",
            "references",
            "vias",
            "zones",
            "tracks",
            "dimensions",
            "stackup",
            "side",
            "allow_other",
            "exclude",
            "allow",
            "cascade",
            "infile",
            "outfile",
        ]
    }
    pcb_filter_run(ki_pro, **argsf)


def pcb_filter_run(
    ki_pro: KicadProject,
    allowed_layers_full: Optional[str] = None,
    allowed_layers: Optional[str] = None,
    values: bool = False,
    references: bool = False,
    vias: bool = False,
    zones: bool = False,
    tracks: bool = False,
    dimensions: bool = False,
    stackup: bool = False,
    side: Optional[str] = None,
    allow_other: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None,
    allow: Optional[List[str]] = None,
    cascade: bool = False,
    infile: Optional[str] = None,
    outfile: str = "filtred.kicad_pcb",
) -> None:
    if not outfile.endswith(".kicad_pcb"):
        outfile += ".kicad_pcb"
    if cascade and os.path.isfile(outfile):
        infile = outfile
    if infile is None:
        infile = ki_pro.pcb_file
    if not len(infile):
        log.error("PCB file was not detected or does not exists")
        return

    log.info("Loading PCB")
    board = Board.from_file(infile)

    if allow is None:
        allow = ["*"]

    if allow_other is None:
        allow_other = []

    if side == "top":
        pass
    elif side == "bottom":
        (allow, allow_other) = (allow_other, allow)
    else:
        (allow, allow_other) = (allow, allow)

    board.footprints = [fp for fp in board.footprints if reference_match(fp, allow, allow_other)]

    if exclude is not None:
        board.footprints = [fp for fp in board.footprints if not reference_match(fp, exclude, exclude)]

    if stackup:
        try:
            stackup_group = [g for g in board.groups if g.name == "group-boardStackUp"][0]
            board.graphicItems = [item for item in board.graphicItems if item.tstamp not in stackup_group.members]
            board.groups = [g for g in board.groups if g.name != "group-boardStackUp"]
        except IndexError:
            pass

    if references or values:
        for fp in board.footprints:
            fp.graphicItems = [g for g in fp.graphicItems if not val_ref_match(g, references, values)]
    full_layers_filter = False
    if allowed_layers_full is not None:
        full_layers_filter = True
        allowed_layers = allowed_layers_full
    if allowed_layers is not None:
        allowed_layers = allowed_layers.replace("User.Comments", "Cmts.User").replace("User.Drawings", "Dwgs.User")

        layers = [lr.strip() for lr in allowed_layers.split(",")]
        board.graphicItems = [
            item for item in board.graphicItems if layer_filter_match(item, layers, full_layers_filter)
        ]
        for fp in board.footprints:
            fp.graphicItems = [item for item in fp.graphicItems if item.layer in layers]

    if dimensions:
        board.dimensions = []

    if zones:
        board.zones = []

    if tracks:
        board.traceItems = [item for item in board.traceItems if isinstance(item, Via)]
    if vias:
        board.traceItems = [item for item in board.traceItems if not isinstance(item, Via)]

    log.info(f"Saving filtred PCB: {outfile}")
    board.to_file(outfile)


def reference_match(fp: Footprint, pat_top: List[str], pat_bottom: List[str]) -> bool:
    if fp.layer == "F.Cu":
        pat = pat_top
    else:
        pat = pat_bottom

    if pat == ["*"]:
        return True

    for item in fp.graphicItems:
        if not isinstance(item, FpText):
            continue
        if item.type != "reference":
            continue
        for p in pat:
            ref = item.text.removeprefix(p)
            if len(ref) == 0 or ref[0].isdecimal():
                return True
        return False
    return False


def val_ref_match(g: Any, references: bool, values: bool) -> bool:
    # g: FpArc | FpCircle | FpCurve | FpLine | FpPoly | FpRect | FpText | FpTextBox
    if not isinstance(g, FpText):
        return False
    if references and g.type == "reference":
        return True
    if values and g.type == "value":
        return True
    return False


def layer_filter_match(g: Any, layers: List[str], full: bool) -> bool:
    # g: GrArc | GrCircle | GrCurve | GrLine | GrPoly | GrRect | GrText | GrTextBox
    if g.layer not in layers:
        if full:
            return False
        if not isinstance(g, GrText):
            return False
        if g.knockout:
            return True
        if g.text.startswith("SHA"):
            return True
        return False
    return True
