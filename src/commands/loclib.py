"""Functions operating on raw .kicad_pcb, .kicad_sch,
    .kicad_mod, .kicad_sym, .kicad_lib files"""

import argparse
import json
import logging
import os
import shutil
import typing
from dataclasses import dataclass, field
from typing import List

from kiutils.board import Board
from kiutils.footprint import Footprint
from kiutils.libraries import Library, LibTable
from kiutils.schematic import Schematic
from kiutils.symbol import Symbol, SymbolLib

from common.kicad_project import KicadProject
from common.kmake_helper import get_property, set_property

log = logging.getLogger(__name__)


@dataclass(order=True)
class LocalSymbol:
    name: str
    symbol: Symbol


@dataclass(order=True)
class UsedLib:
    name: str
    path: str
    symbol_list: typing.List[LocalSymbol] = field(default_factory=list)


@dataclass(order=True)
class SymbolsLibs:
    libs: typing.List[UsedLib] = field(default_factory=list)


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    loclib_parser = subparsers.add_parser(
        "loclib", help="Create local project library and link symbols/footprint/3D models to this library."
    )
    loclib_parser.add_argument(
        "-f",
        "--force",
        "--force-override",
        action="store_true",
        help="Rewrite local library.",
    )
    loclib_parser.add_argument(
        "-c",
        "--cleanup",
        "--cleanup-lib-symbols",
        action="store_true",
        help="Remove unrefferenced lib_symbols, footprints and 3D models.",
    )

    loclib_parser.set_defaults(func=run)


def run(ki_pro: KicadProject, args: argparse.Namespace) -> None:
    loclib_project(ki_pro, args)


# TODO: implement this function as symbols without lib are not handled properly
def dump_sheet_symbols_to_lib(ki_pro: KicadProject, args: argparse.Namespace) -> None:
    pass


def get_sym_lib_mapping(ki_pro: KicadProject) -> typing.Dict[str, str]:
    libtable = ki_pro.read_sym_lib_table_file(ki_pro.glob_sym_lib_table_path)

    if os.path.isfile("sym-lib-table"):
        local_libtable = LibTable.from_file("sym-lib-table")
        for lib_entry in local_libtable.libs:
            libtable.libs.append(lib_entry)

    # Filter non existing libs
    existing_libs = []
    for lib in libtable.libs:
        libpath = os.path.expandvars(lib.uri)
        if not os.path.isfile(libpath):
            log.warning(f"Lib {libpath} in lib table but not in file system, skipping")
            continue
        existing_libs.append(lib)
    libtable.libs = existing_libs

    return {lib.name: os.path.expandvars(lib.uri) for lib in libtable.libs}


def get_fp_lib_mapping(ki_pro: KicadProject) -> typing.Dict[str, str]:
    libtable = ki_pro.read_fp_lib_table_file(ki_pro.glob_fp_lib_table_path)

    if os.path.isfile("fp-lib-table"):
        local_libtable = LibTable.from_file("fp-lib-table")
        for lib_entry in local_libtable.libs:
            libtable.libs.append(lib_entry)

    return {lib.name: os.path.expandvars(lib.uri) for lib in libtable.libs}


def load_kicad_environ_vars(ki_pro: KicadProject) -> None:
    if os.path.exists(ki_pro.comm_cfg_path):
        with open(ki_pro.comm_cfg_path, encoding="utf-8") as kicad_conf:
            if "environment" in json.load(kicad_conf).items():
                for envvar, val in json.load(kicad_conf)["environment"]["vars"].items():
                    os.environ[envvar] = val
            else:
                os.environ[ki_pro.env_var_name_sym_lib] = "/usr/share/kicad/symbols"
                os.environ[ki_pro.env_var_name_fp_lib] = "/usr/share/kicad/footprints"
    else:
        os.environ[ki_pro.env_var_name_sym_lib] = "/usr/share/kicad/symbols"
        os.environ[ki_pro.env_var_name_fp_lib] = "/usr/share/kicad/footprints"
        log.warning(f"KiCad Common file ({ki_pro.comm_cfg_path}) not found. Using default environment values.")
    os.environ["KIPRJMOD"] = os.path.abspath(".")


def get_symbol_name(__symbol: Symbol) -> str:
    """Returns Symbol name"""
    if ":" not in __symbol.libId:
        return __symbol.libId
    symbol_id = __symbol.libId.split(":", 1)
    if len(symbol_id) == 1:
        return symbol_id.libId
    return symbol_id[1]


