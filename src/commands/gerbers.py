import argparse
import logging
from typing import List, Optional

from git import Repo
from git.exc import InvalidGitRepositoryError

from common.kicad_project import KicadProject
from common.kmake_helper import run_kicad_cli, tag_gerbers

log = logging.getLogger(__name__)


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    gerber_parser = subparsers.add_parser(
        "gerber", help="Generate production files of PCB layers and drills in Gerber format."
    )
    gerber_parser.add_argument(
        "-e",
        "--noedge",
        action="store_true",
        help="Do not copy content of Edge.Cuts to other layers.",
    )
    gerber_parser.add_argument(
        "-x",
        "--excellon",
        action="store_true",
        dest="excellon",
        help="Set drill file format to Excellon.",
    )
    gerber_parser.add_argument(
        "--drill-origin",
        choices=["absolute", "plot"],
        default="absolute",
        dest="drill_origin",
        help="Set drill file origin to absolute origin or plot (relative).",
    )
    gerber_parser.set_defaults(func=run)


def run(kicad_project: KicadProject, args: argparse.Namespace) -> None:
    kicad_project.create_fab_dir()

    common_layers = []  # comma separated list of layers names

    if not args.noedge:
        common_layers.append("Edge.Cuts")

    export_gerbers(
        kicad_project,
        output_folder=f"{kicad_project.dir}/fab/",
        common_layers=common_layers,
        verbose=args.debug,
    )

    export_drill(
        kicad_project.pcb_file,
        f"{kicad_project.dir}/fab/",
        excellon=args.excellon,
        origin=args.drill_origin,
    )

    try:
        kicad_project_repo = Repo(f"{kicad_project.dir}")
        modified_files = kicad_project_repo.index.diff(None)
        for file_path in modified_files:
            if "pcb" in file_path.a_path:
                log.warning("%s changed since last commit", file_path.a_path)

        sha = kicad_project_repo.head.commit.hexsha
        short_sha = kicad_project_repo.git.rev_parse(sha, short=7)
        tag_gerbers(f"{kicad_project.dir}/fab", short_sha)
    except InvalidGitRepositoryError:
        log.warning("Project is not in repository. Githash not added.")
        return


def export_gerbers(
    kicad_project: KicadProject,
    output_folder: str = '""',
    layers: str = '""',
    exclude_refdes: bool = False,
    exclude_value: bool = False,
    include_border_title: bool = False,
    no_x2: bool = False,
    no_netlist: bool = False,
    subtract_soldermask: bool = False,
    disable_aperture_macros: bool = False,
    precision: int = 6,
    common_layers: Optional[List[str]] = None,
    board_plot_params: bool = False,
    protel_names: bool = False,
    verbose: bool = False,
) -> None:
    """Generate set of gerber files for PCB fabrication (excl. drill files).

    Extended with \"board-plot-params\" and \"common-layers\" options."""

    gerbers_export_cli_command = [
        "pcb",
        "export",
        "gerbers",
        kicad_project.pcb_file,
        "-o",
        output_folder,
        "--layers",
        layers,
        "--precision",
        str(precision),
    ]

    if common_layers is not None and len(common_layers) > 0:
        gerbers_export_cli_command.extend(["--common-layers"])
        gerbers_export_cli_command.extend(common_layers)

    if exclude_refdes:
        gerbers_export_cli_command.extend(["--exclude-refdes"])
    if exclude_value:
        gerbers_export_cli_command.extend(["--exclude-value"])
    if include_border_title:
        gerbers_export_cli_command.extend(["--include-border-title"])
    if no_x2:
        gerbers_export_cli_command.extend(["--no-x2"])
    if no_netlist:
        gerbers_export_cli_command.extend(["--no-netlist"])
    if subtract_soldermask:
        gerbers_export_cli_command.extend(["--subtract-soldermask"])
    if disable_aperture_macros:
        gerbers_export_cli_command.extend(["--disable-aperture-macros"])
    if board_plot_params:
        gerbers_export_cli_command.extend(["--board-plot-params"])
    if not protel_names:
        gerbers_export_cli_command.extend(["--no-protel-ext"])

    run_kicad_cli(gerbers_export_cli_command, verbose)
    log.info("Exported gerbers to : %s", kicad_project.fab_dir)


def export_drill(
    input_pcb_file: str, output_folder: str = '""', excellon: bool = False, origin: str = "absolute"
) -> None:
    log.info("Exporting drill files to %s", output_folder)
    export_cli_command = "pcb export drill"
    options = f" --format {'excellon' if excellon else 'gerber'}"
    options += " --generate-map"
    options += " --map-format gerberx2"
    options += " --excellon-separate-th"
    options += f" --drill-origin {origin}"
    options += f" {input_pcb_file}"
    options += f" -o {output_folder}"

    command = f"{export_cli_command} {options}"
    run_kicad_cli(command.split(), False)
