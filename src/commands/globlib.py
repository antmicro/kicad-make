#!/usr/bin/python3
import argparse
import json
import logging
import os
from typing import Dict, List, Tuple

from kiutils.items.common import Property
from kiutils.items.schitems import SchematicSymbol
from kiutils.items.fpitems import FpText
from kiutils.libraries import LibTable
from kiutils.schematic import Schematic

from kiutils.board import Board
from kiutils.symbol import SymbolLib

from common.kicad_project import KicadProject
from common.kmake_helper import get_property, set_property

log = logging.getLogger(__name__)


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    globlib_parser = subparsers.add_parser("globlib", help="Link symbols and footprints to global libraries.")
    globlib_parser.add_argument(
        "-a",
        "--all",
        action="store_true",
        help="Use also KiCad official libraries (if installed).",
    )
    globlib_parser.add_argument(
        "-s", "--sch", action="store", nargs="*", help="Specify list of schematic files to update."
    )
    globlib_parser.add_argument(
        "--exclude-pcb",
        action="store_false",
        help="Do not propagate footprint links from schematic to PCB.",
    )
    globlib_parser.set_defaults(func=run)


def run(kicad_project: KicadProject, args: argparse.Namespace) -> None:
    globlib_project(kicad_project, args)


def get_sym_lib_mapping(args: argparse.Namespace) -> Dict[str, str]:
    libtable = LibTable.from_file(os.path.expanduser("~/.config/kicad/7.0/sym-lib-table"))
    if not args.all:  # if not using original KiCad libraries, remove them from list
        libtable.libs = [lib for lib in libtable.libs if "${KICAD7_SYMBOL_DIR}" not in lib.uri]
    else:
        libtable.libs = sorted(libtable.libs, key=lambda x: "${KICAD7_SYMBOL_DIR}" not in x.uri, reverse=True)
    with open(os.path.expanduser("~/.config/kicad/7.0/kicad_common.json"), encoding="utf-8") as kicad_conf:
        for envvar, val in json.load(kicad_conf)["environment"]["vars"].items():
            os.environ[envvar] = val
    os.environ["KIPRJMOD"] = os.path.abspath(".")
    return {lib.name: os.path.expandvars(lib.uri) for lib in libtable.libs}


def get_symbol_name(schematic_symbol: SchematicSymbol) -> str:
    symbol_name = schematic_symbol.libId.split(":", 1)
    if len(symbol_name) == 1:
        return schematic_symbol.libId
    return symbol_name[1]


def get_schematic_symbol_name(schematic_symbol: SchematicSymbol) -> str:
    symbol_name = schematic_symbol.libId.split(":", 1)
    if len(symbol_name) == 1:
        return schematic_symbol.libId
    return symbol_name[1]


def get_global_symbol_list(lib_mapping: Dict[str, str]) -> Dict[str, List[str]]:
    sym_list = dict()
    for lib in lib_mapping:
        lib_name = lib
        path = lib_mapping[lib_name]
        if not os.path.exists(path):
            log.warning(f"Library {lib_name} indicates file that does not exist. Library will be omitted.")
            continue
        sym_library = SymbolLib.from_file(path)
        log.debug(f"Parsing global library: {lib_name}")
        for sym in sym_library.symbols:
            try:
                sym_name = sym.libId.split(":")[1]
            except IndexError:
                sym_name = sym.libId
            # sym_list.update({sym_name: [lib_name, sym]})
            sym_list.update(
                {
                    sym_name: [
                        lib_name,
                        get_property(sym.properties, "Footprint").value,
                        get_property(sym.properties, "MPN"),
                    ]
                }
            )
            log.debug(f"Found symbol: {sym_name}")
    return sym_list


def add_to_failed_list(
    schematic_symbol: SchematicSymbol,
    failures: Dict[str, List[str]],
) -> None:
    if schematic_symbol.libId not in failures:  # if symbol still not added to failures list, add it
        failed_compnent = {
            schematic_symbol.libId: [
                get_property(schematic_symbol.properties, "Footprint").value,
                get_property(schematic_symbol.properties, "Reference").value,
            ]
        }
        failures.update(failed_compnent)  # add to failure list
    else:
        failures[schematic_symbol.libId].append(get_property(schematic_symbol.properties, "Reference").value)


def fallback_search(
    schematic_symbol: SchematicSymbol,
    symbol_name: str,
    global_symbols: Dict[str, List[str]],
    renames: Dict[str, str],
    failures: Dict[str, List[str]],
) -> Tuple[bool, str]:
    mpn = get_property(schematic_symbol.properties, "MPN")

    matching_symbol_names: List[str] = []

    if mpn is None:
        return False, symbol_name

    for sym_name, sym_prop in global_symbols.items():
        sym_property: Property = sym_prop[2]
        if sym_property is None:
            continue
        if not isinstance(sym_property, Property):
            continue
        if sym_property.value == mpn.value:
            matching_symbol_names.append(sym_name)

    if not len(matching_symbol_names):
        log.warning("Symbol: %s not found in global libraries. Added to failure list.", symbol_name)
        add_to_failed_list(schematic_symbol, failures)
        return False, symbol_name

    if len(matching_symbol_names) >= 2:
        log.warning(
            "Multiple replacements found for %s with same MPN %s",
            symbol_name,
            mpn.value,
        )
        add_to_failed_list(schematic_symbol, failures)
        return False, symbol_name

    new_symbol_name = matching_symbol_names[0]

    renames.update({symbol_name: new_symbol_name})

    log.info(
        "Symbol found using MPN - renaming: %s -> %s",
        symbol_name,
        new_symbol_name,
    )
    return True, new_symbol_name


