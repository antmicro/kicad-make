import math
import argparse
import logging
import os
import re

from askiff.kistruct.board import Board, Via, LayerDef, Layer
from askiff.kistruct.footprint import Footprint
from askiff.kistruct.gritems import (
    GrItem,
    GrText,
    GrLine,
    GrLineFp,
    GrLinePCB,
    GrArcPCB,
    GrArcFp,
    GrTextPCB,
    GrTextPCBBase,
    GrTextFp,
    GrCirclePCB,
    GrCircle,
    GrCircleFp,
    GrPolyPCB,
    GrPoly,
    GrPolyFp,
    GrRectPCB,
    GrRect,
    GrRectFp,
    Dimension,
    DimensionStyle,
    DimensionValueFormat,
    LayerSet,
)
from askiff.kistruct.common import Position, Effects, Stroke
from askiff.kistruct.common_pcb import BoardSide

# from kiutils.items.brditems import Via, LayerList
# from kiutils.items.fpitems import FpLine, FpArc
# from kiutils.items.common import Position, PositionStart, PositionMid, PositionEnd

# from kiutils.items.dimensions import Dimension, DimensionFormat, DimensionStyle

from common.kicad_project import KicadProject
from common.kmake_helper import get_property
from typing import List, Any, Optional, Set
from copy import deepcopy
from pathlib import Path

from math import inf

log = logging.getLogger(__name__)


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("pcb-filter", help="Create *.kicad_pcb ")
    parser.add_argument(
        "-o",
        "--outfile",
        action="store",
        default="filtered.kicad_pcb",
        help="Name of output file (defaults to filtered.kicad_pcb)",
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
    parser.add_argument(
        "--first-pads-only",
        action="store_true",
        help="Remove all pads from footprints except the first one",
    )
    parser.add_argument(
        "--std-graphics",
        action="store_true",
        help="Standardize graphics/text size/thickness",
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
            "first_pads_only",
            "std_graphics",
        ]
    }
    pcb_filter_run(ki_pro, **argsf)


def keep_first_pads_only(source_pcb: Board) -> None:
    pad_one_markings = ["1", "A1"]
    for footprint in source_pcb.footprints:
        footprint.pads = [pad for pad in footprint.pads if pad.number in pad_one_markings]


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
    outfile: str = "filtered.kicad_pcb",
    generate_frame: bool = False,
    mirror_bottom: bool = False,
    std_dimension: bool = False,
    first_pads_only: bool = False,
    std_graphics: bool = False,
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
    board = Board.from_file(Path(infile))

    if not side:
        side = ""
    elif side == "top":
        side = BoardSide.FRONT
    elif side == "bottom":
        side == BoardSide.BACK
    else:
        raise AttributeError("Side must be either 'top' or 'bottom'")

    if std_edge:
        # has to be before any footprint removal
        copy_edge_from_footprint(board)

    filter_main = None if ref_filter is None else RefFilter(ref_filter)
    filter_other = None if ref_filter_other is None else RefFilter(ref_filter_other)

    board.footprints = [fp for fp in board.footprints if reference_match(fp, side, filter_main, filter_other)]

    if stackup:  # doesn't work in vanilla kmake as well
        try:
            stackup_group = [g for g in board.groups if g.name == "group-boardStackUp"][0]
            board.graphicItems = [item for item in board.graphic_items if item.uuid not in stackup_group.members]
            board.groups = [g for g in board.groups if g.name != "group-boardStackUp"]
        except IndexError:
            pass

    if references or values:
        for fp in board.footprints:
            if references:
                fp.properties.get("Reference").hide = True
            if values:
                fp.properties.get("Value").hide = True

    layer_filtration(board, allowed_layers, allowed_layers_full)

    if dimensions:
        board.dimensions = []

    if zones:
        board.zones = []

    if tracks:
        board.traces = [item for item in board.traces if isinstance(item, Via)]

    if vias:
        board.traces = [item for item in board.traces if not isinstance(item, Via)]

    if generate_frame or std_dimension or std_graphics:
        bbox_limits = get_outline_bbox(board)

    if generate_frame:
        generate_frame_f(board, bbox_limits)

    if std_dimension:
        board.dimensions = remove_main_dimensions(board)
        board.dimensions += add_main_dimensions(side, bbox_limits)

    if std_graphics:
        unify_graphics(board, bbox_limits)

    if side == "bottom" and mirror_bottom:
        board = mirror_texts(board)

    if first_pads_only:
        keep_first_pads_only(board)

    log.info(f"Saving filtered PCB: {outfile}")
    board.to_file(Path(outfile))
    pcb_file_org = ki_pro.pcb_file
    ki_pro.pcb_file = outfile
    ki_pro.pcb_file = pcb_file_org


