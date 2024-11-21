import argparse
import logging
import os
import re

from kiutils.board import Board
from kiutils.footprint import Footprint
from kiutils.items.gritems import GrText, GrLine, GrArc
from kiutils.items.brditems import Via
from kiutils.items.fpitems import FpLine, FpArc
from kiutils.items.common import Position
from kiutils.items.common import Effects, Stroke, Font, Justify
from kiutils.items.fpitems import FpText
from kiutils.items.gritems import GrCircle, GrPoly, GrRect
from kiutils.items.dimensions import Dimension, DimensionFormat, DimensionStyle

from common.kicad_project import KicadProject
from common.kmake_helper import get_property
from typing import List, Any, Optional, Self
from copy import deepcopy

from math import sin, cos, radians, inf

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
        "-x",
        "--ref-filter",
        action="store",
        help="""Pattern based component filter
         eg. `-x "+J+D-D1"` - remove components other than connectors(J) and diodes(D), diode D1 will also be removed,
         eg. `-x="-J-D+D1"` - remove connectors(J) and diodes(D), other components and diode D1 will left untouched
         (note `=` when first character is `-`)
         """,
    )
    parser.add_argument(
        "-xo",
        "--ref-filter-other",
        action="store",
        help="`--ref-filter` filter  used on side opposite to `--side`",
    )
    parser.add_argument(
        "-s",
        "--side",
        choices=["top", "bottom"],
        help="Leave only components from selected layer",
    )
    parser.add_argument(
        "--std-edge",
        action="store_true",
        help="Copy edge.cuts from footprints to pcb; Set all Edge.Cuts graphics thickness",
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
    parser.add_argument(
        "--generate-frame",
        action="store_true",
        help="""Generate output that is rectangle created from board outline b-box expanded by 60mm""",
    )
    parser.add_argument(
        "--std-dimension",
        action="store_true",
        help="Standardize/add main dimensions",
    )
    parser.add_argument(
        "--mirror-bottom",
        action="store_true",
        help="Mirror text if side is bottom",
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
            "std_edge",
            "ref_filter",
            "ref_filter_other",
            "cascade",
            "infile",
            "outfile",
            "generate_frame",
            "mirror_bottom",
            "std_dimension",
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
    std_edge: bool = False,
    ref_filter: Optional[str] = None,
    ref_filter_other: Optional[str] = None,
    cascade: bool = False,
    infile: Optional[str] = None,
    outfile: str = "filtred.kicad_pcb",
    generate_frame: bool = False,
    mirror_bottom: bool = False,
    std_dimension: bool = False,
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

    if side is None:
        side = ""

    if std_edge:
        copy_edge_from_footprint(board)
        unify_edge_cuts(board)

    filter_main = None if ref_filter is None else RefFilter(ref_filter)
    filter_other = None if ref_filter_other is None else RefFilter(ref_filter_other)

    board.footprints = [fp for fp in board.footprints if reference_match(fp, side, filter_main, filter_other)]

    if stackup:
        try:
            stackup_group = [g for g in board.groups if g.name == "group-boardStackUp"][0]
            board.graphicItems = [item for item in board.graphicItems if item.uuid not in stackup_group.members]
            board.groups = [g for g in board.groups if g.name != "group-boardStackUp"]
        except IndexError:
            pass

    for fp in board.footprints:
        for prop in fp.properties:
            if references:
                hide_property_if_named(prop, property_name="Reference")
            if values:
                hide_property_if_named(prop, property_name="Value")

    full_layers_filter = False
    if allowed_layers_full is not None:
        full_layers_filter = True
        allowed_layers = allowed_layers_full
    if allowed_layers is not None:
        allowed_layers = (
            allowed_layers.replace("User.Comments", "Cmts.User")
            .replace("User.Drawings", "Dwgs.User")
            .replace("F.Silkscreen", "F.SilkS")
            .replace("B.Silkscreen", "B.SilkS")
            .replace("F.Adhesive", "F.Adhes")
            .replace("B.Adhesive", "B.Adhes")
            .replace("User.Eco1", "Eco1.User")
            .replace("User.Eco2", "Eco2.User")
            .replace("F.Courtyard", "F.CrtYd")
            .replace("B.Courtyard", "B.CrtYd")
        )

        layers = [lr.strip() for lr in allowed_layers.split(",")]
        board.graphicItems = [
            item for item in board.graphicItems if layer_filter_match(item, layers, full_layers_filter)
        ]
        for fp in board.footprints:
            fp.graphicItems = [item for item in fp.graphicItems if item.layer in layers]
            for prop in fp.properties:
                if prop.layer in layers:
                    continue
                prop.hide = True

    if dimensions:
        board.dimensions = []

    if zones:
        board.zones = []

    if tracks:
        board.traceItems = [item for item in board.traceItems if isinstance(item, Via)]
    if vias:
        board.traceItems = [item for item in board.traceItems if not isinstance(item, Via)]

    if side == "bottom":
        board = mirror_texts(board)

    if generate_frame or std_dimension:
        bbox_limits = get_outline_bbox(board)

    if generate_frame:
        generate_frame_f(board, bbox_limits)

    if std_dimension:
        board.dimensions = remove_main_dimensions(board)
        board.dimensions += add_main_dimensions(side, bbox_limits)

    log.info(f"Saving filtred PCB: {outfile}")
    board.to_file(outfile)


def copy_edge_from_footprint(board: Board) -> None:
    """Copies all Edge.Cuts graphics found in footprints to board level"""
    for fp in board.footprints:
        angle = radians(-fp.position.angle if fp.position.angle is not None else 0)
        sina, cosa = sin(angle), cos(angle)
        tx, ty = fp.position.X, fp.position.Y

        def glob_pos(pos: Position) -> Position:
            return Position(X=tx + pos.X * cosa - pos.Y * sina, Y=ty + pos.X * sina + pos.Y * cosa)  # noqa: B023

        for item in fp.graphicItems:
            if item.layer != "Edge.Cuts":
                continue
            if isinstance(item, FpLine):
                board.graphicItems.append(
                    GrLine(start=glob_pos(item.start), end=glob_pos(item.end), layer="Edge.Cuts", stroke=item.stroke)
                )
            if isinstance(item, FpArc):
                board.graphicItems.append(
                    GrArc(
                        start=glob_pos(item.start),
                        mid=glob_pos(item.mid),
                        end=glob_pos(item.end),
                        layer="Edge.Cuts",
                        stroke=item.stroke,
                    )
                )


def unify_edge_cuts(board: Board) -> None:
    """Unify thickness of graphics on Edge.Cuts layer"""

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


class RefFilter:
    def __init__(self, filter_pat: str) -> None:
        pat = re.split("([+-][0-9A-Za-z]+)", filter_pat)[1::2]
        pat_dict = {}

        for p in pat:  # this will simplify eg. `+M-M` to `-M`
            pat_dict.update({p[1:]: p[0]})

        def typefilt(char: str) -> List[str]:
            return [p for (p, mode) in pat_dict.items() if mode == char]

        self.mode_additive = filter_pat[0] == "+"
        self.pat_add = typefilt("+")
        self.pat_rem = typefilt("-")


def check_primary_side(fp: Footprint, side: str) -> bool:
    if [fp.layer, side] in [["F.Cu", "top"], ["B.Cu", "bottom"]] or side == "":
        return True

    front, back = False, False
    for pad in fp.pads:
        front = front or "F.Cu" in pad.layers
        back = back or "B.Cu" in pad.layers
    return front and back


def reference_match(fp: Footprint, side: str, filt: Optional[RefFilter], filt_other: Optional[RefFilter]) -> bool:
    if check_primary_side(fp, side):
        if filt is None:
            return True
    else:
        filt = filt_other
        if filt is None:
            return False

    # Extract prefix from reference
    ref = get_property(fp, "Reference").strip()
    ref_type = ref.rstrip("0123456789?*")

    # Compare prefix with selected pattern
    if filt.mode_additive:
        return (ref_type in filt.pat_add and ref not in filt.pat_rem) or ref in filt.pat_add
    return (ref_type not in filt.pat_rem and ref not in filt.pat_rem) or ref in filt.pat_add


def hide_property_if_named(prop: Any, property_name: str) -> None:
    if prop.key == property_name:
        prop.hide = True


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


def remove_main_dimensions(board: Board) -> List[Dimension]:
    """Remove largest dimensions (one horizontal, one vertical)"""
    vertical = []
    horizontal = []
    rest = []
    (maxlen_x, maxlen_y) = (0, 0)
    # remove largest dimensions
    for d in board.dimensions:
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
    return vertical + horizontal + rest


def add_main_dimensions(side: str, bbox_limits: List[BBoxPoint]) -> List[Dimension]:
    """Add new standardized dimensions (one horizontal, one vertical)
    (new dimensions will be on right board side for top and on left for bottom w text mirrored)"""

    # Add new vertical dimension based on outline
    [minx, maxx, miny, maxy] = bbox_limits
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
    new_dim_y = deepcopy(new_dim_x)
    new_dim_y.style.textPositionMode = 3
    new_dim_y.orientation = 1
    new_dim_y.grText.position = tpos
    new_dim_y.pts = dim_pts
    new_dim_y.height = height
    return [new_dim_x, new_dim_y]


def generate_frame_f(board: Board, bbox_limits: List[BBoxPoint]) -> None:
    """Add graphical rectangle to pcb, that is expanded outline bbox"""
    border = 60
    [minx, maxx, miny, maxy] = bbox_limits
    board.graphicItems.append(
        GrRect(
            Position(minx.main - border, miny.main - border),
            Position(maxx.main + border, maxy.main + border),
            layer="Margin",
        )
    )
