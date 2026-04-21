import argparse
import fileinput
import logging

from common.kicad_project import KicadProject

log = logging.getLogger(__name__)


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("rename", help="Rename project files.")
    parser.add_argument("new_name", action="store", type=str, metavar="<new_name>", help="New name of project.")
    parser.set_defaults(func=run)


def run(pro: KicadProject, args: argparse.Namespace) -> None:
    log.info("Renaming project")
    rename(pro, args.new_name)


def rename(pro: KicadProject, new_name: str) -> None:

    whitelist = [
        ".kicad_pro",
        ".kicad_pcb",
        ".kicad_sch",
        ".kicad_mod",
        ".kicad_sym",
        ".kicad_prl",
        ".kicad_dru",
        ".md",
        ".txt",
        ".rst",
        ".json",
        ".csv",
        ".gbr",
        ".svg",
        ".xml",
        "sym-lib-table",
        "fp-lib-table",
        "fp-cache-table",
    ]

    for file_path in pro.path.rglob("*"):
        file_path = file_path.relative_to(pro.path)
        # Skip hidden files/folders
        if str(file_path).startswith("."):
            continue
        log.info(f"Checking: {file_path}..")

        if file_path.suffix in whitelist and file_path.is_file():
            with fileinput.input(files=file_path, inplace=True, encoding="latin-1") as file:
                for _, line in enumerate(file):
                    new_line = line.replace(pro.project_name, new_name)
                    print(new_line, end="")

        if pro.project_name in str(file_path):
            rename = str(file_path).replace(pro.project_name, new_name)
            log.info(f"Renaming: {file_path} -> {rename}")
            file_path.rename(pro.path / rename)

    print("Succesfully renamed the project. Remember to change project name in schematics page settings and on PCB.")
