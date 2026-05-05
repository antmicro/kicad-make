from __future__ import annotations

import argparse
import logging
import math
import re
from math import inf
from pathlib import Path

from askiff.board import Board, Layer, Via
from askiff.common import BBox, Effects, Justify, JustifyH, Position, Stroke
from askiff.common_pcb import BaseLayer, BoardSide, LayerSet, LayerUser
from askiff.footprint import Footprint
from askiff.fp_pad import PadEdgeConnector, PadSMD
from askiff.gritems import (
    Dimension,
    DimensionAligned,
    DimensionCenter,
    DimensionLeader,
    DimensionOrthogonal,
    DimensionOrthogonalOrientation,
    DimensionRadial,
    DimensionStyle,
    DimensionTextPosition,
    DimensionUnit,
    DimensionUnitStyle,
    DimensionValueFormat,
    GrItemPCB,
    GrRectPCB,
    GrShapeFp,
    GrShapePCB,
    GrText,
    GrTextFp,
    GrTextPCB,
    GrTextPCBBase,
)

from common.kicad_project import KicadProject

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
        help="Copy edge.cuts from footprints to pcb; set all Edge.Cuts graphics thickness",
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


def run(pro: KicadProject, args: argparse.Namespace) -> None:
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
    pcb_filter_run(pro, **argsf)


def keep_first_pads_only(source_pcb: Board) -> None:
    pad_one_markings = ["1", "A1"]
    for footprint in source_pcb.footprints:
        footprint.pads = [pad for pad in footprint.pads if pad.number in pad_one_markings]


def pcb_filter_run(
    pro: KicadProject,
    allowed_layers_full: str | None = None,
    allowed_layers: str | None = None,
    values: bool = False,
    references: bool = False,
    vias: bool = False,
    zones: bool = False,
    tracks: bool = False,
    dimensions: bool = False,
    stackup: bool = False,
    side: str | None = None,
    std_edge: bool = False,
    ref_filter: str | None = None,
    ref_filter_other: str | None = None,
    cascade: bool = False,
    infile: str | None = None,
    outfile: str = "filtered.kicad_pcb",
    generate_frame: bool = False,
    mirror_bottom: bool = False,
    std_dimension: bool = False,
    first_pads_only: bool = False,
    std_graphics: bool = False,
) -> None:
    if not outfile.endswith(".kicad_pcb"):
        outfile += ".kicad_pcb"
    if cascade and Path(outfile).exists():
        infile = outfile

    log.info("Loading PCB")
    board = Board.from_file(Path(infile)) if infile is not None else pro.pcb_root

    if not side:
        _side = None
    elif side == "top":
        _side = BoardSide.FRONT
    elif side == "bottom":
        _side = BoardSide.BACK
    else:
        raise AttributeError("Side must be either 'top' or 'bottom'")

    if std_edge:
        # has to be before any footprint removal
        copy_edge_from_footprint(board)

    filter_main = None if ref_filter is None else RefFilter(ref_filter)
    filter_other = None if ref_filter_other is None else RefFilter(ref_filter_other)

    board.footprints = [fp for fp in board.footprints if reference_match(fp, _side, filter_main, filter_other)]

    if stackup:
        stackup_group = next((g for g in board.groups if g.name == "group-boardStackUp"), None)
        if stackup_group:
            board.graphic_items = [item for item in board.graphic_items if item.uuid not in stackup_group.members]
            board.groups = [g for g in board.groups if g.name != "group-boardStackUp"]

    if references or values:
        for fp in board.footprints:
            if references:
                fp.properties.ref.hide = True
            if values:
                val = fp.properties.get("Value")
                if val:
                    val.hide = True

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
        board.dimensions += add_main_dimensions(_side, bbox_limits)

    if std_graphics:
        unify_graphics(board, bbox_limits)

    if _side == BoardSide.BACK and mirror_bottom:
        board = mirror_texts(board)

    if first_pads_only:
        keep_first_pads_only(board)

    log.info(f"Saving filtered PCB: {outfile}")
    board.to_file(Path(outfile))


def layer_filtration(board: Board, allowed_layers: str | None, allowed_layers_full: str | None) -> None:
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
            fp.graphic_items = [item for item in fp.graphic_items if item.layer in layers]
            for prop in fp.properties:
                if prop.layer in layers:
                    continue
                prop.hide = True


