from askiff.pro import Project
import logging
import argparse
import copy
import os

from subprocess import CalledProcessError


from common.kicad_project import KicadProject
from common.kmake_helper import run_kicad_cli

log = logging.getLogger(__name__)


def _get_output_paths(kicad_project: KicadProject, check_type: str, output_format: str) -> list[str]:
    extension = "json" if output_format == "json" else "report"
    output_paths = []

    if check_type in ["all", "erc"]:
        output_paths.append(os.path.join(kicad_project.doc_dir, f"{kicad_project.name}_erc.{extension}"))
    if check_type in ["all", "drc"]:
        output_paths.append(os.path.join(kicad_project.doc_dir, f"{kicad_project.name}_drc.{extension}"))

    return output_paths


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    # Register parser and its arguments as subparser
    check_parser = subparsers.add_parser("check", help="Run checks over project including ERC, DRC and spelling check")

    check_parser.add_argument(
        "check_type", choices=["all", "erc", "drc", "spell"], help="Select type check", default="all"
    )
    check_parser.add_argument("--all", action="store_true", help="Include errors, warnings and exclusions")
    check_parser.add_argument("--errors", help="Include errors", action="store_true", default=False)
    check_parser.add_argument("--warnings", help="Include warnings", action="store_true", default=False)
    check_parser.add_argument("--exclusions", action="store_true", help="Include exclusions", default=False)
    check_parser.add_argument("--format", help="Select output format", choices=["report", "json"], default="report")
    check_parser.add_argument("--units", help="Select report units", choices=["mm", "in", "mils"], default="mm")
    check_parser.set_defaults(func=run)


def check_spelling(kpro: Project) -> None:
    pass


def run(kicad_project: KicadProject, args: argparse.Namespace) -> None:
    """
    Main command function
    """
    kpro = Project(kicad_project.dir)

    cli_args = []

    if args.all:
        log.info("Severity level set to warning, error, exclusions")
        if args.warnings or args.errors or args.exclusions:
            log.error("--all can't be combinded with other severities")
            exit(1)
        args.warnings = True
        args.errors = True
        args.exclusions = True

    if (not args.warnings) and (not args.errors) and (not args.exclusions):
        log.info("Severity not specified, using defaults")

    if args.warnings:
        log.info("Enabling warning")
        cli_args.append("--severity-warning")
    if args.errors:
        log.info("Enabling level set to error")
        cli_args.append("--severity-error")
    if args.exclusions:
        log.info("Enabling exclusions")
        cli_args.append("--severity-exclusions")

    cli_args.append("--units")
    cli_args.append(args.units)

    cli_args.append("--exit-code-violations")

    kicad_project.get_project_dir()
    kicad_project.get_pro_file_name_from_dir(kicad_project.dir)

    cli_args.append("--output")
    cli_args_sch = ["sch", "erc"] + copy.deepcopy(cli_args)
    cli_args_pcb = ["pcb", "drc"] + copy.deepcopy(cli_args)

    if args.format == "json":
        cli_args_sch.append(f"doc/{kicad_project.name}_erc.json")
        cli_args_sch.append("--format")
        cli_args_sch.append("json")

        cli_args_pcb.append(f"doc/{kicad_project.name}_drc.json")
        cli_args_pcb.append("--format")
        cli_args_pcb.append("json")
    else:
        cli_args_sch.append(f"doc/{kicad_project.name}_erc.report")
        cli_args_pcb.append(f"doc/{kicad_project.name}_drc.report")

    cli_args_sch.append(f"{kicad_project.name}.kicad_sch")
    cli_args_pcb.append(f"{kicad_project.name}.kicad_pcb")

    kicad_project.create_doc_dir()
    output_paths = _get_output_paths(kicad_project, args.check_type, args.format)

    failed = False
    try:
        if args.check_type in ["all", "erc"]:
            run_kicad_cli(cli_args_sch, False)
    except CalledProcessError:
        failed = True

    try:
        if args.check_type in ["all", "drc"]:
            run_kicad_cli(cli_args_pcb, False)
    except CalledProcessError:
        failed = True

    if args.check_type in ["all", "spell"]:
        check_spelling(kpro)

    if failed:
        log.info("At least one error exists in design")
        for output_path in output_paths:
            log.info("Check report written to %s", output_path)
        exit(1)
    else:
        log.info("No errors in design")
        for output_path in output_paths:
            log.info("Check report written to %s", output_path)
