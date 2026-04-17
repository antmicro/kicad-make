"""Command for exporting stackup information from kicad's PCB file"""

import argparse
import csv
import json
import logging
import os
from typing import Any
from pathlib import Path
import enum

from askiff.board import Board, StackupLayer, LayerDef, StackupLayerDielectricSubLayer
from common.kicad_project import KicadProject

log = logging.getLogger(__name__)

# Minor version should be with any changes to format.
# Major only when breaking changes are implemented
FORMAT_VERSION = "1.0"
FILENAME = "stackup"
DEF_KEYS = ["name", "type", "color", "material", "thickness", "epsilon_r", "loss_tangent", "user_name"]


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


def get_layerdef(layer: StackupLayer, layer_map: list[LayerDef]) -> LayerDef | None:
    """Get LayerDef from board's LayerMap corresponding to passed StackupLayer."""

    for lm_layer in layer_map:
        if layer.layer == lm_layer.layer:
            return lm_layer
    return None


def get_layer_dict(layer: StackupLayer | StackupLayerDielectricSubLayer) -> dict[str, str | float | None]:
    """Convert StackupLayer object to a dictionary"""

    layer_dict = dict.fromkeys(DEF_KEYS, None)
    for key, val in layer.__dict__.items():
        if key not in DEF_KEYS:
            continue
        layer_dict[key] = val

    return layer_dict


def get_name(layer: StackupLayer) -> str:
    """Get layer name"""
    if isinstance(layer.layer, enum.Enum):
        return layer.layer.value
    return layer.layer


def run(pro: KicadProject, args: argparse.Namespace) -> None:
    """Run stackup-export command"""

    board = Board().from_file(Path(pro.pcb_file))
    if not board.setup.stackup:
        raise RuntimeError("Stackup is not set for the project, open the PCB design and save it to update it.")

    layer_dicts = []
    for layer in board.setup.stackup.layers:
        layerdef = get_layerdef(layer, board.layer_map)
        name = get_name(layer)
        if hasattr(layer, "sublayers"):  # handle layer with sublayers (dielectrics)
            for idx, sublayer in enumerate(layer.sublayers):
                sublayer_dict = {k: v for (k, v) in get_layer_dict(sublayer).items() if v}
                layer_dict = get_layer_dict(layer) | sublayer_dict  # type: ignore
                layer_dict["name"] = f"{name} ({idx + 1}/{len(layer.sublayers)})" if len(layer.sublayers) > 1 else name
                layer_dict["user_name"] = layerdef.user_name if layerdef else None
                layer_dicts.append(layer_dict)

        else:  # handle layer without sublayers
            layer_dict = get_layer_dict(layer)
            layer_dict["name"] = name
            layer_dict["user_name"] = layerdef.user_name if layerdef else None
            layer_dicts.append(layer_dict)

    pro.create_fab_dir()

    if args.legacy_csv:
        save_csv(
            layer_dicts,
            (args.output_filename if args.output_filename else os.path.join(pro.relative_fab_path, FILENAME + ".csv")),
        )
    else:
        save_json(
            {"layers": layer_dicts},
            (args.output_filename if args.output_filename else os.path.join(pro.relative_fab_path, FILENAME + ".json")),
        )


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
        csv_writer.writerow(["Name", "Type", "Material", "Thickness[mm]", "Constant", "User-Name"])
        for layer in stackup:
            csv_writer.writerow(
                [
                    layer["name"],
                    layer["type"],
                    layer["material"],
                    layer["thickness"],
                    layer["epsilon_r"],
                    layer.get("user-name", layer["name"]),
                ]
            )
