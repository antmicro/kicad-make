import argparse
import logging
from pathlib import Path

from common.kicad_project import KicadProject

log = logging.getLogger(__name__)

# based on: https://raw.githubusercontent.com/github/gitignore/master/KiCad.gitignore
GITIGNORE = """
# For PCBs designed using KiCad: https://www.kicad.org/
# Format documentation: https://kicad.org/help/file-formats/

# Temporary files
*.000
*.bak
*.bck
*.kicad_pcb-bak
*.kicad_sch-bak
*-backups
*.kicad_prl
*.sch-bak
*~
_autosave-*
*.tmp
*-save.pro
*-save.kicad_pcb
fp-info-cache
~*.lck
\#auto_saved_files#

# Netlist files (exported from Eeschema)
*.net

# Autorouter files (exported from Pcbnew)
*.dsn
*.ses

# Exported BOM files
*.xml
*.csv

# Except stackup.csv
!stackup.csv
"""


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("get-ignore", help="Copy .gitignore file from template.")
    parser.set_defaults(func=run)


def run(kicad_project: KicadProject, args: argparse.Namespace) -> None:
    """Create gitignore from template"""
    gitignore_path = Path(kicad_project.dir) / ".gitignore"
    if gitignore_path.exists():
        log.warning(f".gitignore already exists in {kicad_project.dir}. Delete it to initialize new one.")
        return

    with open(gitignore_path, "w") as file:
        file.write(GITIGNORE)
