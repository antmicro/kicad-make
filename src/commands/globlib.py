import argparse
import logging
import os
import re
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Union

from askiff import FootprintFile, Project, Schematic, SymbolFile
from askiff.common import LibraryTable
from askiff.footprint import Footprint, FootprintLibraryTable, LibId
from askiff.pro import _LazyFile
from askiff.symbol import SymbolDefinition, SymbolLibraryTable, SymbolSchematic

from common.kicad_project import KicadProject

log = logging.getLogger(__name__)

Symbol = Union[SymbolDefinition, SymbolSchematic]


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


def run(pro: KicadProject, args: argparse.Namespace) -> None:
    if args.sch is not None:
        args.exclude_pcb = True
    globlib_project(pro, args)


def get_lib_table_path(name: Path, global_lib: Path) -> Path:
    if name.exists():
        log.debug(f"Using config from {name}")
        return name
    if global_lib.exists():
        log.warning(f"Provided lib table ({name}) doesn't exist. Using global lib table")
        return global_lib
    log.error("Provided lib table doesn't exist and couldn't find global lib table")
    sys.exit(1)


def get_lib_mapping(
    pro: KicadProject,
    include_kicad_lib: bool,
    lib_table_file: Path,
    system_table_file: Path,
    lib_dir: str,
    libcls: type[LibraryTable],
) -> dict[str, str]:
    """Returns dict mapping symbol library names to paths based on user's kicad config."""
    libtable = libcls.from_file(get_lib_table_path(lib_table_file, system_table_file))

    if not include_kicad_lib:  # if not using original KiCad libraries, remove them from list
        libtable.lib = [lib for lib in libtable.lib if lib_dir not in lib.uri]

    # Sort so that kicad libaries are last
    libtable.lib = sorted(libtable.lib, key=lambda x: lib_dir not in x.uri, reverse=True)

    pro.load_kicad_environ_vars()
    return {lib.name: os.path.expandvars(lib.uri) for lib in libtable.lib}


def get_global_symbol_list(lib_mapping: dict[str, str]) -> dict[str, tuple[str, SymbolDefinition]]:
    sym_list = {}
    for lib_name, path in lib_mapping.items():
        if not os.path.exists(path):
            log.warning(f"Library {lib_name} points to file that does not exist. Library will be omitted.")
            continue
        sym_library = SymbolFile.from_file(path)
        log.debug(f"Parsing global library: {lib_name}")
        for symbol in sym_library.symbols:
            sym_list[symbol.lib_id.name] = (lib_name, symbol)
    return sym_list


def get_global_footprint_list(lib_mapping: dict[str, str]) -> dict[str, tuple[str, Footprint]]:
    fp_list: dict[str, tuple[str, Footprint]] = {}
    for lib_name, path in lib_mapping.items():
        if not os.path.exists(path):
            log.warning(f"Library {lib_name} points to file that does not exist. Library will be omitted.")
            continue
        log.debug(f"Parsing global library: {lib_name}")
        for file in Path(path).glob("*" + FootprintFile.fs_ext):
            fp_list[file.stem] = (lib_name, _LazyFile(FootprintFile, file))  # ty:ignore[invalid-assignment]
    return fp_list


def normalize_mpn(mpn: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(mpn).lower()).strip("-")


def search_by_mpn(
    local_symbol: Symbol,
    global_symbols: dict[str, tuple[str, SymbolDefinition]],
) -> tuple[str, Symbol] | None:
    local_mpn = local_symbol.properties.get_value("MPN")

    if not local_mpn or local_mpn == "":
        log.warning("Symbol: %s has no mpn to match.", local_symbol.lib_id.name)
        return None

    matching_symbols: list[tuple[str, Symbol]] = []

    for _, (global_lib_name, global_symbol) in global_symbols.items():
        global_mpn = global_symbol.properties.get_value("MPN") or ""
        if not global_mpn and normalize_mpn(global_mpn) == normalize_mpn(local_mpn):
            matching_symbols.append((global_lib_name, global_symbol))

    if not matching_symbols:
        log.warning("Symbol: %s not found in global libraries.", local_symbol.lib_id.name)
        return None

    if len(matching_symbols) >= 2:
        log.warning(
            "Multiple replacements found for symbol named: %s with MPN: %s",
            local_symbol.lib_id.name,
            local_mpn,
        )
        return None

    return matching_symbols[0]


def update_props(
    local_symbol: Symbol,
    global_symbol: Symbol,
    global_lib: str,
    all_props: bool,
) -> None:
    local_symbol.lib_id.library = global_lib
    local_symbol.lib_id.name = global_symbol.lib_id.name
    for global_property in global_symbol.properties:
        for local_property in local_symbol.properties:
            if local_property.name == "Reference":
                continue
            if (local_property.name != "Footprint") and not all_props:
                continue
            if local_property.name == global_property.name:
                local_property.value = global_property.value


def get_sch_paths_based_on_args(args: argparse.Namespace, pro: Project) -> list[Schematic]:
    if args.sch is not None:
        return [sch for sch in pro.sch if sch.fs_path.name in args.sch]
    return pro.sch


