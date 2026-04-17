import argparse
import glob
import json
import logging
import os
import re
from typing import Dict, List
from pathlib import Path

from askiff.board import Board, Via
from askiff.common_pcb import Net

from common.kicad_project import KicadProject
from common.kmake_helper import run_kicad_cli

log = logging.getLogger(__name__)


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    impedance_parser = subparsers.add_parser("impedance", help="Generate impedance maps in Gerber format.")
    impedance_parser.set_defaults(func=run)


def run(pro: KicadProject, args: argparse._SubParsersAction) -> None:
    log.info("Loading net classes from project file")

    with open(pro.kicad_pro_path) as f:
        j = json.load(f)

    if not pro.pcb_file:
        log.error("PCB file was not detected or does not exists")
        return

    log.info("Loading PCB")

    board = Board.from_file(Path(pro.pcb_file))
    net_classes: list[NetClass] = NetClass.load_net_classes(j)

    log.info("Processing board items")
    max([layer.layer.order_id() for layer in board.layer_map if ".Cu" in layer.layer.value])

    # Mark non-impedance controlled traces for removal
    # for item in board.traces:
    #     item.dirty = True

    for net_class in net_classes:
        if not net_class.impedance:
            continue

        target_layer = net_class.impedance

        # if target_layer is None:
        #     board.layer_map.append(Layer(last_cu_id, f"In{last_cu_id}.Cu"))
        #     layers[net_class.impedance] = last_cu_id
        #     target_layer = last_cu_id
        #     last_cu_id += 1
        for trace in board.traces:
            # print(item.net)

            if not net_class.contains(trace.net):
                continue
            if isinstance(trace, Via):
                continue

            trace.layers = [f"In{target_layer}.Cu"]

    board.traceItems = [i for i in board.traces if not i.dirty]
    board.footprints = []
    board.zones = []

    log.info("Saving the generated impedance map")
    pro.create_fab_dir()
    pcb_file = os.path.join(pro.fab_dir, "impedance_map.kicad_pcb")
    board.to_file(Path(pcb_file))

    log.info("Plotting gerbers")
    output_folder = Path(pro.fab_dir) / "impedance_maps"

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
        self.patterns = [pattern["pattern"] for pattern in patterns if pattern["netclass"] == self.name]
        self.impedance: int | None = self.name.split("_")[0] if "ohm-" in self.name.lower() else None

        logging.debug(f"Patterns in class {self.name}: {self.patterns}")

    def __repr__(self) -> str:
        return self.name

    @staticmethod
    def load_net_classes(project_json: Dict) -> List["NetClass"]:
        classes_json = project_json["net_settings"]["classes"]
        try:
            classes_patterns = project_json["net_settings"]["netclass_patterns"]
        except KeyError:
            log.error("Failed to parse the project file, only KiCAD8+ projects are supported")
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

    def contains(self, net: Net) -> bool:
        try:
            return any([re.match(pattern, net.name) for pattern in self.patterns])
        except TypeError:
            return False
