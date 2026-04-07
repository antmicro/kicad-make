import argparse
import logging

from askiff.pro import AskiffPro

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
    parser = subparsers.add_parser("clean", help="Clean-up project files from project's directory.")
    parser.add_argument(
        "--unused-files",
        action="store_true",
        help="Clean redundant project files from project's directory. [active if no other flag specified]",
    )
    parser.add_argument(
        "--unused-project-instances",
        action="store_true",
        help="Clean schematics from instance references to other projects.",
    )

    parser.set_defaults(func=run)


def run(kicad_project: KicadProject, args: argparse.Namespace) -> None:
    log.info("Cleaning up project files...")

    pro = AskiffPro(kicad_project.dir).load()

    if not any((args.unused_project_instances, args.unused_files)):
        args.unused_files = True

    if args.unused_files:
        clean_unused_files(pro)

    if args.unused_project_instances:
        clean_unused_project_instances(pro)

    log.info("Cleanup complete")


def clean_unused_files(pro: AskiffPro) -> None:
    """Remove unnecessary files from project directory"""
    for file_path in pro.path.rglob("*"):
        if file_path.relative_to(pro.path).parts[0] in folders_to_skip:
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
    log.info("Unused Files: Cleanup complete")


def clean_unused_project_instances(pro: AskiffPro) -> None:
    """Remove references to other projects from sheet & symbol instances"""

    for sch in pro.sch:
        for sym in sch.symbols:
            sym.instances = [pi for pi in sym.instances if pi.project_name == pro.project_name]
        for sheet in sch.sheets:
            sheet.instances = [pi for pi in sheet.instances if pi.project_name == pro.project_name]
    pro.save()
    log.info("Unused Project Instances: Cleanup complete")
