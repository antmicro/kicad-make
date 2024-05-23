import unittest
import kmake
import os
from pathlib import Path
from git import Repo

from common.kicad_project import KicadProject

COMMAND = "logos"
TEST_NAME = COMMAND

TEST_DIR = Path(__file__).parent.resolve()
JETSON_ORIN_BASEBOARD_DIR = TEST_DIR / "test-designs" / "jetson-orin-baseboard"
RESULT_DIR = TEST_DIR / "results" / TEST_NAME


TEST_LOGO = """(image (at 107.95 270.51)
  (uuid 5368bee9-0dc1-4324-9e19-30a3e0e2c1d2)
  (data
    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
    hZx/AORG4hxFmPYtAAAAAElFTkSuQmCC
  )
)
"""

class LogosTest(unittest.TestCase):
    def setUp(self) -> None:
        kicad_project_repo = Repo(JETSON_ORIN_BASEBOARD_DIR)
        kicad_project_repo.git.reset("--hard", "HEAD")
        kicad_project_repo.git.clean("-fd")
        os.chdir(JETSON_ORIN_BASEBOARD_DIR)
        self.test_logo_path = TEST_DIR / "test_logo"
        with open(self.test_logo_path, "w") as f:
            f.write(TEST_LOGO)
        self.args = kmake.parse_arguments([COMMAND, "test_logo", "-p", str(TEST_DIR)])
        self.kpro = KicadProject()

    def test(self) -> None:
        self.args.func(self.kpro, self.args)

    def tearDown(self) -> None:
        kicad_project_repo = Repo(f"{self.kpro.dir}")
        changed_files = [ item.a_path for item in kicad_project_repo.index.diff(None) ]
        # Skip first line, it contains coordinates that will change
        logo = "\n".join([line.strip() for line in TEST_LOGO.splitlines()[1:]])
        for file in changed_files:
            with open(file, "r") as f:
                file_contents = "\n".join([line.strip() for line in f.readlines()])
                self.assertTrue(logo in file_contents)

        self.assertTrue(len(kicad_project_repo.untracked_files) == 0)


if __name__ == '__main__':
    unittest.main()