def get_assigned_footprint(__symbol: Symbol) -> str:
    """Returns Footprint field content string from Symbol"""
    footprint_id = get_property(__symbol.properties, "Footprint").value
    if ":" in footprint_id:
        return footprint_id.split(":", 1)
    return footprint_id


def get_symbol_from_library(__symbol_name: str, __library_path: str) -> Symbol:
    """Get symbol from library if exists"""
    remote_lib = SymbolLib.from_file(
        __library_path
    )  # this calls for optimization - multiple loads of same library may occur
    return next(
        (symbol for symbol in remote_lib.symbols if symbol.entryName == __symbol_name),
        None,
    )


def append_symbol_to_library(symbol: Symbol, library: SymbolLib) -> None:
    """Add symbol to the library"""
    if symbol not in library.symbols:
        library.symbols.append(symbol)
    else:
        log.debug("Skipping %s, already in lib: %s", symbol.entryName, library.filePath)


def append_template_symbol_to_library(symbol: Symbol, library: SymbolLib) -> None:
    """Add template symbol to the top of the library"""
    if symbol not in library.symbols:
        library.symbols.insert(0, symbol)
    else:
        log.debug("Skipping %s, already in lib: %s", symbol.entryName, library.filePath)


def cleanup_schematic_lib_symbols(ki_pro: KicadProject) -> None:
    """Remove unreferrenced schematic symbols from schematis cache"""
    log.info("Removing unrefferenced schematic symbols")
    for schematic_path in ki_pro.all_sch_files:
        log.info("Processing: %s", os.path.basename(schematic_path))
        schematic = Schematic().from_file(schematic_path)
        log.debug("Schematic %s", schematic.filePath)
        sch_symbol_instances = []
        for sch_symbol in schematic.schematicSymbols:
            # Special case for symbols that have libId token
            # set when the symbol was edited in the schematic
            if sch_symbol.libName:
                if sch_symbol.libName not in sch_symbol_instances:
                    sch_symbol_instances.append(sch_symbol.libName)
                    log.warning("Altered schematic symbol: %s", sch_symbol.libName)

            library = sch_symbol.libraryNickname
            if library is None:
                continue
            symbol_name = get_symbol_name(sch_symbol)
            if symbol_name in sch_symbol_instances:
                continue
            sch_symbol_instances.append(symbol_name)

        schematic.libSymbols = (
            symbol for symbol in schematic.libSymbols if get_symbol_name(symbol) in sch_symbol_instances
        )
        schematic.to_file()


def generate_lib_symbol_list() -> None:
    pass


def group_symbols_by_library_name(ki_pro: KicadProject) -> SymbolsLibs:
    schematic_cache_lib = "__schematic"
    library_mapping = get_sym_lib_mapping(ki_pro)
    log.debug("Mapping: %s", library_mapping)
    # Add library for symbols without lib/lib not exists
    lib_list = SymbolsLibs([UsedLib(schematic_cache_lib, "", [])])

    # get list of all used libraries and symbols
    for schematic_path in ki_pro.all_sch_files:
        schematic = Schematic().from_file(schematic_path)
        log.info("Loading symbols from %s", os.path.basename(schematic.filePath))
        for schematic_symbol in schematic.libSymbols:
            library = schematic_symbol.libraryNickname
            if library is None:
                # Special case for altered symbols
                library = schematic_cache_lib
                continue
            symbol_name = get_symbol_name(schematic_symbol)
            log.debug("Processing  %s. LibID: %s", symbol_name, schematic_symbol.libId)
            lib_entry = next((item for item in lib_list.libs if item.name == library), None)

            if not lib_entry:
                symbol_library_path = library_mapping.get(library, schematic_cache_lib)
                # Library does not exists, add symbol from cache to cache_lib
                if symbol_library_path == schematic_cache_lib:
                    # Use library for cached symbols
                    log.warning("LibID: %s not found. Using %s from cache", schematic_symbol.libId, symbol_name)
                    cache_lib = next((item for item in lib_list.libs if item.name == schematic_cache_lib))
                    # Cached symbol can have properies not set
                    # Copy properties from one of the symbols used in schematic
                    for used_symbol in schematic.schematicSymbols:
                        if used_symbol.entryName == schematic_symbol.entryName:
                            schematic_symbol.properties = used_symbol.properties
                            break
                    cache_lib.symbol_list.append(LocalSymbol(symbol_name, schematic_symbol))
                    continue
                lib_list.libs.append(
                    UsedLib(
                        library,
                        symbol_library_path,
                        [LocalSymbol(symbol_name, schematic_symbol)],
                    )
                )
                continue
            # Don't create duplicates in library
            if symbol_name in [s.name for s in lib_entry.symbol_list]:
                continue

            lib_entry.symbol_list.append(LocalSymbol(symbol_name, schematic_symbol))
    return lib_list


