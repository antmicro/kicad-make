"""kibuzzard-to-graphic"""

import logging
import argparse
from askiff.board import Board
from askiff.gritems import GrPoly, GrPolyFp

from math import sin, cos, radians
from pathlib import Path
from common.kicad_project import KicadProject

log = logging.getLogger(__name__)


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Register parser and its arguments as subparser"""
    parser = subparsers.add_parser("kibuzzard-to-graphic", help="Convert Kibuzzard footprints to graphical polygons")
    parser.set_defaults(func=run)


def main(pro: KicadProject, args: argparse.Namespace) -> None:
    """Main module function"""

    pcb_path = pro.pcb_file
    board = Board().from_file(Path(pcb_path))

    footprints_to_remove = []

    for footprint in board.footprints:
        if not footprint.lib_id.name.startswith("kibuzzard") or not footprint.graphic_items:
            continue
        log.debug(f"KiBuzzard footprint found ({footprint.entry_name})")

        footprints_to_remove.append(footprint)
        for fp_item in footprint.graphic_items:
            if not isinstance(fp_item, GrPolyFp):
                continue

            # Append position to offset coordinates
            gr_poly = GrPoly()
            gr_poly.coordinates = fp_item.coordinates.copy()

            for pos in gr_poly.coordinates:
                # Add footprint offset and rotation to gr_poly coordinates
                rotation = footprint.position.angle
                if not rotation:
                    rotation = 0

                x_angle_offset = pos.x * cos(radians(rotation)) + pos.y * sin(radians(rotation))
                y_angle_offset = pos.y * cos(radians(rotation)) - pos.x * sin(radians(rotation))
                pos.x = x_angle_offset
                pos.y = y_angle_offset
                pos.x += footprint.position.x
                pos.y += footprint.position.y

            gr_poly.layer = fp_item.layer
            gr_poly.width = fp_item.stroke.width
            gr_poly.fill = fp_item.stroke.type
            board.graphic_items.append(gr_poly)
            log.debug("Created graphical polygon from KiBuzzard footprint")

    for footprint in footprints_to_remove:
        board.footprints.remove(footprint)
        log.debug(f"Deleted KiBuzzard footprint ({footprint.entry_name})")

    board.to_file(Path(pcb_path))


def run(project: KicadProject, args: argparse.Namespace) -> None:
    """Entry function for module"""
    main(project, args)
