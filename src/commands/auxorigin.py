import sys
import argparse
import logging
import math
from kiutils.board import Board
from kiutils.schematic import Position
from kiutils.items.gritems import GrCircle, GrArc, GrPoly

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


# Calculates center point and radius of the circle defined with an arc
def calculate_circle(item: GrArc) -> tuple[float, float, float]:
    # Determinant
    det = (item.mid.X - item.start.X) * (item.end.Y - item.start.Y) - (item.end.X - item.start.X) * (
        item.mid.Y - item.start.Y
    )
    # Calculate square distances
    a = pow(item.start.X, 2) + pow(item.start.Y, 2)
    b = pow(item.mid.X, 2) + pow(item.mid.Y, 2)
    c = pow(item.end.X, 2) + pow(item.end.Y, 2)
    # Calculate circle center - intersecting point of perpendicular bisectors of a triangle
    # sides are the center point of the circle circumscribed on that triangle.
    circle_x = -((item.mid.Y - item.start.Y) * (c - a) - (item.end.Y - item.start.Y) * (b - a)) / (2 * det)
    circle_y = -((item.end.X - item.start.X) * (b - a) - (item.mid.X - item.start.X) * (c - a)) / (2 * det)
    # Calculate radius - pythagorean theorem
    r = math.hypot(item.start.X - circle_x, item.start.Y - circle_y)
    return circle_x, circle_y, r


# Calculates arc extremum in x and y axes
def find_arc_extrema(circle_x: float, circle_y: float, r: float, item: GrArc) -> tuple[float, float, float, float]:
    # Finds normalized angle in radians between selected point and circle mid point
    def angle(x: float, y: float) -> float:
        angle = math.atan2(y - circle_y, x - circle_x)
        angle %= 2 * math.pi
        return angle

    # Verifies if angle is in range [start_angle, end_angle] in cartesian system
    def is_angle_in_range(angle: float, start_angle: float, end_angle: float) -> bool:
        if start_angle <= end_angle:
            return start_angle <= angle <= end_angle
        return angle >= start_angle or angle <= end_angle

    # Calculates angles for arc defining points
    start_angle = angle(item.start.X, item.start.Y)
    end_angle = angle(item.end.X, item.end.Y)

    # Add arc defining points as potential extremum
    extrema = [(item.start.X, item.start.Y), (item.mid.X, item.mid.Y), (item.end.X, item.end.Y)]

    # Add extremum occuring for arc on axes
    for candidate_angle in [0, math.pi / 2, math.pi, 3 * math.pi / 2]:
        x_extreme = circle_x + r * math.cos(candidate_angle)
        y_extreme = circle_y + r * math.sin(candidate_angle)
        if is_angle_in_range(candidate_angle, start_angle, end_angle):
            extrema.append((x_extreme, y_extreme))

    x = [point[0] for point in extrema]
    y = [point[1] for point in extrema]

    return max(x), min(x), max(y), min(y)


def set_aux_origin_on_size(board: Board, side: str) -> None:
    log.info("Reading PCB dimmmensions")
    x = []
    y = []
    for item in board.graphicItems:
        if item.layer != "Edge.Cuts":
            continue
        # Circle case
        if isinstance(item, GrCircle):
            # Coordinates of the square circumscribed by circle
            r = math.hypot(item.center.X - item.end.X, item.center.Y - item.end.Y)
            x.append(item.center.X + r)
            x.append(item.center.X - r)
            y.append(item.center.Y + r)
            y.append(item.center.Y - r)
            continue
        # Arc case
        if isinstance(item, GrArc):
            try:
                circ_x, circ_y, r = calculate_circle(item)
                max_x, min_x, max_y, min_y = find_arc_extrema(circ_x, circ_y, r, item)
            # Handle determinant == 0 in calculated circle
            except ZeroDivisionError:
                log.warning("Found arc object with colinear points, omitting")
                continue
            x.append(max_x)
            x.append(min_x)
            y.append(max_y)
            y.append(min_y)
            continue
        # Poly case
        if isinstance(item, GrPoly):
            for point in item.coordinates:
                x.append(point.X)
                y.append(point.Y)
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

    if "r" in side:
        aux_x = max(x)
    else:
        aux_x = min(x)

    if "t" in side:
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
