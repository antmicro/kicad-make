import unittest
import kmake
import os
from pathlib import Path
from git import Repo

from common.kicad_project import KicadProject

COMMAND = "get-ignore"
TEST_NAME = COMMAND

TEST_DIR = Path(__file__).parent.resolve()
JETSON_ORIN_BASEBOARD_DIR = TEST_DIR / "test-designs" / "jetson-orin-baseboard"
RESULT_DIR = TEST_DIR / "results" / TEST_NAME


class GitIgnoreTest(unittest.TestCase):
    def setUp(self) -> None:
        kicad_project_repo = Repo(JETSON_ORIN_BASEBOARD_DIR)
        kicad_project_repo.git.reset("--hard", "HEAD")
        kicad_project_repo.git.clean("-fd")
        (JETSON_ORIN_BASEBOARD_DIR / ".gitignore").unlink(missing_ok=True)
        os.chdir(JETSON_ORIN_BASEBOARD_DIR)
        self.args = kmake.parse_arguments([COMMAND])
        self.kpro = KicadProject()

    def test(self) -> None:
        self.args.func(self.kpro, self.args)

    def tearDown(self) -> None:
        self.assertTrue((JETSON_ORIN_BASEBOARD_DIR / ".gitignore").exists())

        kicad_project_repo = Repo(f"{self.kpro.dir}")
        changed_files = [item.a_path for item in kicad_project_repo.index.diff(None)]
        RESULT_DIR.mkdir(exist_ok=True, parents=True)
        for file in changed_files:
            Path(file).rename(Path(RESULT_DIR) / Path(file).name)
        for file in kicad_project_repo.untracked_files:
            Path(file).rename(Path(RESULT_DIR) / Path(file).name)


if __name__ == "__main__":
    unittest.main()
