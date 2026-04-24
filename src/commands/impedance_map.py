from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path

from askiff.board import LayerDef, Via
from askiff.common_pcb import Layer, LayerCopper

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

    if not pro.pcb_root:
        raise RuntimeError("PCB file not found in project!")

    log.info("Loading PCB")

    net_classes: list[NetClass] = NetClass.load_net_classes(j)

    log.info("Processing board items")
    last_layer_id = int(
        max(
            [
                (layer.layer.order_id() - 2) / 2
                for layer in pro.pcb_root.layer_map
                if isinstance(layer.layer, LayerCopper)
            ]
        )
    )
    impedance_layers = {}

    for net_class in net_classes:
        if not net_class.impedance:
            continue
        if net_class.impedance not in impedance_layers:
            last_layer_id += 1
            target_layer = Layer.CU_IN(last_layer_id)
            impedance_layers[net_class.impedance] = target_layer
            pro.pcb_root.layer_map.append(LayerDef(target_layer, user_name=net_class.impedance))
        else:
            target_layer = impedance_layers[net_class.impedance]

        for trace in pro.pcb_root.traces:
            if isinstance(trace, Via):
                continue
            if not net_class.contains(trace.net.name):
                print(trace.net.name)
                continue

            trace.layer = target_layer

    layer_keys = impedance_layers.values()
    pro.pcb_root.traces = [i for i in pro.pcb_root.traces if not isinstance(i, Via) and i.layer in layer_keys]
    pro.pcb_root.footprints = []
    pro.pcb_root.zones = []
    pro.pcb_root.graphic_items = [item for item in pro.pcb_root.graphic_items if item.layer == Layer.EDGE_CUTS]

    log.info("Saving the generated impedance map")
    pro.doc_fab.mkdir(exist_ok=True, parents=True)
    pcb_file = pro.fab_dir / "impedance_map.kicad_pcb"
    pro.pcb_root.to_file(pcb_file)

    log.info("Plotting gerbers")
    output_folder = pro.fab_dir / "impedance_maps"

    export_impedance_gerbers(pcb_file, output_folder)
    log.info(f"Impedance maps have been generated, gerbers are located at {output_folder}")
    log.warning(
        "Support for impedance maps is experimental, please manually check if"
        "the content of generated gerbers is correct"
    )


def export_impedance_gerbers(pcb_file: Path, output_folder: Path) -> None:
    output_folder.mkdir(exist_ok=True)
    gerber_export_cli_command = [
        "pcb",
        "export",
        "gerbers",
        pcb_file,
        "-o",
        output_folder,
        "--no-protel-ext",
        "--precision",
        "6",
    ]
    run_kicad_cli(gerber_export_cli_command, True)

    for gerber_file in output_folder.glob("*.gbr"):
        if "ohm" not in gerber_file.stem.lower():
            gerber_file.unlink()


class NetClass:
    def __init__(self, class_json: dict, patterns: list) -> None:
        self.name = class_json["name"]
        self.patterns = [pattern["pattern"] for pattern in patterns if pattern["netclass"] == self.name]
        self.impedance: str | None = self.name.split("_")[0] if "ohm" in self.name.lower() else None
        self.nets: set[str] = set()
        self.nets_not_matching: set[str] = set()

        logging.debug(f"Patterns in class {self.name}: {self.patterns}")

    def __repr__(self) -> str:
        return self.name

    @staticmethod
    def load_net_classes(project_json: dict) -> list[NetClass]:
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

    def contains(self, net: str) -> bool:
        if net in self.nets:
            return True

        if net in self.nets_not_matching:
            return False

        if any([re.match(pattern, net) for pattern in self.patterns]):
            self.nets.add(net)
            return True

        self.nets_not_matching.add(net)
        return False
