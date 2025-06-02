import argparse
import logging
import sys
import datetime
import os

from kiutils.items.common import TitleBlock
from kiutils.board import Board
from kiutils.schematic import Schematic
from kiutils.items.common import PageSettings
from common.kicad_project import KicadProject
from .prettify import run as prettify
from typing import Union


log = logging.getLogger(__name__)


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Register parser and its arguments as subparser."""
    init_project_parser = subparsers.add_parser("init-project", help="Initialize KiCad project.")
    init_project_parser.add_argument("-c", "--company", dest="company", help="Company name.")
    init_project_parser.add_argument("-t", "--title", nargs="*", dest="title", help="Project title.", required=True)
    init_project_parser.add_argument(
        "--force-title", dest="force_title", action="store_true", help="Everride existing title."
    )
    init_project_parser.add_argument("-s", "--size", dest="size", default="A3", help="Page size, default A3.")
    init_project_parser.add_argument(
        "-r",
        "--reload",
        dest="reload",
        action="store_true",
        help="Remove project info except: company name, page size, and project title",
    )

    init_project_parser.set_defaults(func=run)


def set_title_block(
    title_block: TitleBlock,
    company: str,
    date: str = "",
    revision: str = "1.0.0",
    title: Union[str, bool] = False,
    reload: bool = False,
) -> TitleBlock:
    """Set: revision, date, company and project title into title block.

    Parameters
    ----------
        title_block (TitleBlock): Title block to configure
        company (str): company name
        date (str): current date
        revision (str): revision
        title (str | bool): project title, set to any boolean value to prevent from setting the title into title block
        verbose (bool): enable logging for set_* functions
        reload (bool): set only company, and project title
    Returns:
        title_block (TitleBlock): updated title block
    """
    if date == "":
        date = datetime.date.today().strftime("%d.%m.%Y")

    if title_block is None:  # title block is none type, when
        # no parameters are sets into title block
        title_block = TitleBlock()

    if company is not None:
        title_block.company = company

    if isinstance(title, str):
        title_block.title = title

    if reload is False:
        title_block.date = date
        title_block.revision = revision

    return title_block


def set_paper_size(page: PageSettings, size: str = "A3", verbose: bool = False) -> PageSettings:
    """Set paper size to selected size.

    Parameters
    ----------
        page (PageSettings): pcb or schematic page object
        size (str): new page size
        verbose (bool): enable logging at info level for this function

    Returns
    -------
        page (PageSettings): page settings with updated paper size

    """
    if size not in ["A0", "A1", "A2", "A3", "A4", "A5", "A", "B", "C", "D", "E"]:
        log.error("Selected page is not range")
        sys.exit(-1)
    else:
        if verbose:
            log.info(f'Set page size to "{size}"')

        page.paperSize = size
        return page


def read_pcb(board_file: str) -> Board:
    """Read PCB file.

    Parameters
    ----------
       board_file (str): path to board file (*.kicad_pcb)

    Returns
    -------
        board (Board): content of board file

    """
    board = Board()

    try:
        board = Board().from_file(board_file)

    except Exception as err_descriptor:
        log.error(f"Can't read board file, due to {err_descriptor}")
        sys.exit(-1)

    return board


def read_sch(sch_file: str) -> Schematic:
    """Read schematic file.

    Parameters
    ----------
       sch_file (str): path to schematic file

    Returns
    -------
        schematic (Schematic): content of schematic file
    """
    try:
        sch = Schematic().from_file(sch_file)
    except Exception as err_descriptor:
        log.error(f"Can't read sch file, due to {err_descriptor}")
        sys.exit(-1)

    return sch


def compare_project_revisions(title_block: TitleBlock, project_revision: str) -> bool:
    """Compare project_revision to project revision set in KiCad project files.

    Parameters
    ----------
        title_blocks: TitleBlock: title block to compare
        project_revision (str): project revision to set

    Returns
    -------
       (bool): True if revision are the same or
               if revision is not set in any of KiCad files,
               otherwise false
    """
    if title_block is None:
        return True

    revision = title_block.revision
    if revision is not None and project_revision != revision:
        log.warning(f"Project revision mismatch, {project_revision} is not the same as {revision}")
        log.info("Use `--reload` to set only project name and company")
        return False

    return True


def compare_project_title(title_block: TitleBlock, project_title: str) -> bool:
    """Compare project_title to project titles set in KiCad project files.

    Parameters
    ----------
        title_block: (TitleBlock): title block to compare
        project_title (str): project title to set

    Returns
    -------
       (bool): True if titles are the same or
               if project title is not set in any of KiCad files,
               otherwise false
    """
    if title_block is None:
        return True

    title = title_block.title
    if title is not None and project_title != title:
        log.warning(f"Project title mismatch, {project_title} is not the same as {title}")
        log.info("Use `--force-title` to overwrite")
        return False

    return True


def get_title_block(target: Union[Board, Schematic]) -> TitleBlock:
    """Read title block from Board or Schematic.

    Parameters
    ----------
        board (str): content of kicad_pcb or kicad_sch file

    Returns
    -------
        title_block (TitleBlock): title block for sch or pcb
    """
    title_block = target.titleBlock

    if title_block is None:
        return TitleBlock()

    return title_block


def create_empty_pro(project: KicadProject, project_title: str) -> bool:
    """
    Create  empty `.kicad_pro` file

    :param project: Kicad project object to work into
    :returns: True if file created successfully or file exist, False if not
    """
    if not project.pro_file:
        log.info("Creating project file")
        with open(file=project_title + ".kicad_pro", mode="w") as file:
            file.write("{}")
    return True


def create_empty_sch(project: KicadProject, project_title: str) -> bool:
    """
    Create  empty `.kicad_sch` file

    :param project: Kicad project object to work into
    :returns: True if file created successfully or file exist, False if not
    """
    if not project.all_sch_files:
        log.info("Creating SCH file")
        sch = Schematic.create_new()
        try:
            sch.to_file(filepath=project_title + ".kicad_sch")
            return True
        except Exception as error_descriptor:
            log.error(f"Can't create sch file due to {error_descriptor}")
            return False
    else:
        return True


def create_empty_pcb(project: KicadProject, project_title: str) -> bool:
    """
    Create  empty `.kicad_pcb` file

    :param project: Kicad project object to work into
    :returns: True if file created successfully or file exist, False if not
    """
    if not project.pcb_file:
        log.info("Creating PCB file")
        board = Board().create_new()
        try:
            board.to_file(filepath=project_title + ".kicad_pcb")
            return True
        except Exception as error_descriptor:
            log.error(f"Can't create board file due to {error_descriptor}")
            return False
    else:
        return True


def init_pcb(
    project: KicadProject,
    company: str,
    reload: bool,
    title: str = "",
    force_title: bool = False,
    revision: str = "1.0.0",
    paper_size: str = "A3",
) -> None:
    """
    Initialize pcb file

    :param project: Kicad project object to work into
    """
    project.get_pcb_file_name_from_dir(_dir=os.getcwd())

    pcb = project.pcb_file
    pcb_data = read_pcb(board_file=pcb)
    pcb_title_block = get_title_block(target=pcb_data)
    pcb_page_settings = pcb_data.paper

    if not reload and not compare_project_revisions(title_block=pcb_title_block, project_revision=revision):
        exit(-1)
    if not force_title and not compare_project_title(title_block=pcb_title_block, project_title=title):
        exit(-1)

    pcb_title_block = set_title_block(
        title_block=pcb_title_block, company=company, revision=revision, title=title, reload=reload
    )
    pcb_data.titleBlock = pcb_title_block

    pcb_page_settings = set_paper_size(page=pcb_page_settings, size=paper_size)
    pcb_data.paper = pcb_page_settings

    try:
        pcb_data.to_file()
    except Exception as err_descriptor:
        log.error(f"Can't save sch file due to {err_descriptor}")


def init_sch(
    project: KicadProject,
    company: str,
    reload: bool,
    title: str = "",
    force_title: bool = False,
    revision: str = "1.0.0",
    paper_size: str = "A3",
) -> None:
    """
    Initialize sch file

    :param project: Kicad project object to work into
    """
    project.get_sch_file_names_from_dir(_dir=os.getcwd())

    for sch in project.all_sch_files:
        sch_data = read_sch(sch_file=sch)
        sch_title_block = get_title_block(target=sch_data)
        sch_page_settings = sch_data.paper

        if not reload and not compare_project_revisions(title_block=sch_title_block, project_revision=revision):
            exit(-1)
        if not force_title and not compare_project_title(title_block=sch_title_block, project_title=title):
            exit(-1)

        sch_title_block = set_title_block(
            title_block=sch_title_block, company=company, revision=revision, title=title, reload=reload
        )
        sch_data.titleBlock = sch_title_block

        sch_page_settings = set_paper_size(page=sch_page_settings, size=paper_size)
        sch_data.paper = sch_page_settings

        try:
            sch_data.to_file()
        except Exception as err_descriptor:
            log.error(f"Can't save sch file due to {err_descriptor}")


def get_title_str(title_list: list) -> str:
    """
    Get project title argument as string type

    :return str: project_title
    """

    title_list = [arg + " " for arg in title_list]

    title = "".join(title_list)
    title = title[:-1]  # Remove space char at the end of title
    log.debug(f"Project title: {title}")
    return title


def main(project: KicadProject, args: argparse.Namespace) -> None:
    """Main module function."""
    project_title = get_title_str(args.title)
    create_empty_pro(project, project_title)
    create_empty_sch(project, project_title)
    create_empty_pcb(project, project_title)
    init_sch(
        project,
        company=args.company,
        reload=args.reload,
        title=project_title,
        force_title=args.force_title,
        paper_size=args.size,
    )
    init_pcb(
        project,
        company=args.company,
        reload=args.reload,
        title=project_title,
        force_title=args.force_title,
        paper_size=args.size,
    )
    prettify(project, argparse.Namespace())


def run(project: KicadProject, args: argparse.Namespace) -> None:
    """Entry function for module."""
    main(project, args)
