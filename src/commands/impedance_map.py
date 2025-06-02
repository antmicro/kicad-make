import argparse
import glob
import json
import logging
import os
import re
from typing import Dict, List
from pathlib import Path

from kiutils.board import Board
from kiutils.items.brditems import LayerToken, Via

from common.kicad_project import KicadProject
from common.kmake_helper import run_kicad_cli

log = logging.getLogger(__name__)


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    impedance_parser = subparsers.add_parser("impedance", help="Generate impedance maps in Gerber format.")
    impedance_parser.set_defaults(func=run)


def run(kicad_project: KicadProject, args: argparse._SubParsersAction) -> None:
    log.info("Loading net classes from project file")
    with open(kicad_project.pro_file) as f:
        j = json.load(f)

    net_classes = NetClass.load_net_classes(j)

    if not len(kicad_project.pcb_file):
        log.error("PCB file was not detected or does not exists")
        return

    log.info("Loading PCB")
    board = Board.from_file(kicad_project.pcb_file)

    # Count number of copper layers
    copper_lcount = 0
    for layer in board.layers:
        if "Cu" in layer.name:
            copper_lcount += 1

    start_layer_id = copper_lcount - 1
    last_layer_id = start_layer_id

    layers: Dict[str, int] = {}

    log.info("Processing board items")
    # Mark non-impedance controlled traces for removal
    for item in board.traceItems:
        item.dirty = True

    for net_class in net_classes:
        net_impedance = net_class.name.split("_")[0]
        if "ohm-" not in net_impedance.lower():
            continue

        target_layer = layers.get(net_impedance)
        if target_layer is None:
            board.layers.append(LayerToken(last_layer_id, f"In{last_layer_id}.Cu", userName=net_impedance))
            layers[net_impedance] = last_layer_id
            target_layer = last_layer_id
            last_layer_id += 1

        nets = []
        for pattern in net_class.patterns:
            for net in board.nets:
                if re.match(pattern, net.name):
                    nets.append(net.number)

        for item in board.traceItems:
            if isinstance(item, Via):
                continue
            if item.net not in nets:
                continue

            item.layers = [f"In{target_layer}.Cu"]
            item.dirty = False

    board.traceItems = [i for i in board.traceItems if not i.dirty]
    board.footprints = []
    board.zones = []

    log.info("Saving the generated impedance map")
    kicad_project.create_fab_dir()
    pcb_file = os.path.join(kicad_project.fab_dir, "impedance_map.kicad_pcb")
    board.to_file(pcb_file)

    log.info("Plotting gerbers")
    output_folder = Path(kicad_project.fab_dir) / "impedance_maps"

    export_impedance_gerbers(pcb_file, output_folder)
    log.info(f"Impedance maps have been generated, gerbers are located at {output_folder}")
    log.warning(
        "Support for impedance maps is experimental, please manually check if"
        "the content of generated gerbers is correct"
    )


def export_impedance_gerbers(pcb_file: str, output_folder: Path) -> None:
    output_folder.mkdir(exist_ok=True)
    gerber_export_cli_command = [
        "pcb",
        "export",
        "gerbers",
        pcb_file,
        "-o",
        str(output_folder),
        "--precision",
        "6",
    ]
    run_kicad_cli(gerber_export_cli_command, True)

    for gerber_file in glob.glob(f"{output_folder}/*.g*"):
        gerber_name, _ = os.path.splitext(gerber_file)
        if "Ohm" in gerber_name:
            os.rename(gerber_file, f"{gerber_name}.gbr")
        else:
            os.remove(gerber_file)


class NetClass:
    def __init__(self, class_json: Dict, patterns: List) -> None:
        self.name = class_json["name"]

        self.patterns = []
        for pattern in patterns:
            if pattern["netclass"] == self.name:
                self.patterns.append(pattern["pattern"])

        logging.debug(f"Patterns in class {self.name}: {self.patterns}")

    def __repr__(self) -> str:
        return self.name

    @staticmethod
    def load_net_classes(project_json: Dict) -> List["NetClass"]:
        classes_json = project_json["net_settings"]["classes"]
        try:
            classes_patterns = project_json["net_settings"]["netclass_patterns"]
        except KeyError:
            log.error("Failed to parse the project file, only KiCAD8 projects are supported")
            exit(1)

        for pattern in classes_patterns:
            # normalize KiCad wildcard patterns to python regex
            pattern["pattern"] = (
                pattern["pattern"]
                .replace(r"{", r"\{")
                .replace(r"}", r"\}")
                .replace(r".", r"\.")
                .replace(r"*", r".*")
                .replace(r"?", r".?")
                .replace(r"+", r"\+")
            )

        net_classes = []
        for class_json in classes_json:
            net_classes.append(NetClass(class_json, classes_patterns))
        return net_classes
