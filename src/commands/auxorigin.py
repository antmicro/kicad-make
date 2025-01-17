import sys
import argparse
import logging
import math
from kiutils.board import Board
from kiutils.schematic import Position
from kiutils.items.gritems import GrCircle

from common.kicad_project import KicadProject

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


def save_board(board: Board) -> None:
    log.info("Saving PCB")
    board.to_file()


def set_aux_axis_origin(board: Board, x: float, y: float) -> None:
    log.info("Setting auxilary axis origin to (%.3f,%.3f)", x, y)
    board.setup.auxAxisOrigin = Position(x, y)
    save_board(board)


def set_aux_origin_on_size(board: Board, side: str) -> None:
    log.info("Reading PCB dimmmensions")
    x = []
    y = []
    for item in board.graphicItems:
        if item.layer != "Edge.Cuts":
            continue
        # Circle case
        if isinstance(item, GrCircle):
            log.info("Detected circular PCB shape")
            # Coordinates of the square circumscribed by circle
            r = math.hypot(abs(item.center.X - item.end.X), abs(item.center.Y - item.end.Y))
            x.append(item.center.X + r)
            x.append(item.center.X - r)
            y.append(item.center.Y + r)
            y.append(item.center.Y - r)
            continue
        # Rectangle, segment case
        if hasattr(item, "start"):
            y.append(item.start.Y)
            x.append(item.start.X)
        if hasattr(item, "end"):
            x.append(item.end.X)
            y.append(item.end.Y)

    for footprint in board.footprints:
        if footprint.position is None:
            continue
        for item in footprint.graphicItems:
            if item.layer == "Edge.Cuts":
                if not hasattr(item, "start"):
                    continue
                x.append(item.start.X + footprint.position.X)
                x.append(item.end.X + footprint.position.X)
                y.append(item.start.Y + footprint.position.Y)
                y.append(item.end.Y + footprint.position.Y)

    if "t" in side:
        aux_x = max(x)
    else:
        aux_x = min(x)

    if "r" in side:
        aux_y = min(y)
    else:
        aux_y = max(y)

    set_aux_axis_origin(board, aux_x, aux_y)


def set_aux_origin(ki_pro: KicadProject, args: argparse.Namespace) -> None:
    """Sets aux Axis Origin in .kicad_pcb file according to args"""

    if not len(ki_pro.pcb_file):
        log.error("PCB file was not detected or does not exists")
        sys.exit(1)

    log.info("Loading PCB")
    board = Board.from_file(ki_pro.pcb_file)
    if args.reset:
        set_aux_axis_origin(board, 0, 0)
    elif args.position:
        x, y = args.position
        set_aux_axis_origin(board, x, y)
    else:
        set_aux_origin_on_size(board, args.side)
