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
    """
    Data class for storing components group

    Attributes:
        refs: list of reference designators
        value: content of the `value` field
        mpn: content of `mpn` field (manufacturer part number)
        description: content of component description
        footprint: footprint assigned to component
        dnp: is component marked as dnp (do not populate)
    """

    refs: list[str]
    value: str
    mpn: str
    manufacturer: str
    description: str
    footprint: str
    dnp: bool

    def quantity(self) -> int:
        """
        Return quantity of components in group
        """
        return len(self.refs)

    @classmethod
    def from_component(cls, c: kicad_netlist_reader.comp) -> Self:
        """
        Generate ComponentGroup from component
        """
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
        """
        Check if fields of components are the same as other component

        Tested fields:
            - value
            - mpn
            - manufacturer
            - description
        """

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
        """
        Check if component is blacklisted

        Blacklisted components:
            - components with `TP` designator (testpoints)
            - components with `MP` designator (mounting pads)
            - components without designator
        """
        if any("TP" in ref for ref in self.refs):
            return True
        if any("MP" in ref for ref in self.refs):
            return True
        if any(ref is None for ref in self.refs):
            return True

        return False


@dataclasses.dataclass
class ValidHeaders:
    """
    Data class with valid headers

    Attributes:
        reference: valid headers for reference designators column
        quantity: valid headers for quantity column
        value: valid headers for value column
        footprint: valid headers for footprint column
        mpn: valid header for manufacturer part number  column
        dnp: valid header for do not populate column
        description: valid header for description column
    """

    reference = ["Reference Designators", "Reference"]
    quantity = ["Quantity"]
    value = ["Value"]
    footprint = ["Footprint"]
    manufacturer = ["Manufacturer"]
    mpn = ["Manufacturer Part Number", "MPN"]
    dnp = ["DNP"]
    description = ["Description"]

    default_fields = ["Reference", "Quantity", "Value", "Footprint", "Manufacturer", "MPN"]

    def get_all_headers(self) -> list[str]:
        """
        Return all valid headers
        """
        return (
            self.reference
            + self.quantity
            + self.value
            + self.footprint
            + self.manufacturer
            + self.mpn
            + self.dnp
            + self.description
        )


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Create kmake bom subparser"""

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
        "--fields",
        nargs="+",
        help=f"""
        Change BoM field. Available fields: {" ".join(ValidHeaders().get_all_headers())}.
        When not provided default setup is selected ({" ".join(ValidHeaders().default_fields)})""",
    )
    parser.add_argument(
        "-g",
        "--group-references",
        action="store_false",
        default=True,
        help="Group references of components into single line",
    )
    parser.add_argument("-o", "--output", help="Output file name")
    parser.set_defaults(func=run)


def run(kicad_project: KicadProject, args: argparse.Namespace) -> None:
    """Main kamke bom method"""

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

    if args.output:
        filename = f"{kicad_project.dir}/{args.output}"
    else:
        if args.group_references:
            filename = f"{kicad_project.doc_dir}/{kicad_project.name}-BOM-{kind}.csv"
        else:
            log.info("Using grouped references")
            filename = f"{kicad_project.doc_dir}/{kicad_project.name}-BOM-{kind}-ReferenceNotGrouped.csv"

    log.info(f"BoM file {filename}")

    if args.fields is None:
        log.info("Using default BoM preset")
        headers = ValidHeaders().default_fields
    else:
        headers = args.fields

    log.info("Saving BoM to file")

    with open(filename, "w", encoding="utf-8") as f:
        save_csv(f, groups, headers, args.group_references)

    log.info("Saved BOM to file")

    if not ok:
        sys.exit(1)


def save_csv(output_file: TextIO, groups: list[ComponentGroup], headers: list[str], group_references: bool) -> None:
    """Save header and components to BoM file"""

    writer = csv.writer(output_file, lineterminator="\n", delimiter=",", quotechar='"', quoting=csv.QUOTE_ALL)

    writer.writerow(headers)

    for group in groups:
        if group_references:
            writer.writerow(prepare_csv_row(group, headers, " ".join(group.refs), group.quantity()))
        else:
            for ref in group.refs:
                writer.writerow(prepare_csv_row(group, headers, ref))


def prepare_csv_row(components: ComponentGroup, headers: list[str], references: str = "", quantity: int = 1) -> list:
    """Generate single row for csv file"""

    line = []

    valid_headers = ValidHeaders()

    for header in headers:
        if header in valid_headers.reference:
            line.append(references)
        elif header in valid_headers.quantity:
            line.append(str(quantity))
        elif header in valid_headers.value:
            line.append(components.value)
        elif header in valid_headers.footprint:
            line.append(components.footprint)
        elif header in valid_headers.manufacturer:
            line.append(components.manufacturer)
        elif header in valid_headers.mpn:
            line.append(components.mpn)
        elif header in valid_headers.dnp:
            if components.dnp:
                line.append("DNP")
            else:
                line.append("")
        elif header in valid_headers.description:
            line.append(components.description)
        else:
            log.error(f"Invalid header {header}")
            exit(-1)
    return line


def parse_netlist(net: kicad_netlist_reader.netlist) -> Tuple[List[ComponentGroup], bool]:
    """Generate component groups from netlist"""

    groups: list[ComponentGroup] = []

    mismatched: Dict[str, List[str]] = {}

    legacy_dnp = []
    for group in net.groupComponents():
        dnp_refs: list[str] = []
        populate_refs: list[str] = []

        example_component = ComponentGroup.from_component(group[0])

        for component in group:
            if component.getField("DNP") == "DNP":
                dnp_refs.append(component.getRef())
                legacy_dnp.append(component.getRef())
            elif component.getDNP():
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
    if legacy_dnp:
        log.warning(str(len(legacy_dnp)) + " components use legacy DNP property:")
        log.warning(str(legacy_dnp))
        log.warning("Use `kmake dnp` to update them.")
    print_mismatched(mismatched)

    return groups, len(mismatched.keys()) <= 0


def print_mismatched(mismatched: Dict[str, List[str]]) -> None:
    """Print components with mismatched fields"""

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
    """Create netlist from KiCad project"""

    assert output_format in ["kicadsexpr", "kicadxml", "cadstar", "cadstar", "orcadpcb2", "spice", "spicemodel"]

    kicad_project.create_doc_dir()
    filename = f"{kicad_project.doc_dir}/netlist"
    command = [
        "sch",
        "export",
        "netlist",
        "--format",
        output_format,
        kicad_project.sch_root,
        "-o",
        filename,
    ]

    log.info("Generating netlist file: %s", filename)
    run_kicad_cli(command, debug)

    net = kicad_netlist_reader.netlist(filename)

    if not debug:
        os.remove(filename)

    return net
