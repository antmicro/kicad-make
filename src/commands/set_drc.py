import argparse
import json
import logging
import os
import sys
from json import JSONDecodeError

from kiutils.dru import DesignRules

from common.kicad_project import KicadProject

log = logging.getLogger(__name__)


def read_json_file(file_path: str) -> dict:
    """Read project file.

    Parameters
    ----------
    file_path (str): path to `.kicad_pro` file

    Returns
    -------
        content (dict): content of a file
    """
    log.debug(f"Loading {file_path}")

    content = {}
    try:
        with open(file_path) as file_content:
            content = json.load(file_content)
    except (JSONDecodeError, OSError) as error_descriptor:
        log.error(f"Can't read file {file_path}, due to {error_descriptor} ")
    return content


def save_json_file(file_path: str, file_content: dict) -> bool:
    """Save json data to file.

    Parameters
    ----------
        file_path (str): path to file
        file_content (str): content to save

    Return:
        (bool): True if saved successfully, False if not
    """
    try:
        with open(file_path, "w") as file:
            json.dump(file_content, file)
        return True
    except (TypeError, OSError) as error_descriptor:
        log.error(f"Can't save file {file_path}, due to {error_descriptor} ")
        return False


def fix_file_extension(file_name: str, file_extension: str = ".kicad_pro") -> str:
    """Check if file_name have a 'valid extension'.

    If the 'valid extension' not exist it will be added.

    Parameters
    ----------
        file_name (str): file name to check
        file_extension (str): file extension to check
    Returns:
        file_name (str): file name with

    """
    ext_lenght = len(file_extension)
    if len(file_name) >= ext_lenght:
        if file_name[-ext_lenght:] != file_extension:
            file_name = file_name + file_extension
    else:
        # if file length is smaller than 10 chars, there is no way that file
        # ends with file extension
        file_name = file_name + file_extension

    return file_name


def create_templates_path() -> str:
    """Create path to DRC templates.

    Returns
    -------
        drc_templates_path (str): full path to DRC templates directory

    """
    return os.path.expandvars("$HOME/.local/share/pcb-drc-templates")


def find_files(search_path: str) -> list:
    """Find files in provided directory.

    Parameters
    ----------
        search_path (str): path to search directory
    Returns:
        files (list): list of files in search_path
    """
    log.debug(f"Searching for files in {search_path}")

    files = []
    try:
        files = os.listdir(search_path)
    except FileNotFoundError:
        log.error("Template path not exist")

    return files


def filter_files_by_extension(files: list, extension: str) -> list:
    """Return list of files with matching extensions.

    Parameters
    ----------
         files (list): raw list of files
         extension (str): extension to search for
    Returns:
       filtered_files (list): list of files with matching extensions
    """
    return [file for file in files if extension in file]


def find_kicad_pro_files(files: list) -> list:
    """Search for KiCad project files (*.kicad_pro).

    Parameters
    ----------
        files (str): list of files inside templates folder
    Returns:
        kicad_pro_files (str): list of kicad_pro files (just file names without
                               extensions)

    """
    filtered_files = filter_files_by_extension(files, ".kicad_pro")

    kicad_pro_files = [file.replace(".kicad_pro", "") for file in filtered_files]

    return sorted(kicad_pro_files)


def find_kicad_dru_files(files: list) -> list:
    """Search for KiCad DRU files (*.kicad_dru).

    Parameters
    ----------
        files (str): list of files inside templates folder
    Returns:
        kicad_dru_files (str): list of kicad_dru files (just file names without
                               extensions)

    """
    filtered_files = filter_files_by_extension(files, ".kicad_dru")

    kicad_dru_files = [file.replace(".kicad_dru", "") for file in filtered_files]

    return sorted(kicad_dru_files)


