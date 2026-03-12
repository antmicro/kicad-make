import argparse
import logging
import tempfile
from pathlib import Path
from typing import List, Optional

from git import Repo
from git.exc import InvalidGitRepositoryError

from askiff.kistruct.board import Board
from askiff.kistruct.footprint import Footprint
from askiff.kistruct.common_pcb import Layer

from common.kicad_project import KicadProject
from common.kmake_helper import run_kicad_cli, tag_gerbers
from .prettify import prettify_file

log = logging.getLogger(__name__)

PASTE_LAYERS = [Layer.PASTE_B, Layer.PASTE_F]
# potentially this could be PASTE_ALL in askiff?


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
    gerber_parser.add_argument(
        "-rp",
        "--remove-dnp-paste",
        dest="no_dnp_paste",
        action="store_true",
        help="Remove solder paste from DNP footprints.",
    )
    gerber_parser.add_argument(
        "-atp",
        "--add-tht-paste",
        dest="add_tht_paste",
        action="store_true",
        help="Add solder paste on THT footprints.",
    )
    gerber_parser.set_defaults(func=run)


# Add a layer to pad's layer list
def add_pad_layer(layers_list: List[str], layer: str) -> None:
    if layer not in layers_list:
        layers_list.append(layer)


# Adds Paste layer on THT pads of footprint
# Assumes THT pad always has F and B
def add_fp_tht_paste(footprint: Footprint) -> bool:
    modified = False
    for pad in [pad for pad in footprint.pads if pad.type == "thru_hole"]:
        pad.layers.extend(PASTE_LAYERS)
        modified = True
    return modified


# Remove Paste layer from DNP footprint
def remove_fp_dnp_paste(footprint: Footprint) -> bool:
    modified = False
    for pad in footprint.pads:
        for layer in PASTE_LAYERS:
            if layer in pad.layers:
                pad.layers.remove(layer)
                modified = True
    return modified


# Adds Paste layer on THT pads of SMD/THT footprints
def add_pcb_tht_paste(board: Board) -> None:
    for fp in board.footprints:
        # if fp.attributes.through_hole: # TBD: this omits non-THT footprints, but some mixed connectors are defined as SMD
        if add_fp_tht_paste(fp):
            log.debug(f"Added solder paste on THT pads of {fp.properties.ref.value}")


# Removes Paste layer from DNP footprints
def remove_pcb_dnp_paste(board: Board) -> None:
    for fp in board.footprints:
        if fp.attributes.dnp:
            if remove_fp_dnp_paste(fp):
                log.info(f"Removed solder paste from DNP footprint {fp.properties.ref.value}")


# rename gerber/drill files
def rename_gbr_files(gbr_dir: str, temp_name: str, prj_name: str) -> None:
    extensions = [".gbr", ".drl", ".gbrjob"]
    for file_path in Path(gbr_dir).rglob("*"):
        if file_path.suffix in extensions:
            file_path.rename(str(file_path).replace(temp_name, prj_name))


# Stamp gerber files with short commit SHA
def stamp_gerbers(kicad_project: KicadProject) -> None:
    try:
        kicad_project_repo = Repo(f"{kicad_project.dir}")
        modified_files = kicad_project_repo.index.diff(None)
        for file_path in modified_files:
            if "pcb" in file_path.a_path:  # type: ignore
                log.warning("%s changed since last commit", file_path.a_path)

        sha = kicad_project_repo.head.commit.hexsha
        short_sha = kicad_project_repo.git.rev_parse(sha, short=7)
        tag_gerbers(f"{kicad_project.dir}/fab", short_sha)
    except InvalidGitRepositoryError:
        log.warning("Project is not in repository. Githash not added.")
        return


def run(kicad_project: KicadProject, args: argparse.Namespace) -> None:
    kicad_project.create_fab_dir()

    common_layers = []  # comma separated list of layers names

    if not args.noedge:
        common_layers.append("Edge.Cuts")

    board = Board.from_file(Path(kicad_project.pcb_file))
    log.info("Creating tmp PCB for manipulation and using it for output generation")
    with tempfile.NamedTemporaryFile(suffix=".kicad_pcb", delete=not args.debug) as temporary_board_file:
        board.filePath = temporary_board_file.name
        if args.add_tht_paste:
            add_pcb_tht_paste(board)
        if args.no_dnp_paste:
            remove_pcb_dnp_paste(board)
        board.to_file(Path(board.filePath))
        prettify_file(Path(board.filePath))

        export_gerbers(
            board.filePath,
            output_folder=f"{kicad_project.dir}/fab/",
            common_layers=common_layers,
            verbose=args.debug,
        )
        export_drill(
            board.filePath,
            f"{kicad_project.dir}/fab/",
            excellon=args.excellon,
            origin=args.drill_origin,
        )
        rename_gbr_files(f"{kicad_project.dir}/fab/", Path(board.filePath).stem, kicad_project.name)

        stamp_gerbers(kicad_project)


def export_gerbers(
    input_pcb_file: str,
    output_folder: str = '""',
    layers: str = "",
    exclude_refdes: bool = False,
    exclude_value: bool = False,
    include_border_title: bool = False,
    no_x2: bool = False,
    no_netlist: bool = False,
    subtract_soldermask: bool = True,
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
        input_pcb_file,
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
    log.info("Exported gerbers to: %s", output_folder)


def export_drill(
    input_pcb_file: str, output_folder: str = '""', excellon: bool = False, origin: str = "absolute"
) -> None:
    drill_export_cli_command = [
        "pcb",
        "export",
        "drill",
        "--generate-map",
        "--map-format",
        "gerberx2",
        "--excellon-separate-th",
        "--drill-origin",
        origin,
        input_pcb_file,
        "-o",
        output_folder,
    ]

    if excellon:
        drill_export_cli_command.extend(["--format", "excellon"])
    else:
        drill_export_cli_command.extend(["--format", "gerber"])

    run_kicad_cli(drill_export_cli_command, False)
    log.info("Exported drill files to: %s", output_folder)
