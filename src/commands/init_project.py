import argparse
import datetime
import logging
import sys

from askiff import Board, Project, Schematic
from askiff.common import Paper, PaperSize, TitleBlock
from askiff.const import Version

log = logging.getLogger(__name__)


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Register parser and its arguments as subparser."""
    init_project_parser = subparsers.add_parser("init-project", help="Initialize KiCad project.")
    init_project_parser.add_argument("-c", "--company", dest="company", help="Company name.")
    init_project_parser.add_argument("-t", "--title", nargs="*", dest="title", help="Project title.", required=True)
    init_project_parser.add_argument(
        "--force-title", dest="force_title", action="store_true", help="Override existing title."
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
    company: str | None = None,
    date: str | None = None,
    revision: str | None = None,
    title: str | None = None,
    reload: bool = False,
) -> None:
    """Set: revision, date, company and project title into title block.

    Parameters
    ----------
        title_block (TitleBlock): Title block to configure
        company (str): company name
        date (str): current date
        revision (str): revision
        title (str): project title
        reload (bool): set only company, and project title
    """

    if company:
        title_block.company = company

    if title:
        title_block.title = title

    if reload is False:
        title_block.date = date or datetime.date.today().strftime("%d.%m.%Y")
        if revision:
            title_block.rev = revision


def set_paper_size(page: Paper, size: str = "A3", verbose: bool = False) -> None:
    """Set paper size to selected size.

    Parameters
    ----------
        page (PageSettings): pcb or schematic page object
        size (str): new page size
        verbose (bool): enable logging at info level for this function
    """
    if size not in ["A0", "A1", "A2", "A3", "A4", "A5", "A", "B", "C", "D", "E"]:
        log.error("Selected page is not range")
        sys.exit(-1)
    else:
        if verbose:
            log.info(f'Set page size to "{size}"')
        page.size = PaperSize(size)


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
    revision = title_block.rev
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

    title = title_block.title
    if title is not None and project_title != title:
        log.warning(f"Project title mismatch, {project_title} is not the same as {title}")
        log.info("Use `--force-title` to overwrite")
        return False

    return True


def create_empty_pro(pro: Project, project_title: str) -> None:
    """
    Create  empty `.kicad_pro` file

    :param pro: Kicad project object to work into
    """
    if not pro.kicad_pro_path:
        log.info("Creating project file")
        pro.kicad_pro_path = pro.fs_path / (project_title + ".kicad_pro")
        pro.kicad_pro_path.write_text("{}")


def create_empty_sch(pro: Project) -> None:
    """
    Create  empty `.kicad_sch` file

    :param pro: Kicad project object to work into
    """
    if not pro.sch_root:
        log.info("Creating SCH file")
        sch = Schematic(version=Version.K9.sch)
        sch.fs_path = pro.kicad_pro_path.with_suffix(Schematic.fs_ext)
        pro.sch_root = sch
        pro.sch = [sch]
        sch.to_file()


def create_empty_pcb(pro: Project) -> None:
    """
    Create  empty `.kicad_pcb` file

    :param pro: Kicad project object to work into
    """
    if not pro.pcb_root:
        log.info("Creating PCB file")
        board = Board(version=Version.K9.pcb)
        board.fs_path = pro.kicad_pro_path.with_suffix(Board.fs_ext)
        pro.pcb_root = board
        pro.pcb = [board]
        board.to_file()


def init_design_file(
    file: Schematic | Board,
    company: str,
    reload: bool,
    title: str = "",
    force_title: bool = False,
    revision: str = "1.0.0",
    paper_size: str = "A3",
) -> None:
    """
    Initialize design file (pcb or sch), setting its title block and paper
    """

    if not reload and not compare_project_revisions(file.title_block, project_revision=revision):
        sys.exit(-1)
    if not force_title and not compare_project_title(file.title_block, project_title=title):
        sys.exit(-1)

    set_title_block(file.title_block, company=company, revision=revision, title=title, reload=reload)

    set_paper_size(page=file.paper, size=paper_size)
    file.to_file()


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


def init_project(pro: Project, args: argparse.Namespace) -> None:
    """Main module function."""
    project_title = get_title_str(args.title)
    create_empty_pro(pro, project_title)
    create_empty_sch(pro)
    create_empty_pcb(pro)
    for design_file in (*pro.sch, *pro.pcb):
        init_design_file(
            design_file,
            company=args.company,
            reload=args.reload,
            title=project_title,
            force_title=args.force_title,
            paper_size=args.size,
        )


def run(pro: Project, args: argparse.Namespace) -> None:
    """Entry function for module."""
    init_project(pro, args)
