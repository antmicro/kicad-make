import argparse
import logging
from collections.abc import Iterable

from askiff import Board, Project
from askiff.common import BBox, Position
from askiff.common_pcb import Layer
from askiff.gritems import GrItem, _GrShapePCBFp

log = logging.getLogger(__name__)


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    aux_origin_parser = subparsers.add_parser(
        "aux-origin", help="Set drill origin to bounding box corner or given x,y coordinate."
    )
    exclusive_group = aux_origin_parser.add_mutually_exclusive_group(required=True)
    exclusive_group.add_argument(
        "-r",
        "--reset",
        action="store_true",
        help="Reset position of auxilary origin to (0,0).",
    )
    exclusive_group.add_argument(
        "-s",
        "--side",
        choices=["tl", "tr", "bl", "br"],
        help="Edge of the PCB bounding box to place aux origin, default: bl.",
    )
    exclusive_group.add_argument(
        "-p",
        "--position",
        metavar=("x_pos", "y_pos"),
        type=float,
        nargs=2,
        help="Position for aux origin to be placed.",
    )

    aux_origin_parser.set_defaults(func=set_aux_origin)


def set_aux_axis_origin(board: Board, x: float, y: float) -> None:
    log.info("Setting auxilary axis origin to (%.3f,%.3f)", x, y)
    board.setup.aux_axis_origin = Position(x, y)
    log.info(f"Saving PCB: {board.fs_path}")
    board.to_file()


def get_bbox(items: Iterable[GrItem], fp_pos: Position | None = None) -> BBox | None:
    bbox = BBox.from_shapes(item for item in items if isinstance(item, _GrShapePCBFp) and item.layer == Layer.EDGE_CUTS)
    return bbox.to_global(fp_pos) if bbox and fp_pos else bbox


def set_aux_origin_on_size(board: Board, side: str) -> None:
    log.info("Reading PCB dimensions")

    pcb_bbox = get_bbox(board.graphic_items)
    fp_bboxes = (get_bbox(fp.graphic_items, fp.position) for fp in board.footprints)
    bbox = BBox.from_shapes(bbox for bbox in (pcb_bbox, *fp_bboxes) if bbox)

    if not bbox:
        raise Exception("Board outline could not be detected!")

    aux_x = bbox.end.x if "r" in side else bbox.start.x
    aux_y = bbox.start.y if "t" in side else bbox.end.y

    set_aux_axis_origin(board, aux_x, aux_y)


def set_aux_origin(pro: Project, args: argparse.Namespace) -> None:
    """Sets aux Axis Origin in .kicad_pcb file according to args"""

    for pcb in pro.pcb:
        log.info(f"Loading PCB : {pcb.fs_path}")
        if args.reset:
            set_aux_axis_origin(pcb, 0, 0)
        elif args.position:
            x, y = args.position
            set_aux_axis_origin(pcb, x, y)
        else:
            set_aux_origin_on_size(pcb, args.side)
