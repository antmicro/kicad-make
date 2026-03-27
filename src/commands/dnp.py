import argparse
import logging
from typing import List
import sys

from kiutils.board import Board
from kiutils.items.schitems import SchematicSymbol

from common.kicad_project import KicadProject, SchProject
from common.kmake_helper import get_property, remove_property
from .prettify import run as prettify

log = logging.getLogger(__name__)


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
        help="List malformed DNP schematic components. List discrepancies between PCB and SCH. Do not modify.",
    )
    parser.add_argument(
        "-f",
        "--fix-legacy",
        dest="fix_legacy",
        action="store_true",
        help="Fix symbols and footprints with legacy DNP property fields.",
    )
    parser.set_defaults(func=run)


def cleanup_sch(schpro: SchProject, malformed_components: List[SchematicSymbol]) -> None:
    # Cleanup components
    log.info(f"Fixing legacy schematic component{'s' if len(malformed_components) != 1 else ''}")
    for component in malformed_components:
        clean_up_component(component)
    schpro.save()


# Remove from PCB footprints additional properties doubling checkboxes functionality
def cleanup_pcb(pcb: Board) -> None:
    log.info("Fixing legacy PCB components")
    for fp in pcb.footprints:
        for prop in ["DNP", "dnp"]:
            fp.properties = remove_property(fp, prop)


def run(kicad_project: KicadProject, args: argparse.Namespace) -> None:
    # Read in all schematic files
    assert not (args.list_broken and args.fix_legacy), "Only one of [`--list-broken`, `--fix-legacy`] can be specified"

    broken_logs: list[str] = []
    schpro = kicad_project.sch_project()

    # Get all components that are marked DNP
    dnp_components = get_dnp_components(schpro)
    log.debug(f"Found {len(dnp_components)} schematic component{'s' if len(dnp_components) != 1 else ''} marked DNP")

    # Count components that need cleanup
    cleanup_list = get_cleanup_components(schpro)
    cleanup_count = len(cleanup_list)
    if cleanup_count:
        log_text = (
            f"Malformed DNP propert{'ies' if cleanup_count != 1 else 'y'} found in "
            f"{cleanup_count} schematic component{'s' if cleanup_count != 1 else ''}: "
            f"{' '.join([get_property(comp,'Reference') for comp in cleanup_list])}."
        )
        if args.list_broken:
            broken_logs.append(log_text)
        else:
            log.warning(log_text)
        if args.fix_legacy:
            cleanup_sch(schpro, cleanup_list)
        else:
            if args.list_broken:
                broken_logs.append("Use `kmake dnp --fix-legacy` to fix schematics.")
            else:
                log.warning("Use `kmake dnp --fix-legacy` to fix schematics.")

    # Get symbol references from schematics
    sym_dnp = []
    log.debug("Collecting all symbol references in schematics.")
    for sym in dnp_components:
        sym_dnp.append(get_property(sym, "Reference"))
        for instance in sym.instances:
            for path in instance.paths:
                if path.reference not in sym_dnp:
                    sym_dnp.append(path.reference)
    # resolve sheet level dnp
    for schematic in schpro.schematics:
        for symbol in schematic.schematicSymbols:
            for instance in symbol.instances:
                for path in instance.paths:
                    if path.reference.startswith("#"):
                        continue
                    if path.reference not in sym_dnp and any(
                        [uid in path.sheetInstancePath and prop.dnp for uid, prop in schpro.sheet_prop.items()]
                    ):
                        sym_dnp.append(path.reference)
    log.debug(f"DNP references from schematic: {' '.join(sorted(sym_dnp))}")

    pcb = Board().from_file(kicad_project.pcb_file)
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
            short_name = f"{get_property(fp, 'Reference')}: {fp.entryName}"
            if fp.attributes.excludeFromBom:
                broken_logs.append(f"Footprint {short_name} has an additional 'Exclude from BOM' attribute set")
            if fp.attributes.excludeFromPosFiles:
                broken_logs.append(
                    f"Footprint {short_name} has an additional 'Exclude from position files' attribute set"
                )
            if get_property(fp, "DNP"):
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
    pcb.to_file()
    prettify(kicad_project, argparse.Namespace())


def get_dnp_components(schpro: SchProject) -> List[SchematicSymbol]:
    components = []
    for schematic in schpro.schematics:
        components.extend([symbol for symbol in schematic.schematicSymbols if is_dnp(symbol)])
    return components


def get_cleanup_components(schpro: SchProject) -> List[SchematicSymbol]:
    components = []
    for schematic in schpro.schematics:
        for comp in schematic.schematicSymbols:
            if get_property(comp, "DNP") is not None:
                components.append(comp)
    return components


# Checks whether component is DNP based on DNP property and attribute
def is_dnp(component: SchematicSymbol) -> bool:
    if component.dnp or get_property(component, "DNP") not in [None, "", "~"]:
        return True
    return False


# Cleans up component - sets DNP attribute and removes legacy DNP property
def clean_up_component(component: SchematicSymbol) -> None:
    dnp_field = get_property(component, "DNP")
    if dnp_field is None:
        return
    component.properties = remove_property(component, "DNP")
    if dnp_field not in [None, "", "~"]:
        component.dnp = True


# Find footprints set as DNP
def find_dnp_footprints_on_pcb(board: Board) -> list[str]:
    fp_dnp = []
    for fp in board.footprints:
        if fp.attributes.dnp and not fp.attributes.boardOnly:
            fp_dnp.append(get_property(fp, "Reference"))
    return fp_dnp


# Updates DNP property on PCB footprints
def update_dnp_on_pcb(references: List[str], board: Board) -> None:
    for footprint in board.footprints:
        dnp_state = get_property(footprint, "Reference") in references
        if not footprint.attributes.boardOnly and footprint.attributes.dnp != dnp_state:
            footprint.attributes.dnp = dnp_state
            log.debug(f"Setting {get_property(footprint, 'Reference')} DNP to: {dnp_state}")
