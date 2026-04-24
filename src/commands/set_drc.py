import argparse
import json
import logging
import sys
from pathlib import Path

from askiff.dru import DesignRulesFile

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


def get_extension_from_type(template_type: str) -> str:
    if template_type == "DRC":
        return ".kicad_pro"
    if template_type == "DRU":
        return ".kicad_dru"

    log.error(f"Unknown template_type: {template_type}")
    sys.exit(1)


def find_templates(local_share_dir: Path, template_type: str) -> dict:
    extension = get_extension_from_type(template_type)
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


def set_drc_template(pro: KicadProject, template: Path) -> None:
    drc_rules = get_drc_rules(pro.local_share_path / TEMPLATES_NAME / template)
    target_file_content = read_json_file(pro.kicad_pro_path)
    if "board" not in target_file_content:
        target_file_content["board"] = {}
    if "design_settings" not in target_file_content["board"]:
        target_file_content["board"]["design_settings"] = {}

    target_file_content["board"]["design_settings"]["rules"] = drc_rules

    save_json_file(pro.kicad_pro_path, target_file_content)
    log.info("Rules updated successfully")


def read_dru_file(file_path: Path) -> DesignRulesFile:
    try:
        design_rules = DesignRulesFile.from_file(file_path)
        log.debug(f"Loaded {file_path} ")
        return design_rules
    except Exception as error_descriptor:
        log.error(f"Can't load {file_path}, due to {error_descriptor} ")
        sys.exit(1)


def create_project_dru_if_not_exists(pro: KicadProject) -> None:
    if pro.dru_root is None:
        log.info("No DRU file in project directory")
        pro.dru_root = DesignRulesFile(fs_path=pro.kicad_pro_path.with_suffix(DesignRulesFile.fs_ext))


def set_dru_rules(pro: KicadProject, template: Path) -> None:
    dru_template = read_dru_file(pro.local_share_path / TEMPLATES_NAME / template)
    current_rules_names = {rule.name for rule in pro.dru_root.rules}
    for rule in dru_template.rules:
        if rule.name not in current_rules_names:
            pro.dru_root.rules.append(rule)
    try:
        pro.dru_root.to_file()
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


def run_drc(pro: KicadProject, args: argparse.Namespace) -> None:
    templates = find_templates(pro.local_share_path, "DRC")

    if args.drc is None:
        show_templates(pro.local_share_path, templates, "DRC")
        return

    if args.drc not in templates["DRC"]:
        log.error(f"Selected {args.drc} DRC template doesn't exist")
        sys.exit(1)

    if not pro.kicad_pro_path:
        log.error("No .kicad_pro file in project directory")
        sys.exit(1)

    set_drc_template(pro, Path(args.drc).with_suffix(".kicad_pro"))


def run_dru(pro: KicadProject, args: argparse.Namespace) -> None:
    templates = find_templates(pro.local_share_path, "DRU")

    if args.dru is None:
        show_templates(pro.local_share_path, templates, "DRU")
        return

    if args.dru not in templates["DRU"]:
        log.error(f"Selected {args.dru} DRU template doesn't exist")
        sys.exit(1)

    create_project_dru_if_not_exists(pro)
    set_dru_rules(pro, Path(args.dru).with_suffix(DesignRulesFile.fs_ext))