def find_templates(silent: bool = True) -> dict:
    """Find both DRC and DRU templates.

    Parameters
    ----------
        silent (bool): Disable logging for this function

    Returns
    -------
        templates (dict): DRC and DRU templates
                  {
                    "DRC": (list) DRC templates
                    "DRU": (list) DRU templates
                  }
    """
    templates_path = create_templates_path()
    templates_files = find_files(templates_path)

    drc_templates = find_kicad_pro_files(templates_files)

    if len(drc_templates) == 0:
        log.error("No DRC templates")
        sys.exit(-1)
    else:
        if not silent:
            log.info(f"Loaded {len(drc_templates)} DRC templates")

    dru_templates = find_kicad_dru_files(templates_files)

    if len(drc_templates) == 0:
        if not silent:
            log.warning("No DRC templates")
        sys.exit(-1)
    else:
        if not silent:
            log.info(
                f"Loaded {len(dru_templates)} custom custom rules templates",
            )

    templates = {}
    templates["DRC"] = drc_templates
    templates["DRU"] = dru_templates

    return templates


def create_description_file_path() -> str:
    """Creates path to DRC templates description file.

    Returns
    -------
        (str): path to description file
    """
    return os.path.expandvars("$HOME/.local/share/pcb-drc-templates/description.json")


def read_description_file() -> dict:
    """Read file that describes DRC templates.

    Returns
    -------
        (dict): dictionary with DRC description
    """
    file_path = create_description_file_path()
    return read_json_file(file_path)


def print_templates(templates: list, descriptors: dict) -> None:
    """Print DRC or DRU template.

    Parameters
    ----------
        templates (list): templates names
        descriptors (dict): templates description,
                            key in descriptors must be name of a template
    Returns:
        None
    """
    for template in templates:
        if template in descriptors:
            template = template + " - " + descriptors[template]
        print(template)


def show_drc_templates() -> None:
    """Print DRC templates."""
    templates = find_templates()
    descriptors = read_description_file()

    print(" ")
    print("Available DRC templates: \n")
    print_templates(templates["DRC"], descriptors)


def show_dru_templates() -> None:
    """Print DRU templates."""
    templates = find_templates()
    descriptors = read_description_file()

    print(" ")
    print("Available custom rules templates: \n")
    print_templates(templates["DRU"], descriptors)


def extract_drc_rules(kicad_file_content: dict) -> dict:
    """Extract DRC rules from KiCad project files.

    Parameters
    ----------
        kicad_file_content (str): content of kicad_pro file

    Returns
    -------
        (dict): set of DRC rules
    """
    if (
        "board" in kicad_file_content
        and "design_settings" in kicad_file_content["board"]
        and "rules" in kicad_file_content["board"]["design_settings"]
    ):
        log.debug("Loaded DRC rules")
        return kicad_file_content["board"]["design_settings"]["rules"]

    log.error("No DRC rules inside kicad_pro file")
    sys.exit(-1)


def get_drc_rules(template_name: str) -> dict:
    """Get DRC rules from DRC template.

    Parameters
    ----------
        template_name (str): Name of the DRC template

    Returns
    -------
        drc_rules (dict): set of DRC rules
    """
    file_name = fix_file_extension(template_name)
    file_path = create_templates_path() + "/" + file_name

    file_content = read_json_file(file_path=file_path)

    return extract_drc_rules(file_content)


def set_drc_template(template: str, target_file: str) -> None:
    """Set DRC rules to kicad project.

    Parameters
    ----------
        template (str):  template name
        target_file (str): kicad project file, where DRC rules will be applied into
    Returns
        None
    """

    drc_rules = get_drc_rules(template_name=template)
    target_file_content = read_json_file(target_file)

    target_file_content["board"]["design_settings"]["rules"] = drc_rules

    save_state = save_json_file(file_path=target_file, file_content=target_file_content)
    if save_state:
        log.info("Rules updated successfully")

    else:
        log.info("An error occurred during update of DRC rules")


def conver_pro_file_path_to_dru(pro_file_path: str) -> str:
    """Convert path to `.kicad_pro` file to path to `.kicad_dru` file.

    Parameters
    ----------
        pro_file_path (str): path to kicad_pro file

    Returns
    -------
        dru_path (str): path to kicad_dru file
    """
    dru_path = pro_file_path.replace("kicad_pro", "kicad_dru")
    log.debug(f"Created DRU file path {dru_path}")
    return dru_path


def read_dru_file(file_path: str) -> DesignRules:
    """Read kicad_dru file.

    Parameters
    ----------
        file_path (str): path to kicad_dru file

    Returns
    -------
        dru_file (DesignRules): Custom design rules
    """
    dru_file = DesignRules()
    try:
        dru_file = DesignRules().from_file(filepath=file_path)
        log.debug(f"Loaded {file_path} ")
    except Exception as error_descriptor:
        log.error(f"Can't load {file_path}, due to {error_descriptor} ")

    return dru_file


