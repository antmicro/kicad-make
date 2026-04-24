"""Simple KiCad CLI Python wrapper"""

import argparse
import logging
import re

from askiff.board import StackupLayerMaskTop

from common.kicad_project import KicadProject
from common.kmake_helper import run_kicad_cli

log = logging.getLogger(__name__)


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    step_parser = subparsers.add_parser("step", help="Export 3D models of PCB in STEP format.")
    step_parser.set_defaults(func=run)


def run(pro: KicadProject, args: argparse.Namespace) -> None:
    pro.step_model3d_dir.mkdir(exist_ok=True, parents=True)

    step_file_name = f"{pro.project_name}.step"
    output_file_path = f"{pro.step_model3d_dir}/{step_file_name}"

    log.info("Exporting 3D STEP as %s", output_file_path)

    silkscreen = [layer for layer in pro.pcb_root.setup.stackup.layers if isinstance(layer, StackupLayerMaskTop)][0]

    preset_colors = {
        "Green": [20, 51, 36],
        "Red": [181, 19, 21],
        "Blue": [2, 59, 162],
        "Purple": [32, 2, 53],
        "Black": [11, 11, 11],
        "White": [245, 245, 245],
        "Yellow": [194, 195, 0],
    }

    if silkscreen.color is None:
        color = preset_colors["Green"]
    elif silkscreen.color.startswith("#"):
        color = [int(silkscreen.color[1:3], 16), int(silkscreen.color[3:5], 16), int(silkscreen.color[5:7], 16)]
    else:
        color = preset_colors.get(silkscreen.color, preset_colors["Green"])
    colorf = [c / 256 for c in color]

    export_step(
        pro.pcb_root.fs_path,
        output_file_path,
        verbose=args.debug,
    )

    with open(output_file_path, "r") as sfile:
        step_file = sfile.read()

    def sub_color(m: re.Match) -> str:
        if 0.3 < float(m.group(2)) < 0.33 and 0.47 < float(m.group(3)) < 0.5 and 0.4 < float(m.group(4)) < 0.42:
            return f"#{m.group(1)} = COLOUR_RGB('',{colorf[0]},{colorf[1]},{colorf[2]});"
        return m.group(0)

    match_r = r"#(\d*) = COLOUR_RGB\('',(\d*\.\d*),(\d*\.\d*),(\d*\.\d*)\);"
    step_file = re.sub(match_r, sub_color, step_file)

    with open(output_file_path, mode="w") as sfile:
        sfile.write(step_file)


def export_step(
    input_pcb_file: str,
    output_file_name: str = '""',
    verbose: bool = False,
) -> None:
    """Generate 3D STEP model from the given PCB file."""

    step_export_cli_command = ["pcb", "export", "step", "--subst-models", input_pcb_file, "-o", output_file_name]

    run_kicad_cli(step_export_cli_command, verbose)
