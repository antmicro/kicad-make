import argparse
import base64
import io
import logging
from typing import List, Union
from pathlib import Path

from kiutils.items.common import Image
from kiutils.schematic import Schematic
from kiutils.utils.sexpr import parse_sexp
from PIL import Image as PIL_Image
from xdg import BaseDirectory

from common.kicad_project import KicadProject
from .prettify import run as prettify

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
    logos_parser.add_argument("--list", action="store_true", help="List available logos.")
    logos_parser.set_defaults(func=run)


def run(kicad_project: KicadProject, args: argparse.Namespace) -> None:
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

    # Load schematics
    schematics = []
    for path in kicad_project.all_sch_files:
        schematics.append(Schematic.from_file(path))

    # Check page size
    for schematic in schematics:
        check_schematic_size(schematic=schematic)
        # Add logos to schematic
        logos = get_current_logos(schematic=schematic)
        logos.extend(new_logos)
        position_logos(logos=logos, schematic=schematic, args=args)
        schematic.graphicalItems.extend(new_logos)
        schematic.to_file()
        log.info(f"Saved {schematic.filePath}")
        for logo in args.logo:
            log.info(f"Added {logo} to {schematic.filePath}")
    prettify(kicad_project, argparse.Namespace())


# Check page size (acceptable sizes are A3/A4)
def check_schematic_size(schematic: Schematic) -> None:
    schematic_name = schematic.filePath
    if schematic.paper.paperSize == "A3" or schematic.paper.paperSize == "A4":
        log.info(f"Found {schematic_name} in {schematic.paper.paperSize} size")
    else:
        log.error(f"{schematic_name} in wrong size ({schematic.paper.paperSize}) Accepted sizes: A3, A4")
        exit(1)


# Open logo file and parse it to sexpression
def read_logos(args: argparse.Namespace) -> List[Image]:
    logos: List[Image] = []
    for logo in args.logo:
        logo_path = Path(args.path) / logo
        if not logo_path.exists():
            logo_path = BUILTIN_LOGO_PATH / logo
        try:
            with open(logo_path, "r", encoding="utf-8") as logo_file:
                logos.append(Image.from_sexpr(parse_sexp(logo_file.read())))
        except IOError:
            log.error(f"{logo} not found")
    return logos


# Load logos already present on the schematic by checking Y pos of the img
def get_current_logos(schematic: Schematic) -> List[Image]:
    logos: List[Image] = []
    for img in schematic.images:
        # TODO: extract magic numbers to constants as percentage of page size
        if schematic.paper.paperSize == "A3":
            if img.position.Y >= 254 and img.position.Y <= 285:
                logos.append(img)
        elif schematic.paper.paperSize == "A4":
            if img.position.Y >= 165 and img.position.Y <= 195:
                logos.append(img)

    return logos


def position_logos(logos: List[Image], schematic: Schematic, args: argparse.Namespace) -> None:
    # mm to px ratio in Eschema
    mm_px_ratio = 0.0846
    logo_clearance = 5
    # Holds right edges of the images
    logo_right_edge: List[Union[float, int]] = []
    logos_height = args.size
    log.debug(f"Logo height = {logos_height}")
    for i, logo in enumerate(logos):
        # set scale
        decoded_logo = decode_img(img=logo)
        scale_factor = logos_height / decoded_logo.size[1]
        logo.scale = scale_factor
        log.debug(f"Scale factor = {scale_factor}")
        # set X position
        logo_width = decoded_logo.size[0] * scale_factor * mm_px_ratio
        # most left logo
        if i == 0:
            logo.position.X = 15 + logo_width / 2
        # rest of the logos
        else:
            logo.position.X = logo_right_edge[i - 1] + logo_width / 2 + logo_clearance
        logo_right_edge.append(logo.position.X + logo_width / 2)
        log.debug(f"X position = {logo.position.X}")
        # set Y position
        if schematic.paper.paperSize == "A3":
            logo.position.Y = 270
        elif schematic.paper.paperSize == "A4":
            logo.position.Y = 180
        log.debug(f"Position = {logo.position}")


# converts base64 to PIL image
def decode_img(img: Image) -> PIL_Image.Image:
    image_mime_data = img.data  # MIME base 64 data
    image_mime_data = "".join(image_mime_data)
    imgdata = base64.b64decode(image_mime_data)
    return PIL_Image.open(io.BytesIO(imgdata))