def get_dru_template(template_name: str) -> DesignRules:
    """Read custom design rules from DRU template.

    Parameters
    ----------
        template_name (str): name of a template to load

    Returns
    -------
        dru_template (str): Selected DRU template
    """
    file_name = fix_file_extension(template_name, ".kicad_dru")
    file_path = create_templates_path() + "/" + file_name

    return read_dru_file(file_path)


def create_dru_file(file_path: str) -> None:
    """Create empty kicad_dru file.

    Parameters
    ----------
        file_path (str): path to file to create
    Returns
        None
    """
    dru = DesignRules().create_new()
    try:
        dru.to_file(file_path)
        log.debug(f"Created {file_path}")
    except Exception as error_descriptor:
        log.error(f"Can't create DRU file, due to {error_descriptor}")


def save_dru_rules(content: list, target_file: str) -> None:
    """Save DRU rule to kicad_dru file.

    Parameters
    ----------
        content (list): list of custom design rules
        target_file (str): file to save custom design rules into

    Returns
    -------
       None
    """
    dru = DesignRules()
    dru.rules = content
    try:
        dru.to_file(filepath=target_file)
    except Exception as error_descriptor:
        log.error(f"Can't save DRU file, due to {error_descriptor}")


def compare_dru(source: list, target: list) -> list:
    """Return list of custom design rules that are in source but not in target.

    Parameters
    ----------
        source (list): source data
        target (list): target data

    Returns
    -------
        diff (list): difference
    """
    diff = []

    for src_element in source:
        if src_element not in target:
            diff.append(src_element)

    return diff


def set_dru_rules(template: str, target_file: str) -> None:
    """Set custom design rule.

    Parameters
    ----------
        template (str): name of DRU templates
        target_file (str): path to target file
    Returns
        None
    """
    dru_template = get_dru_template(template)
    dru_template = dru_template.rules

    dru_target = read_dru_file(target_file)
    dru_target = dru_target.rules

    diff = compare_dru(dru_template, dru_target)

    save_dru_rules(content=diff + dru_target, target_file=target_file)


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Register parser and its arguments as subparser."""

    set_drc_parser = subparsers.add_parser("set-drc", help="Sets `DRC` and `custom DRC` rules from provided template.")
    set_drc_parser.add_argument(
        "-s",
        nargs="?",
        default="",
        help="Manufacturer DRC rules set.",
    )

    set_drc_parser.add_argument(
        "--no-dru",
        action="store_true",
        help="Do not set custom rules.",
    )

    set_drc_parser.add_argument(
        "-u",
        nargs="?",
        default="",
        help="Set custom rules only.",
    )

    set_drc_parser.set_defaults(func=run)


def main(project: KicadProject, args: argparse.Namespace) -> None:
    """Main module function."""
    templates = find_templates(silent=False)
    drc_templates = templates["DRC"]
    dru_templates = templates["DRU"]

    if args.s == "" and args.u == "":
        show_drc_templates()
        show_dru_templates()
        return

    if args.s is None:
        show_drc_templates()

    elif args.s in drc_templates:
        log.info(f"Selected {args.s} template")
        set_drc_template(template=args.s, target_file=project.pro_file)
        if not args.no_dru and args.s in dru_templates:
            log.debug("No DRU file in project directory")
            project.dru_file = conver_pro_file_path_to_dru(
                pro_file_path=project.pro_file,
            )
            create_dru_file(project.dru_file)
            set_dru_rules(template=args.s, target_file=project.dru_file)
        sys.exit(0)

    if args.u is None:
        show_dru_templates()

    elif args.u in dru_templates:
        log.info(f"Selected {args.u} template")

        if project.dru_file == []:  # project.dru_file is a list when no dru file
            log.debug("No DRU file in project directory")
            project.dru_file = conver_pro_file_path_to_dru(
                pro_file_path=project.pro_file,
            )
            create_dru_file(project.dru_file)

        log.info(f"Selected {args.u} template")
        set_dru_rules(template=args.u, target_file=project.dru_file)


def run(project: KicadProject, args: argparse.Namespace) -> None:
    """Entry function for module."""
    main(project, args)
