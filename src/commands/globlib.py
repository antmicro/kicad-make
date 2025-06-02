#!/usr/bin/python3

import argparse
import logging
import os
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple, Union

from kiutils.board import Board
from kiutils.footprint import Footprint
from kiutils.items.schitems import SchematicSymbol
from kiutils.schematic import Schematic
from kiutils.symbol import Symbol, SymbolLib

from common.kicad_project import KicadProject
from common.kmake_helper import get_property, set_property
from .prettify import run as prettify

log = logging.getLogger(__name__)

UniSymbol = Union[SchematicSymbol, Symbol]


class SymbolEntry:
    def __init__(self, symbol: Symbol, library_name: str) -> None:
        self.symbol: Symbol = symbol
        self.library_name: str = library_name


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    globlib_parser = subparsers.add_parser("globlib", help="Link symbols and footprints to global libraries.")
    globlib_parser.add_argument(
        "--include-kicad-lib",
        action="store_true",
        help="Use also KiCad official libraries (if installed).",
    )
    globlib_parser.add_argument(
        "--exclude-pcb",
        action="store_true",
        help="Do not propagate footprint links from schematic to PCB",
    )
    globlib_parser.add_argument(
        "--update-all",
        action="store_true",
        help="Include symbols that already link to global libraries",
    )
    globlib_parser.add_argument(
        "--update-properties",
        action="store_true",
        help="Update all properties of symbols/footprints based on global library",
    )
    globlib_parser.add_argument(
        "-s",
        "--sch",
        action="store",
        nargs="*",
        help="Specify list of schematic files to update, this option also enables --exclude-pcb",
        type=Path,
    )
    globlib_parser.set_defaults(func=run)


def run(kicad_project: KicadProject, args: argparse.Namespace) -> None:
    if args.sch is not None:
        args.exclude_pcb = True
    globlib_project(kicad_project, args)


def get_lib_mapping(
    ki_pro: KicadProject, include_kicad_lib: bool, lib_table_file: str, system_table_file: str, lib_dir: str
) -> Dict[str, str]:
    """Returns dict mapping symbol library names to paths based on user's kicad config."""
    libtable = ki_pro.read_lib_table_file(lib_table_file, system_table_file)

    if not include_kicad_lib:  # if not using original KiCad libraries, remove them from list
        libtable.libs = [lib for lib in libtable.libs if lib_dir not in lib.uri]

    # Sort so that kicad libaries are last
    libtable.libs = sorted(libtable.libs, key=lambda x: lib_dir not in x.uri, reverse=True)

    ki_pro.load_kicad_environ_vars()
    return {lib.name: os.path.expandvars(lib.uri) for lib in libtable.libs}


def get_symbol_name(symbol: UniSymbol) -> str:
    symbol_name = symbol.libId.split(":", 1)
    if len(symbol_name) == 1:
        return symbol.libId
    return symbol_name[1]


def get_global_symbol_list(lib_mapping: Dict[str, str]) -> Dict[str, Tuple[str, UniSymbol]]:
    sym_list: dict[str, Tuple[str, UniSymbol]] = {}
    for lib_name, path in lib_mapping.items():
        if not os.path.exists(path):
            log.warning(f"Library {lib_name} points to file that does not exist. Library will be omitted.")
            continue
        sym_library = SymbolLib.from_file(path)
        log.debug(f"Parsing global library: {lib_name}")
        for symbol in sym_library.symbols:
            sym_name = get_symbol_name(symbol)
            sym_list[sym_name] = (lib_name, symbol)
    return sym_list


def get_global_footprint_list(lib_mapping: Dict[str, str]) -> Dict[str, Tuple[str, Footprint]]:
    fp_list: dict[str, Tuple[str, Footprint]] = {}
    for lib_name, path in lib_mapping.items():
        if not os.path.exists(path):
            log.warning(f"Library {lib_name} points to file that does not exist. Library will be omitted.")
            continue
        log.debug(f"Parsing global library: {lib_name}")
        for file in os.scandir(path):
            if not file.is_file():
                continue
            if not file.name.endswith(".kicad_mod"):
                continue
            name = file.name.removesuffix(".kicad_mod")
            fp_list[name] = (lib_name, Footprint.from_file(file.path))
    return fp_list


def search_by_mpn(
    local_symbol: UniSymbol,
    global_symbols: Dict[str, Tuple[str, UniSymbol]],
) -> Optional[Tuple[str, UniSymbol]]:
    local_mpn = get_property(local_symbol, "MPN")
    local_name = get_symbol_name(local_symbol)

    if local_mpn is None or local_mpn == "":
        log.warning("Symbol: %s has no mpn to match.", local_name)
        return None

    matching_symbols: List[Tuple[str, UniSymbol]] = []

    for _, (global_lib_name, global_symbol) in global_symbols.items():
        global_mpn = get_property(global_symbol, "MPN")
        if global_mpn is not None and global_mpn == local_mpn:
            matching_symbols.append((global_lib_name, global_symbol))

    if not matching_symbols:
        log.warning("Symbol: %s not found in global libraries.", local_name)
        return None

    if len(matching_symbols) >= 2:
        log.warning(
            "Multiple replacements found for symbol named: %s with MPN: %s",
            local_name,
            local_mpn,
        )
        return None

    return matching_symbols[0]


def update_props(
    local_symbol: UniSymbol,
    global_symbol: UniSymbol,
    global_lib: str,
    all_props: bool,
) -> None:
    local_symbol.libId = f"{global_lib}:{global_symbol.libId}"
    for global_property in global_symbol.properties:
        for local_property in local_symbol.properties:
            if local_property.key == "Reference":
                continue
            if (local_property.key != "Footprint") and not all_props:
                continue
            if local_property.key == global_property.key:
                local_property.value = global_property.value


