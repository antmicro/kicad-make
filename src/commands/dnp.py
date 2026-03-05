import argparse
import logging
from typing import List
import sys

from kiutils.board import Board
from kiutils.footprint import Footprint
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
    parser.add_argument(
        "-rp",
        "--remove-dnp-paste",
        dest="no_paste",
        action="store_true",
        help="Remove solder paste from DNP components footprints.",
    )
    parser.add_argument(
        "-sp",
        "--restore-dnp-paste",
        dest="set_paste",
        action="store_true",
        help="Restore solder paste on DNP components footprints.",
    )
    parser.add_argument(
        "-atp",
        "--add-tht-paste",
        dest="set_tht_paste",
        action="store_true",
        help="Add solder paste on THT components footprints.",
    )
    parser.add_argument(
        "-rtp",
        "--restore-tht-paste",
        dest="reset_tht_paste",
        action="store_true",
        help="Restore no solder paste on THT components footprints.",
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
    assert not (
        args.no_paste and args.set_paste
    ), "Only one of [`--remove-dnp-paste`, `--restore-dnp-paste`] can be specified"
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
    update_dnp_on_pcb(sym_dnp, pcb, args.no_paste, args.set_paste, args.set_tht_paste, args.reset_tht_paste)
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
def update_dnp_on_pcb(
    references: List[str],
    board: Board,
    remove_paste: bool,
    restore_paste: bool,
    tht_paste_add: bool,
    tht_paste_restore: bool,
) -> None:
    if restore_paste:
        log.info("Restoring solder paste on DNP components")
    if remove_paste:
        log.info("Removing solder paste from DNP components")
    for footprint in board.footprints:
        if tht_paste_add:
            add_tht_paste(footprint)
        if tht_paste_restore:
            remove_tht_paste(footprint)
        set_fp_dnp_state(footprint, get_property(footprint, "Reference") in references, remove_paste, restore_paste)


# Updates footprint to have dnp field
def set_fp_dnp_state(footprint: Footprint, dnp_state: bool, remove_paste: bool, restore_paste: bool) -> None:
    if not footprint.attributes.boardOnly and footprint.attributes.dnp != dnp_state:
        footprint.attributes.dnp = dnp_state
        log.debug(f"Setting {get_property(footprint, 'Reference')} DNP to: {dnp_state}")
    if remove_paste and dnp_state:
        remove_fp_paste(footprint)
    if restore_paste:
        restore_fp_paste(footprint)


# Moves solder paste pads to `User.6` and `User.7` layers
def remove_fp_paste(footprint: Footprint) -> None:
    log.debug(f"Removing paste from {get_property(footprint, 'Reference')}")
    for pad in footprint.pads:
        if "*.Paste" in pad.layers:
            add_pad_layer(pad.layers, "User.6")
            add_pad_layer(pad.layers, "User.7")
            pad.layers.remove("*.Paste")
        else:
            if "F.Paste" in pad.layers:
                add_pad_layer(pad.layers, "User.6")
                pad.layers.remove("F.Paste")
            if "B.Paste" in pad.layers:
                add_pad_layer(pad.layers, "User.7")
                pad.layers.remove("B.Paste")


# Restores all solder paste pads moved to `User.6` and `User.7` layers
def restore_fp_paste(footprint: Footprint) -> None:
    changed = 0

    for pad in footprint.pads:
        if "User.6" in pad.layers and "User.7" in pad.layers:
            add_pad_layer(pad.layers, "*.Paste")
            pad.layers.remove("User.6")
            pad.layers.remove("User.7")
            changed += 1
        else:
            if "User.6" in pad.layers:
                add_pad_layer(pad.layers, "F.Paste")
                pad.layers.remove("User.6")
                changed += 1
            if "User.7" in pad.layers:
                add_pad_layer(pad.layers, "B.Paste")
                pad.layers.remove("User.7")
                changed += 1
    if changed:
        log.debug(f"Restored solder paste on {get_property(footprint, 'Reference')}")


# Sets pads of THT components to have solder paste on pads
def add_tht_paste(footprint: Footprint) -> None:
    changed = 0
    if footprint.attributes.type != "through_hole":
        return
    for pad in footprint.pads:
        if pad.type != "thru_hole":
            continue
        if "*.Cu" in pad.layers and not any(
            ["*.Paste" in pad.layers, "F.Paste" in pad.layers, "B.Paste" in pad.layers]
        ):
            add_pad_layer(pad.layers, "*.Paste")
            add_pad_layer(pad.layers, "User.3")
            add_pad_layer(pad.layers, "User.4")
            changed += 1
        elif "F.Cu" in pad.layers and "F.Paste" not in pad.layers:
            add_pad_layer(pad.layers, "F.Paste")
            add_pad_layer(pad.layers, "User.3")
            changed += 1
        elif "B.Cu" in pad.layers and "B.Paste" not in pad.layers:
            add_pad_layer(pad.layers, "B.Paste")
            add_pad_layer(pad.layers, "User.4")
            changed += 1

    if changed != 0:
        log.debug(f"Added solder paste on THT pads of {get_property(footprint, 'Reference')}")


# Remove solder paste from pads of THT components
def remove_tht_paste(footprint: Footprint) -> None:
    changed = 0
    if footprint.attributes.type != "through_hole":
        return
    for pad in footprint.pads:
        if pad.type != "thru_hole":
            continue
        if "User.3" in pad.layers and "User.4" in pad.layers:
            remove_pad_layers(pad.layers, ["User.3", "User.4", "*.Paste"])
            changed += 1
        elif "User.3" in pad.layers:
            remove_pad_layers(pad.layers, ["User.3", "F.Paste"])
            changed += 1
        elif "User.4" in pad.layers:
            remove_pad_layers(pad.layers, ["User.4", "B.Paste"])
            changed += 1

    if changed != 0:
        log.debug(f"Removed solder paste from THT pads of {get_property(footprint, 'Reference')}")


def add_pad_layer(lis: List[str], add: str) -> None:
    if add not in lis:
        lis.append(add)


def remove_pad_layers(lis: List[str], remove: List[str]) -> None:
    for layer in remove:
        if layer in lis:
            lis.remove(layer)