def loclib_symbols(ki_pro: KicadProject, args: argparse.Namespace) -> SymbolLib:
    ki_pro.create_fp_lib_dir()
    local_lib_path = f"{ki_pro.lib_dir}/{ki_pro.name}.{ki_pro.sym_lib_ext}"
    if args.force:
        log.info("Localize symbols in force mode")
        local_lib = SymbolLib(version="20211014", generator="kmake_loclib")
        local_lib.filePath = local_lib_path
    else:
        log.info("Localize symbols in append mode")
        try:
            log.debug("Importing: %s", local_lib_path)
            local_lib = SymbolLib.from_file(local_lib_path)
        except Exception:
            log.warning("Local library not found")
            local_lib = SymbolLib(version="20211014", generator="kmake_loclib")
            local_lib.filePath = local_lib_path
            local_lib.to_file()
            log.info("Created empty local library")

    lib_list = group_symbols_by_library_name(ki_pro)

    for used_lib in lib_list.libs:
        # Special case for symbols that were changed on schematic
        # or those with library missing
        if used_lib.name == "__schematic":
            log.info("Processing altered schematic symbols / symbols with missing lib")
            for local_symbol in used_lib.symbol_list:
                append_symbol_to_library(local_symbol.symbol, local_lib)
            continue

        log.info("Processing symbols from %s", os.path.basename(used_lib.path))
        remote_lib = SymbolLib.from_file(used_lib.path)
        log.debug("Processing: %s", used_lib.path)
        for symbol_name in [s.name for s in used_lib.symbol_list]:
            # Get symbol from remote lib
            symbol = next(
                (symbol for symbol in remote_lib.symbols if symbol.entryName == symbol_name),
                None,
            )
            if symbol is None:
                # Get symbol from local lib
                log.warning(
                    "Entry %s not found in %s. Copying from schematic",
                    symbol_name,
                    os.path.basename(used_lib.path),
                )
                symbol = next(s.symbol for s in used_lib.symbol_list if s.name == symbol_name)

            log.debug("Copied %s from %s", symbol_name, used_lib.path)

            template_symbol = symbol.extends
            if template_symbol:
                log.debug("Extends: %s", template_symbol)
                template = next(symbol for symbol in remote_lib.symbols if symbol.entryName == template_symbol)
                append_template_symbol_to_library(template, local_lib)

            append_symbol_to_library(symbol, local_lib)

    ki_pro.local_sym_lib = local_lib
    local_lib.to_file(local_lib_path)
    log.debug("Saved to: %s", local_lib_path)
    return local_lib


def loclib_footprints(ki_pro: KicadProject, args: argparse.Namespace) -> None:
    ki_pro.create_fp_lib_dir()

    library_mapping = get_fp_lib_mapping(ki_pro)

    if args.force:
        log.info("Localize footprints in force mode")
    else:
        log.info("Localize footprints in append mode")
    log.info("Processing : %s", os.path.basename(ki_pro.pcb_file))
    board = Board.from_file(ki_pro.pcb_file)
    footprints_list: List[Footprint] = []
    for footprint in board.footprints:
        if any(fp.entryName == footprint.entryName for fp in footprints_list):
            continue
        # skip kibuzzard footprints
        if "kibuzzard-" in footprint.entryName:
            continue
        if footprint.libraryNickname == "" or footprint.libraryNickname is None:
            log.warning("Skipping %s. No library defined.", footprint.libId)
            continue
        footprints_list.append(footprint)

    for footprint in footprints_list:
        remote_lib_path = library_mapping.get(footprint.libraryNickname)

        lib_fp_path = f"{remote_lib_path}/{footprint.entryName}.{ki_pro.fp_lib_ext}"
        local_fp_path = f"{ki_pro.fp_lib_dir}/{footprint.entryName}.{ki_pro.fp_lib_ext}"
        log.debug("Processing: %s from %s", footprint.entryName, footprint.libraryNickname)
        if not os.path.exists(lib_fp_path):
            log.error("%s does not exists. Skipping", lib_fp_path)
            continue
        if args.force:
            if os.path.exists(local_fp_path):
                # in case of the src and dst are the same file
                if os.path.samefile(lib_fp_path, local_fp_path):
                    log.debug("%s is local footprint. Skipping", footprint.entryName)
                    continue
                os.remove(local_fp_path)
        else:
            if os.path.exists(local_fp_path):
                log.debug("Skipping  : %s already in local lib", footprint.entryName)
                continue
        shutil.copy(lib_fp_path, local_fp_path, follow_symlinks=True)
        log.debug("Copied  : %s to %s", footprint.entryName, local_fp_path)

    # process only symbols from local library