def std_layer_names(layers_str: str) -> LayerSet[BaseLayer]:
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
    return LayerSet(*(BaseLayer.deserialize_downcast(layer) for layer in layers_list))


def copy_edge_from_footprint(board: Board) -> None:
    """Copies all Edge.Cuts graphics found in footprints to board level"""
    for fp in board.footprints:
        for item in fp.graphic_items:
            if not isinstance(item, GrShapeFp) or item.layer != Layer.EDGE_CUTS:
                continue

            board.graphic_items.append(item.to_shape_pcb(fp.position))


def unify_style_graphics(board: Board, layers: LayerSet[BaseLayer], width: float) -> None:
    """set thickness of graphics on specified layer"""
    for g in board.graphic_items:
        if isinstance(g, GrShapePCB) and g.layer in layers:
            if g.stroke is None:
                g.stroke = Stroke()
            g.stroke.width = width


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

        def typefilt(char: str) -> list[str]:
            return [p for (p, mode) in pat_dict.items() if mode == char]

        self.mode_additive = filter_pat[0] == "+"
        self.pat_add = typefilt("+")
        self.pat_rem = typefilt("-")


def check_primary_side(fp: Footprint, side: BoardSide | None) -> bool:
    if side is None or fp.side == side:
        return True

    # Simplified check to detect edge connectors
    front, back = False, False
    for pad in fp.pads:
        if not isinstance(pad, (PadSMD, PadEdgeConnector)):
            continue
        front = front or Layer.CU_F in pad.layers
        back = back or Layer.CU_B in pad.layers
    return front and back


def reference_match(
    fp: Footprint, side: BoardSide | None, filt: RefFilter | None, filt_other: RefFilter | None
) -> bool:
    if check_primary_side(fp, side):
        if filt is None:
            return True
    else:
        filt = filt_other
        if filt is None:
            return False

    # Extract prefix from reference,
    ref = fp.properties.ref.value
    ref_type = ref.rstrip("0123456789?*")

    # Compare prefix with selected pattern
    if filt.mode_additive:
        return (ref_type in filt.pat_add and ref not in filt.pat_rem) or ref in filt.pat_add
    return (ref_type not in filt.pat_rem and ref not in filt.pat_rem) or ref in filt.pat_add


def layer_filter_match(g: GrItemPCB, layers: LayerSet[BaseLayer], full: bool) -> bool:
    if hasattr(g, "layer") and g.layer not in layers:
        if full:
            return False
        if not isinstance(g, GrTextPCB):
            return False
        if g.knockout:
            return True
        if g.text.startswith("SHA"):
            return True
        return False
    return True


def mirror_text_justify(effects: Effects) -> Effects:
    """set text mirrored & flip its justification"""
    if not effects.justify:
        effects.justify = Justify()

    effects.justify.mirror = True
    if effects.justify.horizontal == JustifyH.RIGHT:
        effects.justify.horizontal = JustifyH.LEFT
    elif effects.justify.horizontal == JustifyH.LEFT:
        effects.justify.horizontal = JustifyH.RIGHT
    return effects


def mirror_footprint_text(fp: Footprint) -> None:
    """Mirror texts inside footprint (property & standalone texts)"""

    for p in fp.properties:
        if not p.effects:
            p.effects = Effects()
        p.effects = mirror_text_justify(p.effects)

    for g in fp.graphic_items:
        if isinstance(g, GrTextFp):
            g.effects = mirror_text_justify(g.effects)


def mirror_texts(board: Board) -> Board:
    """Mirror all text in pcb (footprint, dimension & standalone texts)"""
    for fp in board.footprints:
        mirror_footprint_text(fp)

    for g in board.graphic_items:
        if isinstance(g, GrTextPCB):
            g.effects = mirror_text_justify(g.effects)

    for d in board.dimensions:
        if not isinstance(d, (DimensionLeader, DimensionRadial, DimensionOrthogonal, DimensionAligned)):
            continue
        if not d.text:
            d.text = GrTextPCBBase()
        d.text.effects = mirror_text_justify(d.text.effects)

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

    def update(self, ismin: bool, main: float, aux: float) -> BBoxPoint:
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