def globlib_symbols(ki_pro: KicadProject, args: argparse.Namespace) -> int:
    library_mapping = get_sym_lib_mapping(args)
    log.debug("Mapping: %s", library_mapping)
    log.info("Generating global symbol list.")
    global_symbols = get_global_symbol_list(library_mapping)
    failures: Dict[str, List[str]] = dict()
    sym_instances_dict = dict()
    success_count = 0
    for schematic_path in ki_pro.all_sch_files:
        if args.sch is not None:
            schematic_name = schematic_path.replace(ki_pro.dir + "/", "")
            if schematic_name not in args.sch:
                continue
        log.info("Processing schematic: %s", schematic_path)
        schematic = Schematic().from_file(schematic_path)
        renames: Dict[str, str] = dict()
        for schematic_symbol in schematic.schematicSymbols:
            library = schematic_symbol.libId.split(":")[0]
            symbol_name = get_schematic_symbol_name(schematic_symbol)
            new_symbol_name = symbol_name
            if library is None:
                continue
            log.debug("Processing:  %s from lib: %s", symbol_name, library)
            if library not in library_mapping:  # if current library is not in global libraries
                if symbol_name not in global_symbols:  # if symbol name not found in global library
                    # if symbol can not be found by name, search by MPN
                    (found, new_symbol_name) = fallback_search(
                        schematic_symbol, symbol_name, global_symbols, renames, failures
                    )
                    if not found:
                        continue

                symbol_global_library_name = global_symbols[new_symbol_name][0]  # get global symbol library name
                symbol_global_library_path = library_mapping[symbol_global_library_name]
                log.debug("Symbol name: %s found in global library: %s", new_symbol_name, symbol_global_library_name)
                log.debug("Global library path: %s", symbol_global_library_path)
                schematic_symbol.libId = symbol_global_library_name + ":" + new_symbol_name
                new_fp = global_symbols[new_symbol_name][1]
                set_property(schematic_symbol, "Footprint", new_fp)
                sym_instances_dict.update({new_symbol_name: new_fp})
                success_count += 1

        log.info("Re-linking schematic lib symbols")
        loc_libsymbols = schematic.libSymbols  # library of symbols in schematic
        for symbol in loc_libsymbols:
            library = symbol.libId.split(":")[0]
            try:
                symbol_name = symbol.libId.split(":")[1]
            except IndexError:
                symbol_name = symbol.libId
            if library is None:
                continue
            if library not in library_mapping:  # if current library is not in global libraries
                new_symbol_name = symbol_name
                ren = False
                if symbol_name not in global_symbols:
                    if symbol_name in renames:
                        ren = True
                        new_symbol_name = renames[symbol_name]
                if ren or symbol_name in global_symbols:
                    for unit in symbol.units:
                        unit.libId = unit.libId.replace(symbol_name, new_symbol_name)
                    symbol_global_library_name = global_symbols[new_symbol_name][0]  # get global symbol library name
                    symbol.libId = symbol_global_library_name + ":" + new_symbol_name
                    new_fp = global_symbols[new_symbol_name][1]
                    set_property(symbol, "Footprint", new_fp)
        schematic.to_file()
    main_schematic = Schematic().from_file(os.path.abspath(ki_pro.sch_root))
    for sym_instance in main_schematic.symbolInstances:
        if sym_instance.value in sym_instances_dict:
            sym_instance.footprint = sym_instances_dict[sym_instance.value]
    main_schematic.to_file()
    # cleanup_schematic_lib_symbols(ki_pro)
    if len(failures) != 0:
        log.warning("List of symbols not found in global library:")
        for fail in failures:  # printing failures
            log.warning(f"{fail} \r\n\t\t   - fp  : {failures[fail][0]} \r\n\t\t   - ref : {failures[fail][1:]} ")
        log.warning(f"Failed to restore links: {len(failures)}")
    log.info(f"Successfully restored links: {success_count}")
    return len(failures)


def globlib_footprints(ki_pro: KicadProject, args: argparse.Namespace) -> None:
    changed = 0
    pcb = Board().from_file(ki_pro.pcb_file)
    log.info("Updating footprint links")
    for schematic_path in ki_pro.all_sch_files:
        if args.sch is not None:
            schematic_name = schematic_path.replace(ki_pro.dir + "/", "")
            if schematic_name not in args.sch:
                continue
        log.info("Processing schematic: %s", schematic_path)
        schematic = Schematic().from_file(schematic_path)
        for schematic_symbol in schematic.schematicSymbols:
            ref = get_property(schematic_symbol.properties, "Reference").value
            log.debug("Processing:  %s", ref)
            for fp in pcb.footprints:
                for item in fp.graphicItems:
                    if not isinstance(item, FpText):
                        continue
                    if item.type != "reference":
                        continue
                    if item.text == ref:
                        ofp = fp.libId
                        nfp = get_property(schematic_symbol.properties, "Footprint").value
                        fp.libId = nfp
                        if nfp != ofp:
                            log.debug("Changed %s footprint: %s -> %s", ref, ofp, nfp)
                            changed += 1
                        break  # breaks also from above loop
                else:
                    continue
                break
    pcb.to_file()
    log.info("Footprint links updated: %d", changed)


def globlib_project(kicad_project: KicadProject, args: argparse.Namespace) -> None:
    log.info("Start restoring links to global libraries.")
    failures_count = globlib_symbols(kicad_project, args)
    if args.exclude_pcb:
        globlib_footprints(kicad_project, args)
    if not failures_count:
        log.info("All links in symbols were updated successfully.")
        log.info("Use “rm -rf ./lib” to remove local libs")
