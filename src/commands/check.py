import argparse
import copy
import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from itertools import chain
from pathlib import Path
from subprocess import CalledProcessError

from askiff import Project
from askiff.common import Position
from askiff.gritems import GrText, GrTextBox
from platformdirs import PlatformDirs
from rich.console import Console
from rich.table import Table
from spellchecker import SpellChecker as PySpellChecker

from common.kicad_project import KicadProject
from common.kmake_helper import run_kicad_cli

log = logging.getLogger(__name__)


def _get_output_paths(pro: KicadProject, check_type: str, output_format: str) -> list[str]:
    extension = "json" if output_format == "json" else "report"
    output_paths = []

    if check_type in ["all", "both", "erc"]:
        output_paths.append(pro.doc_dir / f"{pro.project_name}_erc.{extension}")
    if check_type in ["all", "both", "drc"]:
        output_paths.append(pro.doc_dir / f"{pro.project_name}_drc.{extension}")

    return output_paths


def _add_erc_drc_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--all", action="store_true", help="Include errors, warnings and exclusions")
    p.add_argument("--errors", help="Include errors", action="store_true", default=False)
    p.add_argument("--warnings", help="Include warnings", action="store_true", default=False)
    p.add_argument("--exclusions", action="store_true", help="Include exclusions", default=False)
    p.add_argument("--format", help="Select output format", choices=["report", "json"], default="report")
    p.add_argument("--units", help="Select report units", choices=["mm", "in", "mils"], default="mm")


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    # Register parser and its arguments as subparser
    check_parser = subparsers.add_parser("check", help="Run checks over project including ERC, DRC and spelling check")
    check_parser = check_parser.add_subparsers(
        title="Check Subcommands",
        dest="check_subcommand",
        help='To display help for specific subcommand use "kmake check SUBCOMMAND -h"',
        required=True,
    )

    check_parser_erc = check_parser.add_parser("erc", help="Run ERC over project")
    _add_erc_drc_args(check_parser_erc)
    check_parser_erc.set_defaults(func=run)

    check_parser_drc = check_parser.add_parser("drc", help="Run DRC over project")
    _add_erc_drc_args(check_parser_drc)
    check_parser_drc.set_defaults(func=run)

    check_parser_both = check_parser.add_parser("both", help="Run both DRC & ERC over project")
    _add_erc_drc_args(check_parser_both)
    check_parser_both.set_defaults(func=run)

    check_parser_all = check_parser.add_parser("all", help="Run ERC, DRC & spell check over project")
    _add_erc_drc_args(check_parser_all)
    check_parser_all.set_defaults(func=run)

    check_parser_spell = check_parser.add_parser("spell", help="Run spell check over project")
    check_parser_spell.add_argument("--file", help="Check this file instead KiCad files", action="store")
    check_parser_spell.add_argument("--list-unknown", help="Print list of unknown words to stdout", action="store_true")
    check_parser_spell.set_defaults(func=run)


@dataclass
class SpellCheckIssueContext:
    file: Path | None
    object_type: str
    layer: str
    position: Position | None
    cell: str = ""

    def row_part(self) -> tuple[str, str, str]:
        layer = "" if not self.layer else f" {self.layer:>10}"
        return (
            self.file.name if self.file else "",
            self.object_type,
            f"(X,Y): ({self.position.x:8.3f}, {self.position.y:8.3f}){layer}{self.cell}" if self.position else "",
        )


class SpellCheckIssueType(Enum):
    CAPITALIZATION = 0
    DICTIONARY = 1
    INCORRECT_CASE_OF_ALLOWED = 2
    FORBIDDEN = 3


