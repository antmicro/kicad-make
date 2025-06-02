"""kibuzzard-to-graphic"""

import logging
import argparse
from kiutils.board import Board
from kiutils.items.gritems import GrPoly
from kiutils.items.fpitems import FpPoly
from math import sin, cos, radians

from common.kicad_project import KicadProject
from .prettify import run as prettify

log = logging.getLogger(__name__)


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Register parser and its arguments as subparser"""
    parser = subparsers.add_parser("kibuzzard-to-graphic", help="Convert Kibuzzard footprints to graphical polygons")
    parser.set_defaults(func=run)


def main(kicad_project: KicadProject, args: argparse.Namespace) -> None:
    """Main module function"""

    pcb_path = kicad_project.pcb_file
    board = Board().from_file(pcb_path)

    footprints_to_remove = []

    for footprint in board.footprints:
        if not footprint.libId.startswith("kibuzzard") or len(footprint.graphicItems) == 0:
            continue
        log.debug(f"KiBuzzard footprint found ({footprint.entryName})")

        footprints_to_remove.append(footprint)
        for fp_item in footprint.graphicItems:

            if not isinstance(fp_item, FpPoly):
                continue

            # Append position to offset coordinates
            gr_poly = GrPoly()
            gr_poly.coordinates = fp_item.coordinates.copy()

            for pos in gr_poly.coordinates:
                # Add footprint offset and rotation to gr_poly coordinates
                rotation = footprint.position.angle
                if rotation is None:
                    rotation = 0

                x_angle_offset = pos.X * cos(radians(rotation)) + pos.Y * sin(radians(rotation))
                y_angle_offset = pos.Y * cos(radians(rotation)) - pos.X * sin(radians(rotation))
                pos.X = x_angle_offset
                pos.Y = y_angle_offset
                pos.X += footprint.position.X
                pos.Y += footprint.position.Y

            gr_poly.layer = fp_item.layer
            gr_poly.width = fp_item.stroke.width
            gr_poly.fill = fp_item.stroke.type
            board.graphicItems.append(gr_poly)
            log.debug("Created graphical polygon from KiBuzzard footprint")

    for footprint in footprints_to_remove:
        board.footprints.remove(footprint)
        log.debug(f"Deleted KiBuzzard footprint ({footprint.entryName})")

    board.to_file(pcb_path)
    prettify(kicad_project, argparse.Namespace())


def run(project: KicadProject, args: argparse.Namespace) -> None:
    """Entry function for module"""
    main(project, args)