def loclib_3d_models(ki_pro: KicadProject, args: argparse.Namespace) -> None:
    ki_pro.create_3d_model_lib_dir()

    local_footprints = os.listdir(ki_pro.fp_lib_dir)

    model_paths = []

    for fp_name in local_footprints:
        fp_path = f"{ki_pro.fp_lib_dir}/{fp_name}"
        # print(fp_name)
        footprint = Footprint.from_file(fp_path)
        for model in footprint.models:
            model_paths.append(os.path.expandvars(model.path))

    for model_path in model_paths:
        model_name = os.path.basename(model_path)
        local_model_path = f"{ki_pro.model_3d_lib_dir}/{model_name}"
        if not os.path.exists(model_path):
            log.error("Skipping  :  %s does not exists", model_path)
            continue
        if args.force:
            if os.path.exists(model_path):
                # in case of the src and dst are the same file
                if os.path.samefile(model_path, local_model_path):
                    log.debug("Skipping  :  %s is local 3D model", model_name)
                    continue
                os.remove(local_model_path)
        else:
            if os.path.exists(local_model_path):
                log.debug("Skipping  : %s already in local lib", model_name)
                continue
        shutil.copy(model_path, local_model_path, follow_symlinks=True)
        log.debug("Copied    : %s to %s", model_name, local_model_path)


def update_links(ki_pro: KicadProject, local_lib: SymbolLib, args: argparse.Namespace) -> None:
    local_symbols = []

    for symbol in local_lib.symbols:
        local_symbols.append(symbol.entryName)

    local_footprints = os.listdir(ki_pro.fp_lib_dir)
    local_3d_models = os.listdir(ki_pro.model_3d_lib_dir)

    # Patch paths in schematic symbols
    for schematic_path in ki_pro.all_sch_files:
        log.info("Patching paths in: %s", os.path.basename(schematic_path))
        schematic = Schematic().from_file(schematic_path)
        log.debug("Schematic %s", schematic.filePath)
        for symbol in schematic.libSymbols + schematic.schematicSymbols:
            if symbol.entryName in local_symbols:
                if not symbol.libraryNickname:
                    continue
                symbol.libraryNickname = ki_pro.name
            # skip power symbols footprint check
            # TODO replace with if symbol.isPower once it's documented
            if "#PWR" in get_property(symbol.properties, "Reference").value:
                continue
            footprint_id = get_property(symbol.properties, "Footprint").value
            if footprint_id == "":
                log.warning(
                    "%s has no footprint assigned",
                    symbol.entryName,
                )
                continue
            if ":" in footprint_id:
                fp_library_nickname, fp_entry_name = footprint_id.split(":", 1)
            else:
                fp_entry_name = footprint_id
            if fp_entry_name in [os.path.splitext(fp_name)[0] for fp_name in local_footprints]:
                fp_library_nickname = f"{ki_pro.name}-{ki_pro.relative_fp_lib_path}"
                footprint_id = f"{fp_library_nickname}:{fp_entry_name}"
                set_property(symbol, "Footprint", footprint_id)
        schematic.to_file()

    # Patch paths in PCB footprints
    log.info("Patching paths in: %s", os.path.basename(ki_pro.pcb_file))
    board = Board.from_file(ki_pro.pcb_file)
    for footprint in board.footprints:
        if footprint.entryName in [os.path.splitext(fp_name)[0] for fp_name in local_footprints]:
            footprint.libraryNickname = f"{ki_pro.name}-{ki_pro.relative_fp_lib_path}"

            for idx, _ in enumerate(footprint.models):
                model_name = os.path.basename(footprint.models[idx].path)
                if model_name in local_3d_models:
                    footprint.models[idx].path = (
                        f"${{KIPRJMOD}}/{ki_pro.relative_lib_path}/{ki_pro.relative_3d_model_path}/{model_name}"
                    )

    board.to_file()

    # Patch paths in local symbol library
    log.info("Patching paths in: %s", os.path.basename(local_lib.filePath))
    for symbol in local_lib.symbols:
        footprint_id = get_property(symbol.properties, "Footprint").value
        if footprint_id == "":
            log.warning(
                "%s has no footprint assigned",
                symbol.entryName,
            )
            continue
        if ":" in footprint_id:
            fp_library_nickname, fp_entry_name = footprint_id.split(":", 1)
        else:
            fp_entry_name = footprint_id
        if fp_entry_name in [os.path.splitext(fp_name)[0] for fp_name in local_footprints]:
            fp_library_nickname = f"{ki_pro.name}-{ki_pro.relative_fp_lib_path}"
            footprint_id = f"{fp_library_nickname}:{fp_entry_name}"
            set_property(symbol, "Footprint", footprint_id)
    local_lib.to_file()

    # Patch 3D model paths in local footprints library
    log.info("Patching 3d model path local footprints")
    for fp_name in local_footprints:
        log.debug("Patching 3d model path in: %s", fp_name)
        fp_path = f"{ki_pro.fp_lib_dir}/{fp_name}"
        # print(fp_name)
        footprint = Footprint.from_file(fp_path)
        for idx, _ in enumerate(footprint.models):
            model_name = os.path.basename(footprint.models[idx].path)
            if model_name in local_3d_models:
                footprint.models[idx].path = (
                    f"${{KIPRJMOD}}/{ki_pro.relative_lib_path}/{ki_pro.relative_3d_model_path}/{model_name}"
                )
        footprint.to_file(fp_path)


