import sys
import argparse
import logging
import math
from typing import List
from pathlib import Path
from askiff.kistruct.board import Board
from askiff.kistruct.common_pcb import Layer
from askiff.kistruct.gritems import GrCircle, GrArcPCB, GrPoly
from askiff.kistruct.common import BaseArc, Position

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


def angle(x: float, y: float, ref_x: float, ref_y: float) -> float:
    """Finds normalized angle in radians between selected point and reference point"""
    angle = math.atan2(y - ref_y, x - ref_x)
    angle %= 2 * math.pi
    return angle


def is_angle_in_range(angle: float, start_angle: float, end_angle: float) -> bool:
    """Verifies if angle is in range [start_angle, end_angle] in cartesian system"""
    if start_angle <= end_angle:
        return start_angle <= angle <= end_angle
    return angle >= start_angle or angle <= end_angle


def calculate_circle(arc: BaseArc) -> tuple[float, float, float]:
    """Calculates center point and radius of the circle defined with an arc"""
    # Squared distance of triangle points to origin
    a = pow(arc.start.X, 2) + pow(arc.start.Y, 2)
    b = pow(arc.mid.X, 2) + pow(arc.mid.Y, 2)
    c = pow(arc.end.X, 2) + pow(arc.end.Y, 2)
    # Determinant
    det = (arc.mid.X - arc.start.X) * (arc.end.Y - arc.start.Y) - (arc.end.X - arc.start.X) * (arc.mid.Y - arc.start.Y)
    # Circle center calculated based on circumcircle equations - perpendicular bisectors of a triangle
    # sides are intersecting in center point of the circle circumscribed on that triangle.
    circle_x = -((arc.mid.Y - arc.start.Y) * (c - a) - (arc.end.Y - arc.start.Y) * (b - a)) / (2 * det)
    circle_y = -((arc.end.X - arc.start.X) * (b - a) - (arc.mid.X - arc.start.X) * (c - a)) / (2 * det)
    # Calculate radius - pythagorean theorem
    r = math.hypot(arc.start.X - circle_x, arc.start.Y - circle_y)
    return circle_x, circle_y, r


def find_arc_extrema(circle_x: float, circle_y: float, r: float, arc: BaseArc) -> tuple[float, float, float, float]:
    """Calculates arc extremum in x and y axes"""
    # Calculates angles for arc defining points
    start_angle = angle(x=arc.start.X, y=arc.start.Y, ref_x=circle_x, ref_y=circle_y)
    end_angle = angle(x=arc.end.X, y=arc.end.Y, ref_x=circle_x, ref_y=circle_y)

    # Add arc defining points as potential extremum
    extrema = [(arc.start.X, arc.start.Y), (arc.mid.X, arc.mid.Y), (arc.end.X, arc.end.Y)]

    # Add extremum occurring for arc on axes
    for candidate_angle in [0, math.pi / 2, math.pi, 3 * math.pi / 2]:
        x_extreme = circle_x + r * math.cos(candidate_angle)
        y_extreme = circle_y + r * math.sin(candidate_angle)
        if is_angle_in_range(candidate_angle, start_angle, end_angle):
            extrema.append((x_extreme, y_extreme))

    x = [point[0] for point in extrema]
    y = [point[1] for point in extrema]

    return max(x), min(x), max(y), min(y)


def handle_arc(arc: BaseArc, x: List[float], y: List[float]) -> None:
    try:
        circ_x, circ_y, r = calculate_circle(arc)
        max_x, min_x, max_y, min_y = find_arc_extrema(circ_x, circ_y, r, arc)
    # Handle determinant == 0 in calculated circle
    except ZeroDivisionError:
        log.warning("Found arc object with colinear points, omitting")
        return
    x.append(max_x)
    x.append(min_x)
    y.append(max_y)
    y.append(min_y)


def set_aux_origin_on_size(board: Board, side: str) -> None:
    log.info("Reading PCB dimensions")
    x = []
    y = []
    for item in board.graphic_items:
        if item.layers != {Layer.EDGE}:
            continue

        # Circle case
        if isinstance(item, GrCircle):
            # Coordinates of the square circumscribed by circle
            r = math.hypot(item.center.x - item.end.x, item.center.y - item.end.y)
            x.append(item.center.x + r)
            x.append(item.center.x - r)
            y.append(item.center.y + r)
            y.append(item.center.y - r)
            continue
        # Arc case
        if isinstance(item, GrArcPCB):
            handle_arc(item, x, y)
            continue
        # Poly case
        if isinstance(item, GrPoly):
            for p in item.pts:
                if isinstance(p, BaseArc):
                    handle_arc(item, x, y)
                else:
                    x.append(p.X)
                    y.append(p.Y)
            continue
        # Rectangle, segment case
        if hasattr(item, "start"):
            y.append(item.start.y)
            x.append(item.start.x)
        if hasattr(item, "end"):
            x.append(item.end.x)
            y.append(item.end.y)

    for footprint in board.footprints:
        if footprint.position is None:
            continue

        for item in footprint.graphic_items:
            if item.layers != {Layer.EDGE}:
                continue

            ref = next((p.value for p in footprint.properties if p.key == "Reference"), None)
            if not hasattr(item, "start"):
                log.warning(f"{ref} has graphicItem without start parameter")
                continue

            angle = math.radians(-footprint.position.angle if footprint.position.angle is not None else 0)
            sina, cosa = math.sin(angle), math.cos(angle)

            if angle != 0:
                log.debug(f"Angle of {ref} is {angle}")

            x.append(item.start.x * cosa - item.start.Y * sina + footprint.position.x)
            x.append(item.end.x * cosa - item.end.Y * sina + footprint.position.x)
            y.append(item.start.y * cosa - item.start.X * sina + footprint.position.y)
            y.append(item.end.y * cosa - item.end.X * sina + footprint.position.y)

            log.debug(f"Coordinates of {ref}")
            log.debug(f"  X start: {x[-2]}")
            log.debug(f"  X end: {x[-1]}")
            log.debug(f"  Y start: {y[-2]}")
            log.debug(f"  Y end: {y[-1]}")

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
    board = Board.from_file(Path(ki_pro.pcb_file))
    if args.reset:
        set_aux_axis_origin(board, 0, 0)
    elif args.position:
        x, y = args.position
        set_aux_axis_origin(board, x, y)
    else:
        set_aux_origin_on_size(board, args.side)
