from askiff.symbol import SymbolSchematic
import argparse
import logging
import sys
from dataclasses import dataclass
import itertools
import re

from askiff import Board, Project, Schematic
from askiff.footprint import Footprint

log = logging.getLogger(__name__)


@dataclass
class PropSet:
    dnp: bool
    in_bom: bool
    variant: list[str]


def get_sch_prop(schematics: list[Schematic]) -> dict[str, PropSet]:
    sheet_prop = {}
    for sch in schematics:
        for sheet in sch.sheets:
            sheet_prop[sheet.uuid] = PropSet(
                sheet.dnp or False,
                sheet.in_bom or False,
                list(
                    itertools.chain.from_iterable(
                        [re.split(r"[,;\s]", p.value) for p in sheet.properties if p.name == "Variant"]
                    )
                ),
            )
    return sheet_prop


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "dnp",
        help="Fix discrepancies in DNP between schematic symbols and footprints.",
    )
    parser.add_argument(
        "-l",
        "--list-broken",
        dest="list_broken",
        action="store_true",
        help="list malformed DNP schematic components. list discrepancies between PCB and SCH. Do not modify.",
    )
    parser.add_argument(
        "-f",
        "--fix-legacy",
        dest="fix_legacy",
        action="store_true",
        help="Fix symbols and footprints with legacy DNP property fields.",
    )
    parser.set_defaults(func=run)


def cleanup_sch(malformed_components: list[SymbolSchematic]) -> None:
    # Cleanup components
    log.info(f"Fixing legacy schematic component{'s' if len(malformed_components) != 1 else ''}")
    for component in malformed_components:
        clean_up_component(component)


# Remove from PCB footprints additional properties doubling checkboxes functionality
def cleanup_pcb(pcb: Board) -> None:
    log.info("Fixing legacy PCB components")
    for fp in pcb.footprints:
        for prop in ["DNP", "dnp"]:
            fp.properties.pop(prop)


def run(pro: Project, args: argparse.Namespace) -> None:
    # Read in all schematic files
    if args.list_broken and args.fix_legacy:
        raise RuntimeError("Only one of [`--list-broken`, `--fix-legacy`] can be specified")

    broken_logs: list[str] = []

    # Get all components that are marked DNP
    dnp_components = get_dnp_components(pro)
    log.debug(f"Found {len(dnp_components)} schematic component{'s' if len(dnp_components) != 1 else ''} marked DNP")

    # Count components that need cleanup
    cleanup_list = get_cleanup_components(pro)
    cleanup_count = len(cleanup_list)

    if cleanup_count:
        log_text = (
            f"Malformed DNP propert{'ies' if cleanup_count != 1 else 'y'} found in "
            f"{cleanup_count} schematic component{'s' if cleanup_count != 1 else ''}: "
            f"{' '.join([comp.properties.ref.value for comp in cleanup_list])}."
        )

        if args.list_broken:
            broken_logs.append(log_text)
        else:
            log.warning(log_text)

        if args.fix_legacy:
            cleanup_sch(cleanup_list)
        else:
            if args.list_broken:
                broken_logs.append("Use `kmake dnp --fix-legacy` to fix schematics.")
            else:
                log.warning("Use `kmake dnp --fix-legacy` to fix schematics.")

    # Get symbol references from schematics
    sym_dnp = []
    log.debug("Collecting all symbol references in schematics.")
    for sym in dnp_components:
        sym_dnp.append(sym.properties.ref.value)
        for instance in sym.instances:
            for project_instances in sym.instances:
                if project_instances.project_name != pro.project_name:
                    continue
                for instance in project_instances.instances:
                    if instance.reference not in sym_dnp:
                        sym_dnp.append(instance.reference)

    sheet_prop = get_sch_prop(pro.sch)  # ty:ignore[invalid-argument-type]
    # resolve sheet level dnp
    for schematic in pro.sch:
        for symbol in schematic.symbols:
            for project_instances in symbol.instances:
                if project_instances.project_name != pro.project_name:
                    continue
                for instance in project_instances.instances:
                    if instance.reference.startswith("#"):
                        continue
                    if instance.reference not in sym_dnp and any(
                        [uid in instance.path and prop.dnp for uid, prop in sheet_prop.items()]
                    ):
                        sym_dnp.append(instance.reference)
    log.debug(f"DNP references from schematic: {' '.join(sorted(sym_dnp))}")

    pcb = pro.pcb_root
    fp_dnp = find_dnp_footprints_on_pcb(pcb)

    if args.list_broken:
        for sym in sym_dnp:
            if sym not in fp_dnp:
                broken_logs.append(f"Component {sym} marked as DNP only in schematics")
        for fp_ref in fp_dnp:
            if fp_ref not in sym_dnp:
                broken_logs.append(f"Component {fp_ref} marked as DNP only in PCB")

        # Check additional properties doubling checkboxes functionality
        for fp in pcb.footprints:
            value_prop = fp.properties.get("Value")
            short_name = f"{fp.properties.ref.value}: {value_prop.value if value_prop else ''}"

            if fp.attributes.exclude_from_bom:
                broken_logs.append(f"Footprint {short_name} has an additional 'Exclude from BOM' attribute set")
            if fp.attributes.exclude_from_pos_files:
                broken_logs.append(
                    f"Footprint {short_name} has an additional 'Exclude from position files' attribute set"
                )
            if fp.properties.get("DNP"):
                broken_logs.append(f"Footprint {short_name} has an additional 'DNP' property set")
        for text in broken_logs:
            log.warning(text)
        if broken_logs:
            sys.exit(1)
        sys.exit(0)

    # Update PCB footprints
    log.debug("Updating PCB")
    if args.fix_legacy:
        cleanup_pcb(pcb)
    update_dnp_on_pcb(sym_dnp, pcb)
    pro.save()


def get_dnp_components(pro: Project) -> list[SymbolSchematic]:
    components = []
    for schematic in pro.sch:
        components.extend([symbol for symbol in schematic.schematicSymbols if is_dnp(symbol)])
    return components


def get_cleanup_components(pro: Project) -> list[SymbolSchematic]:
    components = []
    for schematic in pro.sch:
        for comp in schematic.schematicSymbols:
            if comp.properties.get("DNP") is not None:
                components.append(comp)
    return components


# Checks whether component is DNP based on DNP property and attribute
def is_dnp(component: SymbolSchematic) -> bool:
    if component.dnp or component.properties.get_value("DNP") not in [None, "", "~"]:
        return True
    return False


# Cleans up component - sets DNP attribute and removes legacy DNP property
def clean_up_component(component: SymbolSchematic) -> None:
    dnp_field = component.properties.pop("DNP")
    if dnp_field is None:
        return
    if dnp_field.value not in [None, "", "~"]:
        component.dnp = True


# Find footprints set as DNP
def find_dnp_footprints_on_pcb(board: Board) -> list[str]:
    fp_dnp = []
    for fp in board.footprints:
        if fp.attributes.dnp and not fp.attributes.board_only:
            fp_dnp.append(fp.properties.ref.value)
    return fp_dnp


# Updates DNP property on PCB footprints
def update_dnp_on_pcb(
    references: list[str],
    board: Board,
) -> None:
    for footprint in board.footprints:
        set_fp_dnp_state(footprint, footprint.properties.ref.value in references)


# Updates footprint to have dnp field
def set_fp_dnp_state(footprint: Footprint, dnp_state: bool) -> None:
    if not footprint.attributes.board_only and footprint.attributes.dnp != dnp_state:
        footprint.attributes.dnp = dnp_state
        log.debug(f"Setting {footprint.properties.ref.value} DNP to: {dnp_state}")