def get_outline_bbox(board: Board) -> list[BBoxPoint]:
    """Returns board outline bbox coordinates together with ranges where board touches bbox"""

    pts: list[Position] = []
    (minx, maxx, miny, maxy) = (BBoxPoint(inf), BBoxPoint(-inf), BBoxPoint(inf), BBoxPoint(-inf))
    pts.extend(
        BBox.extrema_from_shapes(
            g for g in board.graphic_items if isinstance(g, GrShapePCB) and g.layer == Layer.EDGE_CUTS
        )
    )
    for fp in board.footprints:
        pts.extend(
            BBox.extrema_from_shapes(
                g.to_shape_pcb(fp.position)
                for g in fp.graphic_items
                if isinstance(g, GrShapeFp) and g.layer == Layer.EDGE_CUTS
            )
        )

    for p in pts:
        minx = minx.update(True, p.x, p.y)
        miny = miny.update(True, p.y, p.x)
        maxx = maxx.update(False, p.x, p.y)
        maxy = maxy.update(False, p.y, p.x)
    return [minx, maxx, miny, maxy]


def remove_main_dimensions(board: Board) -> list[Dimension]:
    """Remove largest dimensions (one horizontal, one vertical)"""
    vertical = []
    horizontal = []
    rest = []
    (maxlen_x, maxlen_y) = (0, 0)
    # remove largest dimensions
    for d in board.dimensions:
        len_x = abs(d.pts[0].x - d.pts[1].x)
        len_y = abs(d.pts[0].y - d.pts[1].y)
        if (isinstance(d, DimensionAligned) and len_x * 10 < len_y) or (
            isinstance(d, DimensionOrthogonal) and d.orientation == 1
        ):
            vertical.append(d)
            if maxlen_y < len_y:
                maxlen_y = len_y
        elif (isinstance(d, DimensionAligned) and len_x > 10 * len_y) or (
            isinstance(d, DimensionOrthogonal) and d.orientation == 0
        ):
            horizontal.append(d)
            if maxlen_x < len_x:
                maxlen_x = len_x
        else:
            rest.append(d)
    vertical = [d for d in vertical if maxlen_y - abs(d.pts[0].y - d.pts[1].y) > 0.01]
    horizontal = [d for d in horizontal if maxlen_x - abs(d.pts[0].x - d.pts[1].x) > 0.01]
    return vertical + horizontal + rest


def add_main_dimensions(side: BoardSide | None, bbox_limits: list[BBoxPoint]) -> list[Dimension]:
    """Add new standardized dimensions (one horizontal, one vertical)
    (new dimensions will be on right board side for top and on left for bottom w text mirrored)"""

    # Add new vertical dimension based on outline
    [minx, maxx, miny, maxy] = bbox_limits
    if side == BoardSide.BACK:
        dim_pts = [Position(miny.aux_min, miny.main), Position(maxy.aux_min, maxy.main)]
        height = minx.main - miny.aux_min - 8
    else:
        dim_pts = [Position(miny.aux_max, miny.main), Position(maxy.aux_max, maxy.main)]
        height = maxx.main - miny.aux_max + 8

    new_dim_x = DimensionOrthogonal(
        pts=[Position(minx.main, minx.aux_max), Position(maxx.main, maxx.aux_max)],
        height=maxy.main - minx.aux_max + 8,
        orientation=DimensionOrthogonalOrientation.HORIZONTAL,
    )
    new_dim_y = DimensionOrthogonal(
        pts=dim_pts,
        height=height,
        orientation=DimensionOrthogonalOrientation.VERTICAL,
    )
    return [new_dim_x, new_dim_y]


def generate_frame_f(board: Board, bbox_limits: list[BBoxPoint]) -> None:
    """Add graphical rectangle to pcb, that is expanded outline bbox"""
    border = 60
    [minx, maxx, miny, maxy] = bbox_limits
    board.graphic_items.append(
        GrRectPCB(
            start=Position(minx.main - border, miny.main - border),
            end=Position(maxx.main + border, maxy.main + border),
            layer=Layer.MARGIN,
        )
    )


