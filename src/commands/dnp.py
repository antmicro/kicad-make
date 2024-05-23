import argparse
import logging
from typing import List

import kiutils.items
import kiutils.schematic
from kiutils.items.schitems import SchematicSymbol

from common.kicad_project import KicadProject
from common.kmake_helper import get_property, import_pcbnew

pcbnew = import_pcbnew()

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
    parser.set_defaults(func=run)


def run(kicad_project: KicadProject, args: argparse.Namespace) -> None:
    # Read in all schematic files
    schematics = []
    for sch_file in kicad_project.all_sch_files:
        schematics.append(kiutils.schematic.Schematic.from_file(sch_file))

    # Get all components that are marked DNP
    components = get_dnp_components(schematics)
    log.debug(f"Found {len(components)} schematic components marked DNP")

    # Count components that need cleanup
    cleanup_count = sum(needs_cleanup(component) for component in components)
    cleanup_list = [get_property(comp.properties, "Reference").value for comp in components if needs_cleanup(comp)]
    if cleanup_count > 0 and args.list_broken:
        log.warn(
            f"There are {cleanup_count} schematic components that "
            f'have their DNP properties malformed: [{" ".join(cleanup_list)}].'
        )
    elif cleanup_count > 0:
        log.info(f"There are {cleanup_count} schematic components that have their DNP properties malformed")
        log.debug(f"[{' '.join(cleanup_list)}]")
        # Cleanup components
        log.info("Cleaning up schematic components")
        for component in components:
            clean_up_component(component)

        # Save all changes to schematic files
        log.debug("Saving all schematic changes to file")
        for schematic in schematics:
            schematic.to_file()

    # Get references
    log.debug("Searching for components on PCB")
    references = []
    for component in components:
        references.append(get_property(component.properties, "Reference").value)

    # Update PCB footprints
    log.debug("Updating PCB")

    board = pcbnew.LoadBoard(kicad_project.pcb_file)
    update_pcb(references, board, args.no_paste, args.set_paste)
    pcbnew.SaveBoard(kicad_project.pcb_file, board, True)


def get_dnp_components(schematics: kiutils.schematic) -> List[SchematicSymbol]:
    components = []
    for schematic in schematics:
        for symbol in schematic.schematicSymbols:
            if is_dnp(symbol):
                components.append(symbol)
    return components


# Checks whether component is DNP based on DNP property and attribute
def is_dnp(component: SchematicSymbol) -> bool:
    dnp_property = get_property(component.properties, "DNP", names_in=["dnp"])

    if component.dnp:
        return True

    if dnp_property is not None and dnp_property.value not in [None, "", "~"]:
        return True

    return False


# Checks whether component needs cleanup
def needs_cleanup(component: SchematicSymbol) -> bool:
    if not component.dnp:
        return True
    if component.inBom:
        return True
    prop = get_property(component.properties, "DNP", names_in=["dnp"])
    if prop is None:
        return True
    if prop.key != "DNP":
        return True
    if prop.value != "DNP":
        return True
    if prop.effects.hide:
        return True
    return False


# Cleans up component - sets dnp, inBom, DNP property
def clean_up_component(component: SchematicSymbol) -> None:
    component.dnp = True
    component.inBom = False

    prop = get_property(component.properties, "DNP", names_in=["dnp"])
    if prop is None:
        prop = kiutils.items.common.Property()
        component.properties.append(prop)
    if prop.effects is None:
        prop.effects = kiutils.items.common.Effects()

    prop.key = "DNP"
    prop.value = "DNP"
    prop.effects.hide = False


# Updates footprints on pcb
def update_pcb(references: List[str], board: pcbnew.BOARD, dnp_remove_paste: bool, dnp_restore_paste: bool) -> None:  # type: ignore
    if dnp_restore_paste:
        log.info("Restoring solder paste on DNP components")
        restore_paste(board)
    if dnp_remove_paste:
        log.info("Removing solder paste from DNP components")

    for footprint in board.Footprints():
        if footprint.GetReference() in references:
            update_footprint(footprint, dnp_remove_paste)


# Updates footprint to have dnp field and appropriate attributes
def update_footprint(footprint: pcbnew.FOOTPRINT, remove_paste: bool) -> None:  # type: ignore
    footprint.SetProperty("DNP", "DNP")
    attrs = footprint.GetAttributes()
    attrs = attrs | pcbnew.FP_EXCLUDE_FROM_BOM
    attrs = attrs | pcbnew.FP_EXCLUDE_FROM_POS_FILES
    footprint.SetAttributes(attrs)

    if remove_paste:
        remove_paste_from_footprint(footprint)


# Moves solder paste pads to User_6 and User_7 layers
def remove_paste_from_footprint(footprint: pcbnew.FOOTPRINT) -> None:  # type: ignore
    log.debug(f"Removing paste from {footprint.GetReference()}")

    for pad in footprint.Pads():
        pad_mask = pad.GetLayerSet()

        if pad_mask.Contains(pcbnew.F_Paste):
            pad_mask.AddLayer(pcbnew.User_6)
            pad_mask.RemoveLayer(pcbnew.F_Paste)

        if pad_mask.Contains(pcbnew.B_Paste):
            pad_mask.AddLayer(pcbnew.User_7)
            pad_mask.RemoveLayer(pcbnew.B_Paste)

        pad.SetLayerSet(pad_mask)


# Restores all solder paste pads moved to User_1 and User_2
def restore_paste(board: pcbnew.BOARD):  # type: ignore
    for footprint in board.GetFootprints():
        log.debug(f"Restoring solder paste on {footprint.GetReference()}")

        for pad in footprint.Pads():
            pad_mask = pad.GetLayerSet()

            if pad_mask.Contains(pcbnew.User_6):
                pad_mask.AddLayer(pcbnew.F_Paste)
                pad_mask.RemoveLayer(pcbnew.User_6)

            if pad_mask.Contains(pcbnew.User_7):
                pad_mask.AddLayer(pcbnew.B_Paste)
                pad_mask.RemoveLayer(pcbnew.User_7)

            pad.SetLayerSet(pad_mask)
