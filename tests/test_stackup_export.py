import unittest
import kmake
import os
from pathlib import Path
from git import Repo

from common.kicad_project import KicadProject

TEST_COMMAND = "stackup-export"
TEST_DIR = Path(__file__).parent.resolve()
# path to test design repository
JETSON_ORIN_BASEBOARD_DIR = TEST_DIR / "test-designs" / "jetson-orin-baseboard"


class StackupExportTest(unittest.TestCase):
    def test_stackup_export(self) -> None:
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

        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/stackup.json"))

    def test_stackup_export_output(self) -> None:
        # make sure test design repository doesn't have any changes
        kicad_project_repo = Repo(JETSON_ORIN_BASEBOARD_DIR)
        kicad_project_repo.git.reset("--hard", "HEAD")
        kicad_project_repo.git.clean("-fd")
        # change current directory to the test design repository
        # as kmake expects to be run from the root of the test repository
        os.chdir(JETSON_ORIN_BASEBOARD_DIR)
        # parse arguments for the test command
        self.args = kmake.parse_arguments([TEST_COMMAND, "-o", "fab/test_output_filename.json"])
        self.kpro = KicadProject()
        self.args.func(self.kpro, self.args)

        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/test_output_filename.json"))

    def test_stackup_legacy(self) -> None:
        # make sure test design repository doesn't have any changes
        kicad_project_repo = Repo(JETSON_ORIN_BASEBOARD_DIR)
        kicad_project_repo.git.reset("--hard", "HEAD")
        kicad_project_repo.git.clean("-fd")
        # change current directory to the test design repository
        # as kmake expects to be run from the root of the test repository
        os.chdir(JETSON_ORIN_BASEBOARD_DIR)
        # parse arguments for the test command
        self.args = kmake.parse_arguments([TEST_COMMAND, "--legacy-csv"])
        self.kpro = KicadProject()
        self.args.func(self.kpro, self.args)

        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/stackup.csv"))

    def test_stackup_legacy_output(self) -> None:
        # make sure test design repository doesn't have any changes
        kicad_project_repo = Repo(JETSON_ORIN_BASEBOARD_DIR)
        kicad_project_repo.git.reset("--hard", "HEAD")
        kicad_project_repo.git.clean("-fd")
        # change current directory to the test design repository
        # as kmake expects to be run from the root of the test repository
        os.chdir(JETSON_ORIN_BASEBOARD_DIR)
        # parse arguments for the test command
        self.args = kmake.parse_arguments([TEST_COMMAND, "--legacy-csv", "-o", "fab/test_output_filename.csv"])
        self.kpro = KicadProject()
        self.args.func(self.kpro, self.args)

        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/test_output_filename.csv"))


if __name__ == "__main__":
    unittest.main()
