import argparse
import csv
import logging
import os
import sys
import dataclasses
from typing_extensions import Self
from typing import TextIO, Dict, List, Tuple

import kicad_netlist_reader

from common.kicad_project import KicadProject
from common.kmake_helper import run_kicad_cli

log = logging.getLogger(__name__)


@dataclasses.dataclass
class ComponentGroup:
    refs: list[str]
    value: str
    mpn: str
    manufacturer: str
    description: str
    footprint: str
    dnp: bool

    def quantity(self) -> int:
        return len(self.refs)

    @classmethod
    def from_component(cls, c: kicad_netlist_reader.comp) -> Self:
        footprint = c.getFootprint()
        if ":" in footprint:
            footprint = c.getFootprint().split(":")[1]
        dnp = c.getField("DNP") == "DNP"
        return cls(
            refs=[c.getRef()],
            value=c.getValue(),
            mpn=c.getField("MPN"),
            manufacturer=c.getField("Manufacturer"),
            description=c.getDescription(),
            footprint=footprint,
            dnp=dnp,
        )

    def has_same_fields(self, other: Self) -> bool:
        if self.value != other.value:
            logging.debug("Compared components have different value: %s and %s", self.value, other.value)
            return False
        if self.mpn != other.mpn:
            logging.debug("Compared components have different mpn: %s and %s", self.mpn, other.mpn)
            return False
        if self.manufacturer != other.manufacturer:
            logging.debug(
                "Compared components have different manufacturer: %s and %s", self.manufacturer, other.manufacturer
            )
            return False
        if self.description != other.description:
            logging.debug(
                "Compared components have different description: %s and %s", self.description, other.description
            )
            return False
        if self.footprint != other.footprint:
            logging.debug("Compared components have different footprint: %s and %s", self.footprint, other.footprint)
            return False
        return True

    def is_blacklisted(self) -> bool:
        if any("TP" in ref for ref in self.refs):
            return True
        if any("MP" in ref for ref in self.refs):
            return True
        if any(ref is None for ref in self.refs):
            return True

        return False


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "bom",
        help="Generate Bill-of-Materials (BOM)",
        description="Generate Bill-of-Materials (BOM). Include ONLY populated components by default."
        "Default format is `default` ."
        "None of the options include blacklisted components unless `--no-ignore` flag is passed.",
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument("-d", "--dnp", action="store_true", help="Include ONLY DNP components.")
    group.add_argument("-a", "--all", action="store_true", help="Include populated and DNP components.")

    parser.add_argument("--no-ignore", action="store_true", help="Don't ignore blacklisted components.")

    parser.add_argument(
        "--format",
        choices=["default", "CircuitHub"],
        default="default",
        help="Select which format to use for output.",
    )
    parser.set_defaults(func=run)


def run(kicad_project: KicadProject, args: argparse.Namespace) -> None:
    log.info("Exporting netlist from project")
    net = create_netlist(kicad_project, "kicadxml", args.debug)

    log.info("Parsing netlist")
    groups, ok = parse_netlist(net)

    if not args.no_ignore:
        groups = [group for group in groups if not group.is_blacklisted()]

    kind = "ALL"
    if not args.all:
        if not args.dnp:
            groups = [group for group in groups if not group.dnp]
            kind = "populated"
        else:
            groups = [group for group in groups if group.dnp]
            kind = "DNP"

    if args.format == "default":
        filename = f"{kicad_project.doc_dir}/{kicad_project.name}-BOM-{kind}.csv"
    else:
        filename = f"{kicad_project.doc_dir}/{kicad_project.name}-BOM-{kind}-{args.format}.csv"

    log.info("Saving BOM to file")
    with open(filename, "w", encoding="utf-8") as f:
        if args.format == "default":
            write_default(f, groups)
        elif args.format == "CircuitHub":
            write_circuithub(f, groups)

    log.info("Saved BOM to file")

    if not ok:
        sys.exit(1)


def write_default(output_file: TextIO, groups: list[ComponentGroup]) -> None:
    writer = csv.writer(output_file, lineterminator="\n", delimiter=",", quotechar='"', quoting=csv.QUOTE_ALL)
    writer.writerow(["Reference", "Quantity", "Value", "Footprint", "Manufacturer", "MPN"])
    for group in groups:
        writer.writerow(
            [" ".join(group.refs), group.quantity(), group.value, group.footprint, group.manufacturer, group.mpn]
        )


def write_circuithub(output_file: TextIO, groups: list[ComponentGroup]) -> None:
    writer = csv.writer(output_file, lineterminator="\n", delimiter=",", quotechar='"', quoting=csv.QUOTE_ALL)
    writer.writerow(["reference designator", "manufacturer", "mpn", "fitted", "description", "quantity"])
    for group in groups:
        for ref in group.refs:
            writer.writerow([ref, group.manufacturer, group.mpn, not group.dnp, group.description, 1])


def parse_netlist(net: kicad_netlist_reader.netlist) -> Tuple[List[ComponentGroup], bool]:
    groups: list[ComponentGroup] = []

    mismatched: Dict[str, List[str]] = {}

    for group in net.groupComponents():
        dnp_refs: list[str] = []
        populate_refs: list[str] = []

        example_component = ComponentGroup.from_component(group[0])

        for component in group:
            # TODO: Take Do-not-populate property into account
            if component.getField("DNP") == "DNP":
                dnp_refs.append(component.getRef())
            else:
                populate_refs.append(component.getRef())
            converted_component = ComponentGroup.from_component(component)
            if not converted_component.has_same_fields(example_component):
                mismatched[example_component.refs[0]] = mismatched.get(example_component.refs[0], []) + [
                    converted_component.refs[0]
                ]
        if populate_refs:
            groups.append(dataclasses.replace(example_component, refs=populate_refs, dnp=False))
        if dnp_refs:
            groups.append(dataclasses.replace(example_component, refs=dnp_refs, dnp=True))

    print_mismatched(mismatched)

    return groups, len(mismatched.keys()) <= 0


def print_mismatched(mismatched: Dict[str, List[str]]) -> None:
    if not len(mismatched.keys()) > 0:
        return
    logging.error("There were components that have mismatched fields.")
    count = 0
    for key, value in mismatched.items():
        logging.error("%s doesn't match: %s", key, value)
        count += len(value)
    logging.error("In total there were %i mismatched components", count)


def create_netlist(
    kicad_project: KicadProject, output_format: str = "kicadsexpr", debug: bool = False
) -> kicad_netlist_reader.netlist:
    assert output_format in ["kicadsexpr", "kicadxml", "cadstar", "cadstar", "orcadpcb2", "spice", "spicemodel"]

    kicad_project.create_doc_dir()
    filename = f"{kicad_project.doc_dir}/netlist"

    command = "sch export netlist"
    command += f" --format {output_format}"
    command += f" {kicad_project.sch_root} -o {filename}"

    log.info("Generating netlist file: %s", filename)
    run_kicad_cli(command.split(), debug)

    net = kicad_netlist_reader.netlist(filename)

    if not debug:
        os.remove(filename)

    return net