def get_sch_paths_based_on_args(args: argparse.Namespace, ki_pro: KicadProject) -> List[Path]:
    schematic_paths = [Path(file).resolve() for file in ki_pro.all_sch_files]
    if args.sch is not None:
        whitelist = [file.resolve() for file in args.sch]
        schematic_paths = [path for path in schematic_paths if path in whitelist]
    return schematic_paths


def find_global_symbol(
    local_symbol: UniSymbol, global_symbols: dict[str, Tuple[str, UniSymbol]]
) -> Optional[Tuple[str, UniSymbol]]:
    local_symbol_name = get_symbol_name(local_symbol)
    log.debug("Processing symbol: %s", local_symbol_name)

    if local_symbol_name in global_symbols:
        global_symbol_name = local_symbol_name
        global_symbol_lib = global_symbols[global_symbol_name][0]
        global_symbol = global_symbols[global_symbol_name][1]
        log.debug("Symbol with name: %s found in global library: %s", global_symbol_name, global_symbol_lib)
    else:
        result = search_by_mpn(local_symbol, global_symbols)
        if result is not None:
            global_symbol_lib, global_symbol = result
            log.debug("Symbol with libId: %s found in global library by MPN", local_symbol.libId)
        else:
            log.warning("Symbol with libId: %s wasn't found in global library", local_symbol.libId)
            return None

    return global_symbol_lib, global_symbol


def should_symbol_be_globlibed(symbol: UniSymbol, global_libraries: Iterable[str], update_all: bool) -> bool:
    split = symbol.libId.split(":")
    if len(split) <= 1:  # If there is no : in libId, symbol is locally edited and shouldn't be globlibed
        return False
    if split[0] in global_libraries and not update_all:
        return False
    return True


def globlib_project_symbols(ki_pro: KicadProject, args: argparse.Namespace) -> list[UniSymbol]:
    library_mapping = get_lib_mapping(
        ki_pro,
        args.include_kicad_lib,
        ki_pro.glob_sym_lib_table_path,
        ki_pro.system_sym_lib_table,
        ki_pro.env_var_name_sym_lib,
    )
    log.debug("Libary name to path mapping: %s", library_mapping)

    log.info("Generating global symbol list.")
    global_symbols = get_global_symbol_list(library_mapping)

    failures: list[UniSymbol] = []

    for schematic_path in get_sch_paths_based_on_args(args, ki_pro):
        log.info("Processing schematic: %s", schematic_path)
        schematic = Schematic().from_file(str(schematic_path))

        for local_symbol in schematic.schematicSymbols:
            if not should_symbol_be_globlibed(local_symbol, library_mapping.keys(), args.update_all):
                continue
            result = find_global_symbol(local_symbol, global_symbols)
            if result is None:
                failures.append(local_symbol)
                continue
            update_props(local_symbol, result[1], result[0], args.update_properties)

        for local_symbol in schematic.libSymbols:
            if not should_symbol_be_globlibed(local_symbol, library_mapping.keys(), args.update_all):
                continue
            result = find_global_symbol(local_symbol, global_symbols)
            if result is None:
                failures.append(local_symbol)
                continue
            update_props(local_symbol, result[1], result[0], args.update_properties)

        schematic.to_file()
    return failures


def update_fp_props(source: SchematicSymbol, ref: str, fp: Footprint, update_all: bool) -> Tuple[bool, bool]:
    changed = False
    if get_property(fp, "Reference") != ref:
        return (False, False)
    ofp = fp.libId
    nfp = get_property(source, "Footprint")
    fp.libId = nfp
    if nfp != ofp:
        log.debug("Changed %s footprint: %s -> %s", ref, ofp, nfp)
        changed = True
    if update_all:
        for sch_prop in source.properties:
            set_property(fp, sch_prop.key, sch_prop.value)

    return (True, changed)


def globlib_footprints(ki_pro: KicadProject, args: argparse.Namespace) -> None:
    changes = 0
    log.info("Loading Footprints ...")
    lib_mapping = get_lib_mapping(
        ki_pro,
        args.include_kicad_lib,
        ki_pro.glob_fp_lib_table_path,
        ki_pro.system_fp_lib_table,
        ki_pro.env_var_name_fp_lib,
    )
    fp_list = get_global_footprint_list(lib_mapping)
    log.info("Loading PCB ...")
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
            ref = get_property(schematic_symbol, "Reference")
            log.debug("Processing:  %s", ref)
            for fp in pcb.footprints:
                (found, changed) = update_fp_props(schematic_symbol, ref, fp, args.update_properties)
                if changed:
                    changes += 1
                if found:
                    break
    # bellow iteration has 2 purposes: 1. to globlib footprints that are not in schematic; 2. to update 3D model links
    for fp in pcb.footprints:
        for globname, (globlib, globfp) in fp_list.items():
            if globname != fp.entryName:
                continue
            if fp.libraryNickname not in lib_mapping:
                changes += 1
                fp.libId = globlib + ":" + globname
            fp.models = globfp.models
    pcb.to_file()
    log.info("Footprint links updated: %d", changes)


def globlib_project(kicad_project: KicadProject, args: argparse.Namespace) -> None:
    log.info("Start restoring links to global libraries.")
    failures = globlib_project_symbols(kicad_project, args)
    if not args.exclude_pcb:
        globlib_footprints(kicad_project, args)
    prettify(kicad_project, argparse.Namespace())

    if not failures:
        log.info("All links in symbols were updated successfully.")
        log.info("Use “rm -rf ./lib” to remove local libs")
    else:
        log.error("There were %i failures while finding global symbols.", len(failures))