@dataclass
class SpellCheckIssue:
    type: SpellCheckIssueType
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
                self.pyspellchecker.word_frequency.load_text_file(path)

        allowed_cs = path_allowed_cs.read_text().splitlines() if path_allowed_cs.exists() else []
        self.allowed_case_sensitive = {self.norm_str(item): item for item in allowed_cs}
        forbidden = path_forbidden.read_text().splitlines() if path_forbidden.exists() else []
        self.forbidden = {phrase: comment for phrase, _, comment in (item.partition("#") for item in forbidden)}

    def norm_str(self, text: str) -> str:
        return self.str_normalize_regex.sub(" ", text.strip()).lower()

    def split_str(self, text: str) -> Iterable[str]:
        split = (t.strip("+-#~$:,.\"'(){}[]0123456789") for t in text.split())
        return (word for word in split if word and word.isalpha())

    def check_str_std_dictionary_check(self, text: str, context: SpellCheckIssueContext) -> None:
        """Checks if all words in `text` are present in dictionary (case insensitive)"""
        for word in self.split_str(text):
            if self.pyspellchecker.unknown((word,)):
                correction = self.pyspellchecker.correction(word)
                comment = f"Did You mean: {correction}" if correction else ""
                self.issues.append(SpellCheckIssue(SpellCheckIssueType.DICTIONARY, context, word, text, comment))

    def check_str_std_capitalization_check(self, text: str, context: SpellCheckIssueContext) -> None:
        """Checks for unusual capitalization of words (eg. uSb) (except when word is in allowed-case-sensitive)"""
        for word in self.split_str(text):
            if not any((word.islower(), word.isupper(), word.istitle())):
                if word in self.allowed_case_sensitive.values():
                    continue
                self.issues.append(
                    SpellCheckIssue(
                        SpellCheckIssueType.CAPITALIZATION, context, word, text, "Nonstandard capitalization"
                    )
                )

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
                    self.issues.append(
                        SpellCheckIssue(
                            SpellCheckIssueType.INCORRECT_CASE_OF_ALLOWED,
                            context,
                            phrase_norm,
                            text,
                            f"Did You mean: `{phrase}`",
                        )
                    )

    def check_str_forbidden_pattern_usage(self, text: str, context: SpellCheckIssueContext) -> None:
        """Reports forbidden phrase usage in text"""
        norm_text = self.norm_str(text)
        for phrase, comment in self.forbidden.items():
            comment = f": {comment}" if comment else ""
            if self.norm_str(phrase) in norm_text:
                self.issues.append(
                    SpellCheckIssue(SpellCheckIssueType.FORBIDDEN, context, phrase, text, "Forbidden phrase" + comment)
                )

    def check_str(self, text: str, context: SpellCheckIssueContext) -> None:
        """Perform complete string correctness check"""
        text = text.encode().decode("unicode_escape")
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
                    context = SpellCheckIssueContext(kfile.fs_path, "Text", layer, gritem.position)
                    self.check_str(gritem.text, context)
                elif isinstance(gritem, GrTextBox):
                    context = SpellCheckIssueContext(kfile.fs_path, "TextBox", layer, gritem.box.position)
                    self.check_str(gritem.text, context)
            for table in kfile.tables:
                layer = str(getattr(table, "layer", ""))
                for idx, cell in enumerate(table.cells):
                    col = idx % table.column_count
                    row = idx // table.column_count
                    context = SpellCheckIssueContext(
                        kfile.fs_path, "Table", layer, cell.box.position, f" (col:{col}, row:{row})"
                    )
                    self.check_str(cell.text, context)

            for meta_name in ("title", "date", "rev", "company"):
                meta = getattr(kfile.title_block, meta_name)
                context = SpellCheckIssueContext(kfile.fs_path, f"TitleBlock: {meta_name}", "", None)
                self.check_str(meta, context)
            for comment in kfile.title_block.comment:
                context = SpellCheckIssueContext(kfile.fs_path, f"TitleBlock: comment {comment.number}", "", None)
                self.check_str(comment.content, context)

    def check_file(self, path: Path) -> None:
        """Check text in file"""
        context: SpellCheckIssueContext
        file_lines = path.read_text().splitlines()
        for idx, line in enumerate(file_lines):
            context = SpellCheckIssueContext(path, f"line:{idx}", "", None)
            self.check_str(line, context)

    def prepare_report(self, print_context: bool = False, list_unknown: bool = False) -> None:
        unrecognized = set()
        console = Console()

        table = Table(show_lines=True)
        table.add_column("Incorrect")
        table.add_column("Comment")
        table.add_column("File")
        table.add_column("Object")
        table.add_column("Location")
        debug = False
        if log.isEnabledFor(logging.DEBUG) or print_context:
            debug = True
            table.add_column("Context text")

        for issue in self.issues:
            if issue.type in (SpellCheckIssueType.DICTIONARY, SpellCheckIssueType.CAPITALIZATION):
                unrecognized.add(issue.incorrect_part)
            table.add_row(
                "`" + issue.incorrect_part + "`",
                issue.comment,
                *issue.context.row_part(),
                *((issue.text.strip(),) if debug else ()),
            )

        if list_unknown:
            console.print("\n".join(unrecognized))
        else:
            console.print(table)


def run(pro: KicadProject, args: argparse.Namespace) -> None:
    """
    Main command function
    """
    pro.create_doc_dir()
    fmt = getattr(args, "format", "")
    output_paths = _get_output_paths(pro, args.check_subcommand, fmt)

    if args.check_subcommand in ["all", "both", "drc", "erc"]:
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

        cli_args.append("--output")
        cli_args_sch = ["sch", "erc"] + copy.deepcopy(cli_args)
        cli_args_pcb = ["pcb", "drc"] + copy.deepcopy(cli_args)

        if args.format == "json":
            cli_args_sch.append(f"doc/{pro.project_name}_erc.json")
            cli_args_sch.append("--format")
            cli_args_sch.append("json")

            cli_args_pcb.append(f"doc/{pro.project_name}_drc.json")
            cli_args_pcb.append("--format")
            cli_args_pcb.append("json")
        else:
            cli_args_sch.append(f"doc/{pro.project_name}_erc.report")
            cli_args_pcb.append(f"doc/{pro.project_name}_drc.report")

        cli_args_sch.append(f"{pro.project_name}.kicad_sch")
        cli_args_pcb.append(f"{pro.project_name}.kicad_pcb")

    failed = False
    if args.check_subcommand in ["all", "both", "erc"]:
        try:
            run_kicad_cli(cli_args_sch, False)
        except CalledProcessError:
            failed = True

    if args.check_subcommand in ["all", "both", "drc"]:
        try:
            run_kicad_cli(cli_args_pcb, False)
        except CalledProcessError:
            failed = True

    if args.check_subcommand in ["all", "spell"]:
        spell = SpellCheck()
        args_file = getattr(args, "file", None)
        list_unknown = getattr(args, "list_unknown", False)

        if args_file:
            spell.check_file(Path(args_file))
        else:
            spell.check_project(pro)

        if spell.issues:
            failed = True
            spell.prepare_report(bool(args_file), list_unknown)

        if list_unknown:
            exit(0)

    if failed:
        log.info("At least one error exists in design")
        for output_path in output_paths:
            log.info("Check report written to %s", output_path)
        exit(1)
    else:
        log.info("No errors in design")
        for output_path in output_paths:
            log.info("Check report written to %s", output_path)
