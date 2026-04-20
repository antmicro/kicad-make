"""kibuzzard-to-graphic"""

import argparse
import logging

from askiff import Project
from askiff.gritems import GrPolyFp


log = logging.getLogger(__name__)


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Register parser and its arguments as subparser"""
    parser = subparsers.add_parser("kibuzzard-to-graphic", help="Convert Kibuzzard footprints to graphical polygons")
    parser.set_defaults(func=run)


def kibuzzard_to_graphic(pro: Project, _args: argparse.Namespace) -> None:
    """Main module function"""

    for pcb in pro.pcb:
        footprints_to_remove = []

        for footprint in pcb.footprints:
            if not footprint.lib_id.name.startswith("kibuzzard") or not footprint.graphic_items:
                continue
            log.debug(f"KiBuzzard footprint found ({footprint.entry_name})")

            footprints_to_remove.append(footprint)
            pcb.graphic_items.extend(
                item.to_shape_pcb(footprint.position) for item in footprint.graphic_items if isinstance(item, GrPolyFp)
            )

        for footprint in footprints_to_remove:
            pcb.footprints.remove(footprint)
            log.debug(f"Deleted KiBuzzard footprint ({footprint.entry_name})")

        pcb.to_file()


def run(project: Project, args: argparse.Namespace) -> None:
    """Entry function for module"""
    kibuzzard_to_graphic(project, args)