def find_global_symbol(
    local_symbol: Symbol,
    global_symbols: dict[str, tuple[str, SymbolDefinition]],
) -> tuple[str, Symbol] | None:
    log.debug("Processing symbol: %s", local_symbol.lib_id.name)

    if local_symbol.lib_id.name in global_symbols:
        global_symbol_lib = global_symbols[local_symbol.lib_id.name][0]
        global_symbol = global_symbols[local_symbol.lib_id.name][1]
        log.debug("Symbol with name: %s found in global library: %s", local_symbol.lib_id.name, global_symbol_lib)
    else:
        result = search_by_mpn(local_symbol, global_symbols)
        if result is not None:
            global_symbol_lib, global_symbol = result
            log.debug("Symbol with lib_id: %s found in global library by MPN", local_symbol.lib_id)
        else:
            log.warning("Symbol with lib_id: %s wasn't found in global library", local_symbol.lib_id)
            return None

    return global_symbol_lib, global_symbol


def should_symbol_be_globlibed(symbol: Symbol, global_libraries: Iterable[str], update_all: bool) -> bool:
    if symbol.lib_id.library is None:  # If there is no : in lib_id, symbol is locally edited and shouldn't be globlibed
        return False
    if symbol.lib_id.library in global_libraries and not update_all:
        return False
    return True


def globlib_project_symbols(pro: KicadProject, args: argparse.Namespace) -> list[Symbol]:
    library_mapping = get_lib_mapping(
        pro,
        args.include_kicad_lib,
        pro.glob_sym_lib_table_path,
        pro.system_sym_lib_table,
        pro.env_var_name_sym_lib,
        SymbolLibraryTable,
    )
    log.debug("Libary name to path mapping: %s", library_mapping)

    log.info("Generating global symbol list.")
    global_symbols = get_global_symbol_list(library_mapping)

    failures: list[Symbol] = []

    for schematic in get_sch_paths_based_on_args(args, pro):
        log.info("Processing schematic: %s", schematic.fs_path)

        for local_symbol in schematic.symbols:
            if not should_symbol_be_globlibed(local_symbol, library_mapping.keys(), args.update_all):
                continue
            result = find_global_symbol(local_symbol, global_symbols)
            if result is None:
                failures.append(local_symbol)
                continue
            update_props(local_symbol, result[1], result[0], args.update_properties)

        for local_symbol in schematic.lib_symbols:
            if not should_symbol_be_globlibed(local_symbol, library_mapping.keys(), args.update_all):
                continue
            result = find_global_symbol(local_symbol, global_symbols)
            if result is None:
                failures.append(local_symbol)
                continue
            update_props(local_symbol, result[1], result[0], args.update_properties)

        schematic.to_file()
    return failures


def update_fp_props(source: SymbolSchematic, ref: str, fp: Footprint, update_all: bool) -> tuple[bool, bool]:
    changed = False
    if fp.properties.get("Reference") != ref:
        return (False, False)
    ofp = fp.lib_id
    nfp = source.properties.get_value("Footprint")
    fp.lib_id.name = nfp or ""
    if nfp != ofp:
        log.debug("Changed %s footprint: %s -> %s", ref, ofp, nfp)
        changed = True
    if update_all:
        for sch_prop in source.properties:
            fp.properties.set(sch_prop.name, sch_prop.value)

    return (True, changed)


def globlib_footprints(pro: KicadProject, args: argparse.Namespace) -> None:
    changes = 0
    log.info("Loading Footprints ...")
    lib_mapping = get_lib_mapping(
        pro,
        args.include_kicad_lib,
        pro.glob_fp_lib_table_path,
        pro.system_fp_lib_table,
        pro.env_var_name_fp_lib,
        FootprintLibraryTable,
    )
    fp_list = get_global_footprint_list(lib_mapping)
    log.info("Loading PCB ...")
    for pcb in pro.pcb:
        log.info("Updating footprint links")

        for schematic in get_sch_paths_based_on_args(args, pro):
            log.info("Processing schematic: %s", schematic.fs_path)
            for schematic_symbol in schematic.symbols:
                ref = schematic_symbol.properties.ref.value
                log.debug("Processing:  %s", ref)
                for fp in pcb.footprints:
                    (found, changed) = update_fp_props(schematic_symbol, ref, fp, args.update_properties)
                    if changed:
                        changes += 1
                    if found:
                        break

        # below iteration has 2 purposes: 1. to globlib footprints that are not in schematic; 2. to update 3D model link
        for fp in pcb.footprints:
            for globname, (globlib, globfp) in fp_list.items():
                if globname != fp.lib_id.name:
                    continue
                if fp.lib_id.library not in lib_mapping:
                    changes += 1
                    fp.lib_id = LibId(globlib, globname)
                fp.models = globfp.models
        pcb.to_file()
    log.info("Footprint links updated: %d", changes)


def globlib_project(pro: KicadProject, args: argparse.Namespace) -> None:
    log.info("Start restoring links to global libraries.")
    failures = globlib_project_symbols(pro, args)
    if not args.exclude_pcb:
        globlib_footprints(pro, args)

    if not failures:
        log.info("All links in symbols were updated successfully.")
        log.info("Use “rm -rf ./lib” to remove local libs")
    else:
        log.error("There were %i failures while finding global symbols.", len(failures))
