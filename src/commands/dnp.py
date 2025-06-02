import argparse
import logging
from typing import List

import kiutils.items
import kiutils.schematic
from kiutils.board import Board
from kiutils.footprint import Footprint
from kiutils.items.schitems import SchematicSymbol
from kiutils.schematic import Schematic

from common.kicad_project import KicadProject
from common.kmake_helper import get_property, remove_property
from .prettify import run as prettify

log = logging.getLogger(__name__)


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "dnp",
        help="Fix discrepancies between DNP, `exclude-from-bom` and"
        " `exclude-from-board` atributes in schematic symbols and footprints.",
    )
    parser.add_argument(
        "-l",
        "--list-broken",
        dest="list_broken",
        action="store_true",
        help="List references of malformed DNP schematic components, do not modify.",
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


def run(kicad_project: KicadProject, args: argparse.Namespace) -> None:
    # Read in all schematic files
    assert not (
        args.no_paste and args.set_paste
    ), "Only one of [`--remove-dnp-paste`, `--restore-dnp-paste`] can be specified"

    schematics = []
    for sch_file in kicad_project.all_sch_files:
        schematics.append(kiutils.schematic.Schematic.from_file(sch_file))

    # Get all components that are marked DNP
    dnp_components = get_dnp_components(schematics)
    log.debug(f"Found {len(dnp_components)} schematic components marked DNP")

    # Count components that need cleanup
    cleanup_count = sum(needs_cleanup(component) for component in dnp_components)
    cleanup_list = [get_property(comp, "Reference") for comp in dnp_components if needs_cleanup(comp)]
    if cleanup_count > 0 and args.list_broken:
        log.warning(
            f"There are {cleanup_count} schematic components that "
            f'have their DNP properties malformed: [{" ".join(cleanup_list)}].'
        )
        return
    if cleanup_count > 0:
        log.info(f"There are {cleanup_count} schematic components that have their DNP properties malformed")
        log.debug(f"[{' '.join(cleanup_list)}]")
        # Cleanup components
        log.info("Cleaning up schematic components")
        for component in dnp_components:
            clean_up_component(component)

        # Save all changes to schematic files
        log.debug("Saving all schematic changes to file")
        for schematic in schematics:
            schematic.to_file()

    # Get references
    log.debug("Searching for components on PCB")
    references = []
    for component in dnp_components:
        references.append(get_property(component, "Reference"))
        for instance in component.instances:
            for path in instance.paths:
                if path.reference not in references:
                    references.append(path.reference)
    log.debug(f"DNP references from schematic {sorted(references)}")

    # Update PCB footprints
    log.debug("Updating PCB")

    pcb = Board().from_file(kicad_project.pcb_file)
    update_pcb(references, pcb, args.no_paste, args.set_paste, args.set_tht_paste, args.reset_tht_paste)
    pcb.to_file()

    prettify(kicad_project, argparse.Namespace())


def get_dnp_components(schematics: list[Schematic]) -> List[SchematicSymbol]:
    components = []
    for schematic in schematics:
        for symbol in schematic.schematicSymbols:
            if is_dnp(symbol):
                components.append(symbol)
    return components


# Checks whether component is DNP based on DNP property and attribute
def is_dnp(component: SchematicSymbol) -> bool:
    dnp_property = get_property(component, "DNP")

    if component.dnp:
        return True

    if dnp_property not in [None, "", "~"]:
        return True

    return False


# Checks whether component needs cleanup
def needs_cleanup(component: SchematicSymbol) -> bool:
    if not component.dnp:
        return True
    if component.inBom:
        return True
    prop = get_property(component, "DNP")
    if prop is not None:
        return True
    return False


# Cleans up component - sets dnp, inBom, DNP property
def clean_up_component(component: SchematicSymbol) -> None:
    component.dnp = True
    component.inBom = False
    # Replaces legacy DNP property with default kicad DNP checkbox
    prop = get_property(component, "DNP")
    if prop is not None:
        component.properties = remove_property(component, "DNP")


# Updates footprints on pcb
def update_pcb(
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
        if get_property(footprint, "Reference") in references:
            set_fp_dnp(footprint, remove_paste, restore_paste)
        elif not footprint.attributes.boardOnly and get_property(footprint, "MPN"):
            footprint.attributes.excludeFromPosFiles = False
            footprint.attributes.excludeFromBom = False
            footprint.attributes.dnp = False
            restore_fp_paste(footprint)
        # Remove additional properties doubling checkboxes functionality
        for prop in ["DNP", "dnp", "exclude_from_bom"]:
            footprint.properties = remove_property(footprint, prop)


# Updates footprint to have dnp field and appropriate attributes
def set_fp_dnp(footprint: Footprint, remove_paste: bool, restore_paste: bool) -> None:
    log.debug(f"Setting {get_property(footprint, 'Reference')} to DNP")
    footprint.attributes.excludeFromPosFiles = True
    footprint.attributes.excludeFromBom = True
    footprint.attributes.dnp = True
    if remove_paste:
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
    if footprint.attributes.type is None:
        return
    for pad in footprint.pads:
        if pad.type != "thru_hole":
            continue
        if "*.Cu" in pad.layers:
            add_pad_layer(pad.layers, "*.Paste")
            add_pad_layer(pad.layers, "User.3")
            add_pad_layer(pad.layers, "User.4")
            changed += 1
        else:
            if "F.Cu" in pad.layers:
                add_pad_layer(pad.layers, "F.Paste")
                add_pad_layer(pad.layers, "User.3")
            if "B.Cu" in pad.layers:
                add_pad_layer(pad.layers, "B.Paste")
                add_pad_layer(pad.layers, "User.4")

    if changed != 0:
        log.debug(f"Added solder paste on THT pins of {get_property(footprint, 'Reference')}")


# Remove solder paste from pads of THT components
def remove_tht_paste(footprint: Footprint) -> None:
    changed = 0
    if footprint.attributes.type is None:
        return
    for pad in footprint.pads:
        if pad.type != "thru_hole":
            continue
        if "User.3" in pad.layers and "User.4" in pad.layers:
            remove_pad_layers(pad.layers, ["User.3", "User.4", "*.Paste", "User.6", "User.7"])
            changed += 1
        else:
            if "User.3" in pad.layers:
                remove_pad_layers(pad.layers, ["User.3", "F.Paste", "User.6"])
                changed += 1
            if "User.4" in pad.layers:
                remove_pad_layers(pad.layers, ["User.4", "B.Paste", "User.7"])
                changed += 1

    if changed != 0:
        log.debug(f"Removed solder paste from THT pins of {get_property(footprint, 'Reference')}")


def add_pad_layer(lis: List[str], add: str) -> None:
    if add not in lis:
        lis.append(add)


def remove_pad_layers(lis: List[str], remove: List[str]) -> None:
    for layer in remove:
        if layer in lis:
            lis.remove(layer)
