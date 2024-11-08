"""File and working directory helper scripts"""

import logging
import os
import subprocess
import sys
from kiutils.footprint import Footprint
from kiutils.symbol import Symbol
from kiutils.items.schitems import SchematicSymbol
from kiutils.items.fpitems import FpProperty
from kiutils.items.common import Property
from typing import List, Any, Optional, Union

log = logging.getLogger(__name__)


def is_venv() -> bool:
    return hasattr(sys, "real_prefix") or (hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix)


def is_in_path(name: str) -> bool:
    from shutil import which

    return which(name) is not None


def get_kicad_cli_command() -> tuple[str, List[str]]:
    try:
        kicad_cli_name = os.environ["KMAKE_KICAD_CLI"]
        kicad_cli_path = kicad_cli_name.split(" ")[0]
        kicad_cli_args = kicad_cli_name.split(" ")[1:]
    except KeyError:
        kicad_cli_path = "kicad-cli"
        kicad_cli_args = []
    if not is_in_path(kicad_cli_path):
        raise FileNotFoundError(
            f'Couldn\'t find "{kicad_cli_path}" in PATH. Make sure it is properly installed on your system. Exiting.'
        )
    return kicad_cli_path, kicad_cli_args


def run_kicad_cli(args: List[str], verbose: bool) -> None:
    kicad_cli_path, kicad_cli_args = get_kicad_cli_command()
    command = [kicad_cli_path] + kicad_cli_args
    command.extend(args)
    log.info(f"Running command: {' '.join(command)}")
    stdout_redirect = None
    stderr_redirect = None
    if not verbose:
        stdout_redirect = subprocess.DEVNULL
        stderr_redirect = subprocess.STDOUT

    subprocess.run(command, check=True, stdout=stdout_redirect, stderr=stderr_redirect)


def find_files_by_ext_recursive(wdir: str, ext: str) -> List[str]:
    """Recursevely search for file by extension"""
    searched_files = []
    if not ext[0] == ".":
        ext = "." + ext
    for root_folder, _, files in os.walk(wdir):
        for file in files:
            if file[-len(ext) :] == ext:
                searched_files.append(os.path.join(root_folder, file))
    if len(searched_files) < 1:
        log.warning(f"No *{ext} files found in {wdir}.")
    return searched_files


def find_files_by_ext(wdir: str, ext: str, disable_logging: bool = False) -> List[str]:
    """Search for file by extension

    Parameters:
        disable_logging (bool): do not log warrings
    """
    files = []
    if not ext[0] == ".":
        ext = "." + ext
    for file in os.listdir(wdir):
        if file.endswith(ext):
            files.append(os.path.join(wdir, file))
    if len(files) < 1 and not disable_logging:
        log.warning(f"No *{ext} files found in {wdir}.")
    return files


def tag_gerbers(folder: str, tag: str) -> None:
    """Mark all Gerber files with hash tag"""
    gerber_files = find_files_by_ext(folder, "gbr")
    for gerber_file in gerber_files:
        with open(gerber_file, "r+", encoding="ascii") as file:
            filedata = ""
            for line in file:
                if "G04 Created by KiCad" in line and " commit " not in line:
                    stripped_line = line.rstrip("*\n")
                    line = f"{stripped_line} commit  {tag} *\n"
                filedata += line
            file.seek(0)
            file.write(filedata)


def get_property(obj: Union[Footprint, Symbol, SchematicSymbol], prop: str) -> Optional[str]:
    for item in obj.properties:
        if item.key.lower() == prop.lower():
            return item.value
    return None


def remove_property(obj: Union[Footprint, Symbol, SchematicSymbol], name: str) -> List[Union[Property, FpProperty]]:
    return [prop for prop in obj.properties if prop.key.lower() != name.lower()]


def set_property(symbol: Any, name: str, value: Any) -> None:
    prop = next(filter(lambda prop: prop.key == name, symbol.properties))
    prop.value = value
