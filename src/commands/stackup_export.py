"""Command for exporting stackup information from kicad's PCB file"""

import argparse
import csv
import json
import logging
import os
import sys
from typing import Any, Dict, List, Union

from kiutils.board import Board
from kiutils.items.brditems import StackupLayer

from common.kicad_project import KicadProject

log = logging.getLogger(__name__)


# Minor version should be with any changes to format.
# Major only when breaking changes are implemented
FORMAT_VERSION = "1.0"

FILENAME = "stackup"


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Adds stackup-export subparser to passed parser"""
    stackup_export_parser = subparsers.add_parser("stackup-export", help="Export stackup information to file.")
    stackup_export_parser.add_argument("-o", dest="output_filename", help="Change export file name/location.")
    stackup_export_parser.add_argument(
        "--legacy-csv",
        dest="legacy_csv",
        action="store_true",
        help="Export as csv with legacy format.",
    )
    stackup_export_parser.set_defaults(func=run)


def run(kicad_project: KicadProject, args: argparse.Namespace) -> None:
    """Run stackup-export command"""
    board = Board().from_file(kicad_project.pcb_file)
    stackup = {"layers": export_stackup(board)}
    kicad_project.create_fab_dir()

    if args.legacy_csv:
        save_csv(
            stackup["layers"],
            (
                args.output_filename
                if args.output_filename is not None
                else os.path.join(kicad_project.relative_fab_path, FILENAME + ".csv")
            ),
        )
    else:
        save_json(
            stackup,
            (
                args.output_filename
                if args.output_filename is not None
                else os.path.join(kicad_project.relative_fab_path, FILENAME + ".json")
            ),
        )


def export_stackup(board: Board) -> List[Dict[str, Any]]:
    """Exports stackup as list of layers in custom format"""
    layers: List[Dict[str, Any]] = []
    if board.setup.stackup is None:
        log.error("Stackup wasn't set for the project. " "User needs to open the editor and save it. Aborting")
        sys.exit(1)
    for layer in board.setup.stackup.layers:
        layers.append(export_layer(layer))
        if len(layer.subLayers) > 0:
            for i, _ in enumerate(layer.subLayers):
                layers.append(export_layer(layer, i))
    return layers


def export_layer(layer: StackupLayer, sublayer: Union[int, None] = None) -> Dict[str, Any]:
    """Converts kiutil layer representation to our representation.
    If sublayer is passed it exports it as it were a layer"""
    out = {}
    if len(layer.subLayers) > 0:
        if sublayer is None:
            out["name"] = layer.name + " (1/" + str(len(layer.subLayers) + 1) + ")"
        else:
            out["name"] = layer.name + " (" + str(sublayer + 2) + "/" + str(len(layer.subLayers) + 1) + ")"
    else:
        out["name"] = layer.name
    out["type"] = layer.type
    out["color"] = layer.color
    if sublayer is not None:
        out["thickness"] = layer.subLayers[sublayer].thickness
        out["material"] = layer.subLayers[sublayer].material
        out["epsilon"] = layer.subLayers[sublayer].epsilonR
        out["lossTangent"] = layer.subLayers[sublayer].lossTangent
    else:
        out["thickness"] = layer.thickness
        out["material"] = layer.material
        out["epsilon"] = layer.epsilonR
        out["lossTangent"] = layer.lossTangent

    return out


def save_json(obj: Any, filename: str) -> None:
    """Saves object as json to file"""
    log.info("Saving stackup information as json: %s", filename)
    with open(filename, "w", encoding="utf-8") as file_handle:
        obj["format_version"] = "1.0"
        json.dump(obj, file_handle)


def save_csv(stackup: Any, filename: str) -> None:
    """Saves stackup as csv"""
    log.info("Saving stackup information as csv: %s", filename)
    with open(filename, "w", encoding="utf-8") as file_handle:
        csv_writer = csv.writer(file_handle, delimiter=";")
        csv_writer.writerow(["Name", "Type", "Material", "Thickness[mm]", "Constant"])
        for layer in stackup:
            csv_writer.writerow(
                [
                    layer["name"],
                    layer["type"],
                    layer["material"],
                    layer["thickness"],
                    layer["epsilon"],
                ]
            )
