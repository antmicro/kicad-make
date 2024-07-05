import argparse
import json
import logging
import sys
from pathlib import Path

from kiutils.dru import DesignRules
from kiutils.utils import sexpr
from common.kicad_project import KicadProject

log = logging.getLogger(__name__)

TEMPLATES_NAME = "pcb-drc-templates"
TEMPLATES_DECRIPTION_NAME = "description.json"


def read_json_file(file_path: Path) -> dict:
    content = {}
    try:
        with open(file_path) as file_content:
            content = json.load(file_content)
    except (json.JSONDecodeError, OSError) as error_descriptor:
        log.error(f"Can't read file {file_path}, due to {error_descriptor} ")
        sys.exit(1)
    return content


def save_json_file(file_path: Path, file_content: dict) -> None:
    try:
        with open(file_path, "w") as file:
            json.dump(file_content, file, indent=2)
    except (TypeError, OSError) as error_descriptor:
        log.error(f"Can't save file {file_path}, due to {error_descriptor} ")
        sys.exit(1)


def get_extenstion_from_type(template_type: str) -> str:
    if template_type == "DRC":
        return ".kicad_pro"
    if template_type == "DRU":
        return ".kicad_dru"

    log.error(f"Unknown template_type: {template_type}")
    sys.exit(1)


def find_templates(local_share_dir: Path, template_type: str) -> dict:
    extension = get_extenstion_from_type(template_type)
    templates_path = local_share_dir / TEMPLATES_NAME
    templates: dict = dict(template_type=list())

    if not templates_path.exists():
        log.error("DRC templates path doesn't exist")
        return templates

    templates[template_type] = [template.stem for template in list(templates_path.glob(f"*{extension}"))]

    if not len(templates[template_type]):
        log.warning(f"No valid {template_type} templates found")

    return templates


def read_description_file(local_share_dir: Path) -> dict:
    return read_json_file(local_share_dir / TEMPLATES_NAME / TEMPLATES_DECRIPTION_NAME)


def show_templates(local_share_dir: Path, templates: dict, kind: str) -> None:
    descriptors = read_description_file(local_share_dir)

    print(" ")
    print(f"Available {kind} templates:")
    for template in templates[kind]:
        if template in descriptors:
            template = template + " - " + descriptors[template]
        print(template)


def extract_drc_rules(kicad_file_content: dict) -> dict:
    if (
        "board" in kicad_file_content
        and "design_settings" in kicad_file_content["board"]
        and "rules" in kicad_file_content["board"]["design_settings"]
    ):
        log.debug("Loaded DRC rules")
        return kicad_file_content["board"]["design_settings"]["rules"]

    log.error("No DRC rules inside kicad_pro file")
    sys.exit(1)


def get_drc_rules(template_path: Path) -> dict:
    file_content = read_json_file(template_path)

    return extract_drc_rules(file_content)


def set_drc_template(templates_share_path: Path, template: Path, target_file: Path) -> None:
    drc_rules = get_drc_rules(templates_share_path / TEMPLATES_NAME / template)
    target_file_content = read_json_file(target_file)
    if "board" not in target_file_content:
        target_file_content["board"] = {}
    if "design_settings" not in target_file_content["board"]:
        target_file_content["board"]["design_settings"] = {}

    target_file_content["board"]["design_settings"]["rules"] = drc_rules

    save_json_file(target_file, target_file_content)
    log.info("Rules updated successfully")


def read_dru_file(file_path: Path) -> DesignRules:
    try:
        dru_file = list()
        with open(file_path, "r") as file:
            for line in file:
                if line.strip().startswith("#"):
                    continue
                dru_file.append(line)
        data = "".join(dru_file)
        data = f"({data})"
        design_rules = DesignRules().from_sexpr(sexpr.parse_sexp(data))
        design_rules.filePath = str(file_path)
        log.debug(f"Loaded {file_path} ")
        return design_rules
    except Exception as error_descriptor:
        log.error(f"Can't load {file_path}, due to {error_descriptor} ")
        sys.exit(1)


def create_dru_file(file_path: str) -> bool:
    dru = DesignRules().create_new()
    try:
        dru.to_file(file_path)
        log.debug(f"Created {file_path}")
    except Exception as error_descriptor:
        log.error(f"Can't create DRU file, due to {error_descriptor}")
        return False

    return True


def create_project_dru_if_not_exists(project: KicadProject) -> None:
    if project.dru_file is None:
        log.info("No DRU file in project directory")
        log.info("Converting .kicad_pro file to .kicad_dru file.")
        project.dru_file = project.pro_file.replace(project.pro_ext, project.dru_ext)
        if not create_dru_file(project.dru_file):
            log.error(f"Can't create DRU file in {project.dru_file}")
            sys.exit(1)


def set_dru_rules(templates_share_path: Path, template: Path, target_file: Path) -> None:
    dru_template = read_dru_file(Path(templates_share_path / TEMPLATES_NAME / template))
    dru_target = read_dru_file(target_file)
    for rule in dru_template.rules:
        if rule not in dru_target.rules:
            dru_target.rules.append(rule)

    try:
        dru_target.to_file()
        log.info("Rules updated successfully")
    except Exception as error_descriptor:
        log.error(f"Can't save DRU file, due to {error_descriptor}")
        sys.exit(1)


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Register parser and its arguments as subparser."""

    set_drc_parser = subparsers.add_parser("set-drc", help="Sets `DRC` rules from provided template")
    set_drc_parser.add_argument(
        "-s",
        "--drc",
        nargs="?",
        default=None,
        help="Manufacturer DRC rules set",
    )

    set_dru_parser = subparsers.add_parser("set-dru", help="Sets `DRU` rules from provided template")
    set_dru_parser.add_argument(
        "-u",
        "--dru",
        nargs="?",
        default=None,
        help="Set DRU rules",
    )

    set_drc_parser.set_defaults(func=run_drc)
    set_dru_parser.set_defaults(func=run_dru)


def run_drc(project: KicadProject, args: argparse.Namespace) -> None:
    templates = find_templates(project.local_share_path, "DRC")

    if args.drc is None:
        show_templates(project.local_share_path, templates, "DRC")
        return

    if args.drc not in templates["DRC"]:
        log.error(f"Selected {args.drc} DRC template doesn't exist")
        sys.exit(1)

    if not project.pro_file:
        log.error("No .kicad_pro file in project directory")
        sys.exit(1)

    set_drc_template(
        project.local_share_path, Path(args.drc).with_suffix(f".{project.pro_ext}"), Path(project.pro_file)
    )


def run_dru(project: KicadProject, args: argparse.Namespace) -> None:
    templates = find_templates(project.local_share_path, "DRU")

    if args.dru is None:
        show_templates(project.local_share_path, templates, "DRU")
        return

    if args.dru not in templates["DRU"]:
        log.error(f"Selected {args.dru} DRU template doesn't exist")
        sys.exit(1)

    if not project.dru_file:
        log.error("No .kicad_dru file in project directory")
        sys.exit(1)

    if args.dru in templates["DRU"]:
        create_project_dru_if_not_exists(project)
        set_dru_rules(
            project.local_share_path, Path(args.dru).with_suffix(f".{project.dru_ext}"), Path(project.dru_file)
        )
