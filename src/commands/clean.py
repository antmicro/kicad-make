import argparse
import logging

from pathlib import Path
from common.kicad_project import KicadProject

log = logging.getLogger(__name__)

folders_to_skip = [
    "assets",
    "doc",
]

extensions_to_remove = [
    ".000",  # .000
    ".bak",  # .bak
    ".bck",  # .bck
    ".kicad_pcb-bak",  # .kicad_pcb-bak
    ".sch-bak",  # .sch-bak
    ".kicad-sch-bak",  # .kicad-sch-bak
    ".net",  # .bck
    ".ses",  # .ses
    ".xml",  # .xml
    ".csv",  # .csv
    ".tmp",  # .tmp
    ".~",  # .~
]

files_to_remove = [
    "fp-info-cache",  # fp-info-cache
]

startswith_to_remove = [
    "_autosave-.",  # _autosave-
]

endswith_to_remove = [
    "-save.pro",  # -save.pro
    "-save.kicad_pro",  # -save.kicad_pro
    "-save.kicad_pcb",  # -save.kicad_pcb
]


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("clean", help="Clean redundant project files from project's directory.")
    parser.set_defaults(func=run)


def run(kicad_project: KicadProject, args: argparse.Namespace) -> None:
    log.info("Cleaning up redundant files in the project directory")

    for file_path in Path(kicad_project.dir).rglob("*"):
        if file_path.relative_to(Path(kicad_project.dir)).parts[0] in folders_to_skip:
            continue

        # remove only files
        if not file_path.is_file():
            continue

        if file_path.suffix in extensions_to_remove:
            log.warning(f"Deleting {file_path}")
            file_path.unlink()
        elif file_path.name in files_to_remove:
            log.warning(f"Deleting {file_path}")
            file_path.unlink()
        elif file_path.name.startswith(tuple(startswith_to_remove)):
            log.warning(f"Deleting {file_path}")
            file_path.unlink()
        elif file_path.name.endswith(tuple(endswith_to_remove)):
            log.warning(f"Deleting {file_path}")
            file_path.unlink()

    log.info("Cleanup complete")
