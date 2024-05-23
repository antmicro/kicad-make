import unittest
import kmake
import os
from pathlib import Path
from git import Repo

from common.kicad_project import KicadProject

TEST_COMMAND = "sch"
TEST_DIR = Path(__file__).parent.resolve()
# path to test design repository
JETSON_ORIN_BASEBOARD_DIR = TEST_DIR / "test-designs" / "jetson-orin-baseboard"

class SchTest(unittest.TestCase):
    def test_sch(self) -> None:
        # make sure test design repository doesn't have any changes
        kicad_project_repo = Repo(JETSON_ORIN_BASEBOARD_DIR)
        kicad_project_repo.git.reset("--hard", "HEAD")
        kicad_project_repo.git.clean("-fd")
        # change current directory to the test design repository
        # as kmake expects to be run from the root of the test repository
        os.chdir(JETSON_ORIN_BASEBOARD_DIR)
        # parse arguments for the test command
        self.args = kmake.parse_arguments([TEST_COMMAND])
        self.kpro = KicadProject()
        self.args.func(self.kpro, self.args)

        self.assertTrue(os.path.exists(self.kpro.doc_dir))
        self.assertTrue(os.path.exists(f"{self.kpro.doc_dir}/{self.kpro.name}.pdf"))

    def test_sch_theme(self) -> None:
        # make sure test design repository doesn't have any changes
        kicad_project_repo = Repo(JETSON_ORIN_BASEBOARD_DIR)
        kicad_project_repo.git.reset("--hard", "HEAD")
        kicad_project_repo.git.clean("-fd")
        # change current directory to the test design repository
        # as kmake expects to be run from the root of the test repository
        os.chdir(JETSON_ORIN_BASEBOARD_DIR)
        # parse arguments for the test command
        self.args = kmake.parse_arguments([TEST_COMMAND, "-t", "Kicad Classic"])
        self.kpro = KicadProject()
        self.args.func(self.kpro, self.args)

        self.assertTrue(os.path.exists(self.kpro.doc_dir))
        self.assertTrue(os.path.exists(f"{self.kpro.doc_dir}/{self.kpro.name}.pdf"))
        # TODO: check if the theme is applied to the pdf
        # TODO: kicad doesn't fail if the theme is not found, instead it uses the default theme
        # maybe we should add this check in `sch` command

if __name__ == '__main__':
    unittest.main()
