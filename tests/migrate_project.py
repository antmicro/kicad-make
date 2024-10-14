"""Script automatically converts kicad project to match version of installed kicad
    to make sure kmake works properly after this conversion"""

import sys
from pathlib import Path
import git
from pcbnew import *  # type:ignore  # noqa: F403
import logging

log = logging.getLogger(__name__)


def main() -> None:
    if len(sys.argv) != 2:
        log.error(f"{Path(__file__).name} expects 1 argument, got: {len(sys.argv)-1}")
        exit(1)
    # Get path to test designs
    test_designs_path = Path(sys.argv[1]).resolve()
    # For each project in designs dir

    for project in test_designs_path.glob("*"):
        for file in project.glob("*.kicad_pcb"):
            # Migrate pcb
            pcb = LoadBoard(file)  # type: ignore  # noqa: F405
            SaveBoard(file, pcb)  # type: ignore  # noqa: F405
            log.info(f"Migrated {file} to the tested KiCad version")
            try:
                repo = git.Repo(project, search_parent_directories=False)
                repo.index.add(str(file))
                repo.index.add(file.stem + ".kicad_pro")
                repo.index.commit("Migrate project to tested KiCad version")
            except git.exc.InvalidGitRepositoryError:
                log.info(f"Found {project} without git repository (initializing new repo)")
                repo = git.Repo.init(project)
                repo.git.add(all=True)
                repo.index.commit("initial")


if __name__ == "__main__":
    main()