def layer_filtration(board: Board, allowed_layers: Optional[str], allowed_layers_full: Optional[str]) -> None:
    """Filter board graphics leaving only these on whitelisted layers"""
    full_layers_filter = False

    if allowed_layers_full:
        full_layers_filter = True
        allowed_layers = allowed_layers_full

    if allowed_layers:
        layers = std_layer_names(allowed_layers)
        board.graphic_items = [
            item for item in board.graphic_items if layer_filter_match(item, layers, full_layers_filter)
        ]
        layers = std_layer_names(allowed_layers)
        for fp in board.footprints:
            fp.graphic_items = [item for item in fp.graphic_items if item.layers in layers]
            for prop in fp.properties:
                if prop.layer in layers:
                    continue
                prop.hide = True


def std_layer_names(layers_str: str) -> set[Layer]:
    """Normalize layer names & split into list"""
    layers_str = (
        layers_str.replace("User.Comments", "Cmts.User")
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
    layers_list = [lr.strip() for lr in layers_str.split(",")]
    return {Layer(layer) for layer in layers_list}


def copy_edge_from_footprint(board: Board) -> None:
    """Copies all Edge.Cuts graphics found in footprints to board level"""
    for fp in board.footprints:
        for item in fp.graphic_items:

            if item.layers != {Layer.EDGE}:
                continue

            board.graphic_items.append(item.to_board_shape(fp.position))  # doesn't work, probably in newest askiff


def unify_style_graphics(board: Board, layers: Set[str], width: float) -> None:
    """Set thickness of graphics on specified layer"""
    # set all lines to same width
    # bgi = []
    for g in board.graphic_items:
        if isinstance(g, GrItem) and g.layer in layers:
            if g.stroke is None:
                g.stroke = Stroke()
            g.stroke.width = width
        # bgi.append(g)
    # board.graphicItems = bgi


class RefFilter:
    def __init__(self, filter_pat: str) -> None:
        if filter_pat == "":
            self.mode_additive = True
            self.pat_add = []
            return
        pat = re.split("([+-][0-9A-Za-z]+)", filter_pat)[1::2]
        pat_dict = {}

        for p in pat:  # this will simplify eg. `+M-M` to `-M`
            pat_dict.update({p[1:]: p[0]})

        def typefilt(char: str) -> List[str]:
            return [p for (p, mode) in pat_dict.items() if mode == char]

        self.mode_additive = filter_pat[0] == "+"
        self.pat_add = typefilt("+")
        self.pat_rem = typefilt("-")


def check_primary_side(fp: Footprint, side: Optional[BoardSide]) -> bool:
    # double check: this function seems to work fine even when wrong side parameter is passed?
    if fp.side == side or not side:
        return True

    front, back = False, False
    for pad in fp.pads:
        # todo: check after pulling newest askiff, there's a bug
        front = front or Layer.CU_F in pad.layers
        back = back or Layer.CU_B in pad.layers
    return front and back


def reference_match(fp: Footprint, side: BoardSide, filt: Optional[RefFilter], filt_other: Optional[RefFilter]) -> bool:
    if check_primary_side(fp, side):
        if filt is None:
            return True
    else:
        filt = filt_other
        if not filt:
            return False

    # Extract prefix from reference,
    ref = fp.properties.ref.value
    ref_type = fp.properties.ref.value.rstrip("0123456789?*")

    # Compare prefix with selected pattern
    if filt.mode_additive:
        return (ref_type in filt.pat_add and ref not in filt.pat_rem) or ref in filt.pat_add
    return (ref_type not in filt.pat_rem and ref not in filt.pat_rem) or ref in filt.pat_add


def hide_property_if_named(prop: Any, property_name: str) -> None:
    if prop.key == property_name:
        prop.hide = True


def layer_filter_match(g: Any, layers: set[Layer], full: bool) -> bool:
    # g: GrArc | GrCircle | GrCurve | GrLine | GrPoly | GrRect | GrText | GrTextBox
    if g.layers not in layers:
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
        if isinstance(g, GrTextFp):
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
    board.graphic_items = brdgi

    brdd = []
    for d in board.dimensions:
        if d.grText is None:
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

    def update(self, ismin: bool, main: float, aux: float) -> "BBoxPoint":
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
    for item in board.graphic_items:
        if item.layers != {Layer.EDGE}:
            continue
        if hasattr(item, "start"):
            pts.append(item.start)
        if hasattr(item, "end"):
            pts.append(item.end)
        if hasattr(item, "mid"):
            pts.append(item.mid)
        if hasattr(item, "pts"):
            pts.extend(item.pts)

    for p in pts:
        minx = minx.update(True, p.x, p.y)
        miny = miny.update(True, p.y, p.x)
        maxx = maxx.update(False, p.x, p.y)
        maxy = maxy.update(False, p.y, p.x)
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
    vertical = [d for d in vertical if maxlen_y - abs(d.pts[0].y - d.pts[1].y) > 0.01]
    horizontal = [d for d in horizontal if maxlen_x - abs(d.pts[0].x - d.pts[1].x) > 0.01]
    return vertical + horizontal + rest


def add_main_dimensions(side: str, bbox_limits: List[BBoxPoint]) -> List[Dimension]:
    """Add new standardized dimensions (one horizontal, one vertical)
    (new dimensions will be on right board side for top and on left for bottom w text mirrored)"""

    # Add new vertical dimension based on outline
    [minx, maxx, miny, maxy] = bbox_limits
    if side == "bottom":
        dim_pts = [Position(miny.aux_min, miny.main), Position(maxy.aux_min, maxy.main)]
        height = minx.main - miny.aux_min - 8
    else:
        dim_pts = [Position(miny.aux_max, miny.main), Position(maxy.aux_max, maxy.main)]
        height = maxx.main - miny.aux_max + 8

    new_dim_x = Dimension(
        type="orthogonal",
        layer="Dwgs.User",
        pts=[Position(minx.main, minx.aux_max), Position(maxx.main, maxx.aux_max)],
        height=maxy.main - minx.aux_max + 8,
        orientation=0,
    )
    new_dim_y = deepcopy(new_dim_x)
    new_dim_y.orientation = 1
    new_dim_y.pts = dim_pts
    new_dim_y.height = height
    return [new_dim_x, new_dim_y]


def generate_frame_f(board: Board, bbox_limits: List[BBoxPoint]) -> None:
    """Add graphical rectangle to pcb, that is expanded outline bbox"""
    border = 60
    [minx, maxx, miny, maxy] = bbox_limits
    board.graphic_items.append(
        GrRectPCB(
            Position(minx.main - border, miny.main - border),
            Position(maxx.main + border, maxy.main + border),
            layers=LayerSet({Layer.MARGIN}),
        )
    )
    print(
        GrRectPCB(
            Position(minx.main - border, miny.main - border),
            Position(maxx.main + border, maxy.main + border),
            layers=LayerSet({Layer.MARGIN}),
        )
    )


def std_grtext(text: GrText, scale: float) -> float:
    if text.effects is None:
        text.effects = Effects()
    old_thick = text.effects.font.thickness if text.effects.font.thickness else 0
    old_height = old_thick + text.effects.font.height
    text.effects.font.width = 2 * scale
    text.effects.font.height = 2 * scale
    text.effects.font.thickness = 0.2 * scale
    text.effects.font.bold = False
    text.effects.font.face = None
    return text.effects.font.thickness + text.effects.font.height - old_height


def unify_style_text(board: Board, layers: Set[str], scale: float) -> None:
    """Set text style on specified layer"""
    # bgi = []
    for g in board.graphic_items:
        if isinstance(g, GrText) and g.layer in layers:
            std_grtext(g, scale)
        # bgi.append(g)
    # board.graphic_items = bgi


def get_aligned_dim_center(dim: Dimension) -> tuple[float, float]:
    """Gets point that is the center (middle of main dimension line) of dimension"""
    x1, y1 = dim.pts[0].X, dim.pts[0].Y
    x2, y2 = dim.pts[1].X, dim.pts[1].Y

    # Midpoint
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2

    # Direction vector
    dx, dy = x2 - x1, y2 - y1

    # Orthogonal vector (rotate 90 degrees)
    ox, oy = -dy, dx

    # Normalize & scale
    mag = math.hypot(ox, oy)
    ox, oy = ox * dim.height / mag, oy * dim.height / mag

    # Endpoint of the orthogonal vector
    return mx + ox, my + oy


def unify_style_dimensions(board: Board, layers: Set[str], scale: float, bbox: list[float]) -> None:
    """Set text style on specified layer"""
    [minx, maxx, miny, maxy] = bbox

    # set all lines to same width
    bdi = []

    # qtr_dim is { layer : [ [dim_pos1, dim_pos2, ..] [..] [..] [..] ] }
    # 4 quarters left, right, top, bottom
    qtr_dim: dict[str, list[list[float]]] = {}

    # dim.uuid: (dim_quarter, dim_pos)
    dim_qtr_pos: dict[str, tuple[int, float]] = {}

    for d in board.dimensions:
        if d.type == "aligned":
            d_center = get_aligned_dim_center(d)
        elif d.type == "orthogonal":
            if d.orientation == 0:
                d_center = (d.pts[0].x + d.pts[1].X) * 0.5, d.pts[0].y + d.height
            else:
                d_center = d.pts[0].x + d.height, (d.pts[0].y + d.pts[1].y) * 0.5

        else:
            continue

        if d_center[0] < minx:
            qtr = 0
        elif d_center[0] > maxx:
            qtr = 1
        elif d_center[1] < miny:
            qtr = 2
        elif d_center[1] > maxy:
            qtr = 3
        else:
            # dimension inside board outline
            continue

        pos = d_center[qtr // 2]
        qd = qtr_dim.setdefault(d.layer, [[], [], [], []])
        similar_pos = [dim for dim in qd[qtr] if abs(dim - pos) < 0.25]
        if similar_pos:
            dim_qtr_pos[d.uuid] = (qtr, similar_pos[0])
        else:
            qd[qtr].append(pos)
            dim_qtr_pos[d.uuid] = (qtr, pos)

    for layer in qtr_dim:
        qtr_dim[layer][0].sort(reverse=True)
        qtr_dim[layer][1].sort()
        qtr_dim[layer][2].sort(reverse=True)
        qtr_dim[layer][3].sort()

    for d in board.dimensions:
        if d.layer in layers:
            d.format = DimensionValueFormat(
                precision=1,  # one fraction digit
                units=2,  # millimeters
                unitsFormat=0,  # bare value, no unit suffix
                suppressZeroes=False,
                overrideValue=d.format.overrideValue if d.format else None,
            )

            arrow_len = 1
            try:
                if d.type in ["center", "leader", "radial"]:
                    arrow_len = d.style.arrowLength
                else:
                    length = ((d.pts[0].X - d.pts[1].X) ** 2 + (d.pts[0].Y - d.pts[1].Y) ** 2) ** 0.5
                    arrow_len = min(1, round(length / 2, 2))
            except Exception:
                pass

            d.style = DimensionStyle(
                extensionOffset=d.style.extensionOffset,
                extensionHeight=d.style.extensionHeight,
                thickness=0.1,
                arrowLength=arrow_len,
                textPositionMode=0,
                # """The ``textPositionMode`` token defines the position mode of the dimension text. Valid position
                # modes are as follows:
                # - 0: Text is outside the dimension line
                # - 1: Text is in line with the dimension line
                # - 2: Text has been manually placed by the user"""
                arrowDirection=d.style.arrowDirection,  # inward/outward
                textFrame=d.style.textFrame,
                keepTextAligned=True,
            )
            if d.grText is None:
                d.grText = GrText()
            height_change = std_grtext(d.grText, scale)

            # Extend dimensions to reduce overlaps due to text scaling
            if d.uuid in dim_qtr_pos:
                qtr, pos = dim_qtr_pos[d.uuid]
                dim_idx = qtr_dim[d.layer][qtr].index(pos)
                # additional offset for dimmesniosn on the right and bottom of board
                edge_overlap_cor = 1 if qtr in [1, 3] else 0
                d.height += math.copysign((dim_idx + edge_overlap_cor) * height_change * 1.66, d.height)

        bdi.append(d)
    board.dimensions = bdi


def unify_graphics(board: Board, bbox_limits: List[BBoxPoint]) -> None:
    """Unify graphics font/thickness"""
    simple_bbox = [b.main for b in bbox_limits]
    board_width = simple_bbox[1] - simple_bbox[0]
    if board_width <= 15:
        scale = 0.25
    elif board_width <= 30:
        scale = 0.5
    elif board_width <= 120:
        scale = 1
    else:
        scale = 2
    unify_style_graphics(board, set(["Edge.Cuts"]), 0.2)
    layers = set(["Eco1.User", "Eco2.User", "Cmts.User", "Dwgs.User"] + [f"User.{i}" for i in range(20)])
    unify_style_graphics(board, layers, 0.1)
    unify_style_graphics(board, set(["User.9"]), 0.02)
    unify_style_text(board, layers, scale)
    unify_style_dimensions(board, layers, scale, simple_bbox)