def std_grtext(text: GrText, scale: float) -> float:
    if text.effects is None:
        text.effects = Effects()
    old_thick = text.effects.font.thickness if text.effects.font.thickness else 0
    old_height = old_thick + text.effects.font.size.height
    text.effects.font.size.width = 2 * scale
    text.effects.font.size.height = 2 * scale
    text.effects.font.thickness = 0.2 * scale
    text.effects.font.bold = False
    text.effects.font.face = None
    return text.effects.font.thickness + text.effects.font.size.height - old_height


def unify_style_text(board: Board, layers: LayerSet[BaseLayer], scale: float) -> None:
    """set text style on specified layer"""
    for g in board.graphic_items:
        if isinstance(g, GrTextPCB) and g.layer in layers:
            std_grtext(g, scale)


def get_aligned_dim_center(dim: DimensionAligned) -> tuple[float, float]:
    """Gets point that is the center (middle of main dimension line) of dimension"""
    x1, y1 = dim.pts[0].x, dim.pts[0].y
    x2, y2 = dim.pts[1].x, dim.pts[1].y

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


def unify_style_dimensions(board: Board, layers: LayerSet[BaseLayer], scale: float, bbox: list[float]) -> None:
    """set text style on specified layer"""
    [minx, maxx, miny, maxy] = bbox

    # qtr_dim is { layer : [ [dim_pos1, dim_pos2, ..] [..] [..] [..] ] }
    # 4 quarters left, right, top, bottom
    qtr_dim: dict[BaseLayer, list[list[float]]] = {}

    # dim.uuid: (dim_quarter, dim_pos)
    dim_qtr_pos: dict[str, tuple[int, float]] = {}

    for d in board.dimensions:
        if isinstance(d, DimensionAligned):
            d_center = get_aligned_dim_center(d)
        elif isinstance(d, DimensionOrthogonal):
            if d.orientation == DimensionOrthogonalOrientation.HORIZONTAL:
                d_center = (d.pts[0].x + d.pts[1].x) * 0.5, d.pts[0].y + d.height
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
        if isinstance(d, DimensionCenter):
            continue
        assert isinstance(d, (DimensionLeader, DimensionRadial, DimensionOrthogonal, DimensionAligned))
        if d.layer in layers:
            d.format = DimensionValueFormat(
                precision=1,  # one fraction digit
                units=DimensionUnit.MM,  # millimeters
                units_format=DimensionUnitStyle.SKIP,  # bare value, no unit suffix
                suppress_zeroes=False,
                override_value=d.format.override_value if d.format else None,
            )

            if isinstance(d, (DimensionLeader, DimensionRadial)):
                arrow_len = d.style.arrow_length
            else:
                length = ((d.pts[0].x - d.pts[1].x) ** 2 + (d.pts[0].y - d.pts[1].y) ** 2) ** 0.5
                arrow_len = min(1, round(length / 2, 2))

            d.style = DimensionStyle(
                extension_offset=d.style.extension_offset,
                extension_height=d.style.extension_height,
                thickness=0.1,
                arrow_length=arrow_len,
                text_position_mode=DimensionTextPosition.OUTSIDE,
                arrow_direction=d.style.arrow_direction,
                text_frame=d.style.text_frame,
                keep_text_aligned=True,
            )
            if not d.text:
                d.text = GrTextPCBBase()
            height_change = std_grtext(d.text, scale)

            # Extend dimensions to reduce overlaps due to text scaling
            if d.uuid in dim_qtr_pos:
                assert isinstance(d, (DimensionOrthogonal, DimensionAligned))
                qtr, pos = dim_qtr_pos[d.uuid]
                dim_idx = qtr_dim[d.layer][qtr].index(pos)
                # additional offset for dimmesniosn on the right and bottom of board
                edge_overlap_cor = 1 if qtr in [1, 3] else 0
                d.height += math.copysign((dim_idx + edge_overlap_cor) * height_change * 1.66, d.height)


def unify_graphics(board: Board, bbox_limits: list[BBoxPoint]) -> None:
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
    unify_style_graphics(board, LayerSet(Layer.EDGE_CUTS), 0.2)
    layers = LayerUser.all
    unify_style_graphics(board, layers, 0.1)
    unify_style_graphics(board, LayerSet(Layer.USER(9)), 0.02)
    unify_style_text(board, layers, scale)
    unify_style_dimensions(board, layers, scale, simple_bbox)
