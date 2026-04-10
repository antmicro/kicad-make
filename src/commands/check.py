from rich.table import Table
from rich.console import Console
import argparse
import copy
import logging
import os
import re
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import chain
from pathlib import Path
from subprocess import CalledProcessError

from askiff.gritems import GrTable, GrText, GrTextBox
from askiff import Project
from askiff.common import Position
from platformdirs import PlatformDirs
from spellchecker import SpellChecker as PySpellChecker

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


@dataclass
class SpellCheckIssueContext:
    file: str
    object_type: str
    layer: str
    position: Position
    cell: str = ""

    def row_part(self) -> tuple[str, str, str]:
        layer = "" if not self.layer else f" {self.layer:>10}"
        return (
            self.file,
            self.object_type,
            f"(X,Y): ({self.position.x:8.3f}, {self.position.y:8.3f}){layer}{self.cell}",
        )


@dataclass
class SpellCheckIssue:
    context: SpellCheckIssueContext
    incorrect_part: str
    text: str
    comment: str


class SpellCheck:
    pyspellchecker: PySpellChecker
    issues: list[SpellCheckIssue]
    allowed_case_sensitive: dict[str, str]
    forbidden: dict[str, str]
    str_normalize_regex: re.Pattern[str] = re.compile(r"[_\-\s]")

    def __init__(self) -> None:
        self.issues = []

        dirs = PlatformDirs("kmake", "Antmicro")
        template_dir = Path(dirs.user_config_dir) / "templates" / "check_spell"
        path_allowed = template_dir / "allowed.txt"
        path_allowed_cs = template_dir / "allowed-case-sensitive.txt"
        path_forbidden = template_dir / "forbidden.txt"

        self.pyspellchecker = PySpellChecker()
        for path in (path_allowed, path_allowed_cs):
            if path.exists():
                self.pyspellchecker.word_frequency.load_text_file()

        allowed_cs = path_allowed_cs.read_text().splitlines() if path_allowed_cs.exists() else []
        self.allowed_case_sensitive = {self.norm_str(item): item for item in allowed_cs}
        forbidden = path_forbidden.read_text().splitlines() if path_forbidden.exists() else []
        self.forbidden = {phrase: comment for phrase, _, comment in (item.partition("#") for item in forbidden)}

    def norm_str(self, text: str) -> str:
        return self.str_normalize_regex.sub(" ", text)

    def check_str_std_dictionary_check(self, text: str, context: SpellCheckIssueContext) -> None:
        """Checks if all words in `text` are present in dictionary (case insensitive)"""
        for word in text.split():
            if self.pyspellchecker.unknown(word):
                candidates = self.pyspellchecker.candidates(word)
                self.issues.append(SpellCheckIssue(context, word, text, f"Did You mean: {candidates}"))

    def check_str_std_capitalization_check(self, text: str, context: SpellCheckIssueContext) -> None:
        """Checks for unusual capitalization of words (eg. uSb) (except when word is in allowed-case-sensitive)"""
        for word in text.split():
            if not any((word.islower(), word.isupper(), word.istitle())) and word.isalpha():
                if word in self.allowed_case_sensitive.values():
                    continue
                self.issues.append(SpellCheckIssue(context, word, text, "Nonstandard capitalization"))

    def check_str_incorrect_pattern_usage(self, text: str, context: SpellCheckIssueContext) -> None:
        """Reports incorrect usage of phrases in text

        Catches things like (assuming phrase is in allowed-case-sensitive):
        * `csi` instead of `CSI`
        * `USB Type C` instead of `USB Type-C`
        """

        normalized = self.norm_str(text)

        for phrase_norm, phrase in self.allowed_case_sensitive.items():
            for match in re.finditer(phrase_norm, normalized):
                org_text_match = text[match.start() : match.end()]
                if org_text_match != phrase:
                    self.issues.append(SpellCheckIssue(context, phrase_norm, text, f"Did You mean: `{phrase}`"))

    def check_str_forbidden_pattern_usage(self, text: str, context: SpellCheckIssueContext) -> None:
        """Reports forbidden phrase usage in text"""
        for phrase, comment in self.allowed_case_sensitive.items():
            comment = f": {comment}" if comment else ""
            if phrase in text:
                self.issues.append(SpellCheckIssue(context, phrase, text, "Forbidden phrase" + comment))

    def check_str(self, text: str, context: SpellCheckIssueContext) -> None:
        """Perform complete string correctness check"""
        self.check_str_incorrect_pattern_usage(text, context)
        self.check_str_forbidden_pattern_usage(text, context)
        self.check_str_std_dictionary_check(text, context)
        self.check_str_std_capitalization_check(text, context)

    def check_project(self, kpro: Project) -> None:
        """Check text elements in project files"""
        context: SpellCheckIssueContext

        for kfile in chain(kpro.sch, kpro.pcb):
            for gritem in kfile.graphic_items:
                layer = str(getattr(gritem, "layer", ""))
                if isinstance(gritem, GrText):
                    context = SpellCheckIssueContext(kfile._fs_path.name, "Text", layer, gritem.position)
                    self.check_str(gritem.text, context)
                elif isinstance(gritem, GrTextBox):
                    context = SpellCheckIssueContext(kfile._fs_path.name, "TextBox", layer, gritem.box.position)
                    self.check_str(gritem.text, context)
                elif isinstance(gritem, GrTable):
                    for idx, cell in enumerate(gritem.cells):
                        col = idx % gritem.column_count
                        row = idx // gritem.column_count
                        context = SpellCheckIssueContext(
                            kfile._fs_path.name, "Table", layer, cell.box.position, f"{col}:{row}(col:row)"
                        )
                        self.check_str(cell.text, context)

    def prepare_report(self, path: Path) -> None:
        _fmt = path.suffix[1:]
        console = Console()

        table = Table()
        table.add_column("Incorrect")
        table.add_column("Comment")
        table.add_column("File")
        table.add_column("Object")
        table.add_column("Location")
        debug = False
        if log.isEnabledFor(logging.DEBUG):
            debug = True
            table.add_column("Context text")

        for issue in self.issues:
            table.add_row(
                "`" + issue.incorrect_part + "`",
                issue.comment,
                *issue.context.row_part(),
                *((issue.text,) if debug else ()),
            )

        console.print(table)


def run(kicad_project: KicadProject, args: argparse.Namespace) -> None:
    """
    Main command function
    """
    kpro = Project(kicad_project.dir).load()

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
        spell = SpellCheck()
        spell.check_project(kpro)
        if spell.issues:
            failed = True
            report_path = Path(kicad_project.doc_dir) / f"{kicad_project.name}_spell_check.{args.format}"
            spell.prepare_report(report_path)

    if failed:
        log.info("At least one error exists in design")
        for output_path in output_paths:
            log.info("Check report written to %s", output_path)
        exit(1)
    else:
        log.info("No errors in design")
        for output_path in output_paths:
            log.info("Check report written to %s", output_path)
