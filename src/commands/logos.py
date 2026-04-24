import argparse
import io
import logging
from pathlib import Path

from askiff import Schematic
from askiff.common import DataBlock, PaperSize
from askiff.gritems import ImageSch
from PIL import Image as PIL_Image
from xdg import BaseDirectory

from common.kicad_project import KicadProject

log = logging.getLogger(__name__)

BUILTIN_LOGO_PATH = Path(__file__).parent.parent / "logos"


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    logos_parser = subparsers.add_parser("logos", help="Adds selected logo to the schematic.")
    logos_parser.add_argument("logo", nargs="*", metavar="<logo file>", help="Name of the logo file.")
    logos_parser.add_argument(
        "-s",
        "--size",
        action="store",
        default=180,
        type=int,
        help="Size of the logos.",
    )
    logos_parser.add_argument(
        "-p",
        "--path",
        action="store",
        default=f"{BaseDirectory.xdg_data_home}/kmake/logos/",
        type=str,
        help="Custom path to logos folder.",
    )
    logos_parser.add_argument("--list", action="store_true", help="list available logos.")
    logos_parser.set_defaults(func=run)


def run(pro: KicadProject, args: argparse.Namespace) -> None:
    if args.list is True:
        custom_path = [f.parts[-1] for f in Path(args.path).glob("*")]
        built_in = [f.parts[-1] for f in BUILTIN_LOGO_PATH.glob("*")]
        built_in_ok = []
        built_in_masked = []

        for logo in built_in:
            if logo in custom_path:
                built_in_ok.append(logo)
            else:
                built_in_masked.append(logo)

        if len(custom_path) > 0:
            log.info(f"Available logos (Custom path): {custom_path}")
        if len(built_in_ok) > 0:
            log.info(f"Available logos (Built-in): {built_in_ok}")
        if len(built_in_masked) > 0:
            log.info(f"Some Built-in logos are masked by custom-path logos: {built_in_masked}")

        exit(0)

    if not len(args.logo):
        log.error("No logo name was defined. Exit")
        log.info("Use --list to see available logos")
        exit(1)

    # Open logo files
    new_logos = read_logos(args)

    if not len(new_logos):
        log.error("Failed to open any of the provided logo. Exit")
        exit(1)

    # Check page size
    for schematic in pro.sch:
        check_schematic_size(schematic=schematic)
        # Add logos to schematic
        logos = get_current_logos(schematic=schematic)
        logos.extend(new_logos)
        position_logos(logos=logos, schematic=schematic, args=args)
        schematic.graphic_items.extend(new_logos)
        schematic.to_file()
        log.info(f"Saved {schematic.fs_path}")
        for logo in args.logo:
            log.info(f"Added {logo} to {schematic.fs_path}")


# Check page size (acceptable sizes are A3/A4)
def check_schematic_size(schematic: Schematic) -> None:
    assert schematic.fs_path
    if schematic.paper.size in (PaperSize.A3, PaperSize.A4):
        log.info(f"Found {schematic.fs_path.name} in {schematic.paper.size} size")
    else:
        log.error(f"{schematic.fs_path.name} in wrong size ({schematic.paper.size}) Accepted sizes: A3, A4")
        exit(1)


# Open logo file and parse it to s-expression
def read_logos(args: argparse.Namespace) -> list[ImageSch]:
    logos: list[ImageSch] = []
    for logo in args.logo:
        logo_path = Path(args.path) / logo

        if logo_path.suffix == "":
            logo_path = logo_path.with_suffix(".png")

        if logo_path.suffix != ".png":
            raise ValueError(f"Not supported image format: {logo_path} (supported: png)")

        if not logo_path.exists():
            logo_path = (BUILTIN_LOGO_PATH / logo).with_suffix(".png")
        if not logo_path.exists():
            log.error(f"{logo} not found")

        with open(logo_path, "rb") as f:
            data = f.read()  # raw binary buffer
        img = ImageSch(data=DataBlock(data))
        logos.append(img)

    return logos


# Load logos already present on the schematic by checking Y pos of the img
def get_current_logos(schematic: Schematic) -> list[ImageSch]:
    logos: list[ImageSch] = []
    for img in schematic.graphic_items:
        if not isinstance(img, ImageSch):
            continue
        # TODO: extract magic numbers to constants as percentage of page size
        if schematic.paper.size == PaperSize.A3:
            if img.position.y >= 254 and img.position.y <= 285:
                logos.append(img)
        elif schematic.paper.size == PaperSize.A4:
            if img.position.y >= 165 and img.position.y <= 195:
                logos.append(img)

    return logos


def position_logos(logos: list[ImageSch], schematic: Schematic, args: argparse.Namespace) -> None:
    # mm to px ratio in Eschema
    mm_px_ratio = 0.0846
    logo_clearance = 5
    # Holds right edges of the images
    logo_right_edge: list[float | int] = []
    logos_height = args.size
    log.debug(f"Logo height = {logos_height}")
    for i, logo in enumerate(logos):
        # set scale
        decoded_logo = PIL_Image.open(io.BytesIO(logo.data))
        scale_factor = logos_height / decoded_logo.size[1]
        logo.scale = scale_factor
        log.debug(f"Scale factor = {scale_factor}")
        # set X position
        logo_width = decoded_logo.size[0] * scale_factor * mm_px_ratio
        # most left logo
        if i == 0:
            logo.position.x = 15 + logo_width / 2
        # rest of the logos
        else:
            logo.position.x = logo_right_edge[i - 1] + logo_width / 2 + logo_clearance
        logo_right_edge.append(logo.position.x + logo_width / 2)
        log.debug(f"X position = {logo.position.x}")
        # set Y position
        if schematic.paper.size == PaperSize.A3:
            logo.position.y = 270
        elif schematic.paper.size == PaperSize.A4:
            logo.position.y = 180
        log.debug(f"Position = {logo.position}")
