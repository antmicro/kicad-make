import argparse
import logging
import fileinput

from pathlib import Path
from common.kicad_project import KicadProject

log = logging.getLogger(__name__)


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("rename", help="Rename project files.")
    parser.add_argument("new_name", action="store", type=str, metavar="<new_name>", help="New name of project.")
    parser.set_defaults(func=run)


def run(kicad_project: KicadProject, args: argparse.Namespace) -> None:
    log.info("Renaming project")
    rename(kicad_project, args.new_name)


def rename(kicad_project: KicadProject, new_name: str) -> None:
    for file_path in Path(kicad_project.dir).rglob("*"):
        file_path = file_path.relative_to(kicad_project.dir)
        # Skip hidden files/folders
        if str(file_path).startswith("."):
            continue
        log.info(f"Checking: {file_path}..")

        if file_path.is_file():
            with fileinput.input(files=file_path, inplace=True, encoding="latin-1") as file:
                for _, line in enumerate(file):
                    new_line = line.replace(kicad_project.name, new_name)
                    print(new_line)

        if kicad_project.name in str(file_path):
            rename = str(file_path).replace(kicad_project.name, new_name)
            log.info(f"Renaming: {file_path} -> {rename}")
            file_path.rename(Path(kicad_project.dir) / rename)

    print("Succesfully renamed the project. Remember to change project name in schematics page settings and on PCB.")