def add_lib_to_sym_lib_table(lib_name: str, symb_lib_path: str, sym_lib_table_path: str = "sym-lib-table") -> None:
    """Add Symbol lib to sym-lib-table"""
    if os.path.isfile(sym_lib_table_path):
        log.info("Updating %s", sym_lib_table_path)
        sym_lib_table = LibTable.from_file(sym_lib_table_path)
    else:
        log.info("Generating %s", sym_lib_table_path)
        sym_lib_table = LibTable.create_new("sym_lib_table")
        sym_lib_table.filePath = sym_lib_table_path

    local_lib_entry = Library(name=lib_name, uri=symb_lib_path)
    if local_lib_entry not in sym_lib_table.libs:
        sym_lib_table.libs.append(local_lib_entry)

    sym_lib_table.to_file()


def add_lib_to_fp_lib_table(lib_name: str, fp_lib_path: str, fp_lib_table_path: str = "fp-lib-table") -> None:
    """Add Foorprint lib directory to fp-lib-table"""
    if os.path.isfile(fp_lib_table_path):
        log.info("Updating %s", fp_lib_table_path)
        fp_lib_table = LibTable.from_file(fp_lib_table_path)
    else:
        log.info("Generating %s", fp_lib_table_path)
        fp_lib_table = LibTable.create_new("fp_lib_table")
        fp_lib_table.filePath = fp_lib_table_path

    local_lib_entry = Library(name=lib_name, uri=fp_lib_path)
    if local_lib_entry not in fp_lib_table.libs:
        fp_lib_table.libs.append(local_lib_entry)

    fp_lib_table.to_file()


def loclib_project(ki_pro: KicadProject, args: argparse.Namespace) -> None:
    """Create local library from components used in schematic/pcb"""
    if args.cleanup:
        cleanup_schematic_lib_symbols(ki_pro)
        return

    load_kicad_environ_vars(ki_pro)
    kiprjmod_lib = loclib_symbols(ki_pro, args)

    # Dump symbols and footprints to library in project folder
    loclib_footprints(ki_pro, args)
    loclib_3d_models(ki_pro, args)

    # Update symbol/footprint library links
    update_links(ki_pro, kiprjmod_lib, args)

    # Generate/extend sym-lib-table
    kiprjmod_sym_lib_path = f"${{KIPRJMOD}}/{ki_pro.relative_lib_path}/{ki_pro.name}.{ki_pro.sym_lib_ext}"
    add_lib_to_sym_lib_table(lib_name=ki_pro.name, symb_lib_path=kiprjmod_sym_lib_path)

    # Generate/extend fp-lib-table
    kiprjmod_fp_lib_path = f"${{KIPRJMOD}}/{ki_pro.relative_lib_path}/{ki_pro.name}-footprints/"
    add_lib_to_fp_lib_table(lib_name=f"{ki_pro.name}-footprints", fp_lib_path=kiprjmod_fp_lib_path)
