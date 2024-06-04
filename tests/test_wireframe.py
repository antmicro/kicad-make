import unittest
import kmake
import os
from pathlib import Path
from git import Repo

from common.kicad_project import KicadProject
from kiutils.board import Board

TEST_COMMAND = "wireframe"
TEST_DIR = Path(__file__).parent.resolve()
# path to test design repository
JETSON_ORIN_BASEBOARD_DIR = TEST_DIR / "test-designs" / "jetson-orin-baseboard"


class WireframeTest(unittest.TestCase):

    def test_wireframe_reset(self) -> None:
        # make sure test design repository doesn't have any changes
        kicad_project_repo = Repo(JETSON_ORIN_BASEBOARD_DIR)
        kicad_project_repo.git.reset("--hard", "HEAD")
        kicad_project_repo.git.clean("-fd")
        # change current directory to the test design repository
        # as kmake expects to be run from the root of the test repository
        os.chdir(JETSON_ORIN_BASEBOARD_DIR)
        self.kpro = KicadProject()

        # Create board file that is equivalent of legacy wireframe result
        board = Board.from_file(self.kpro.pcb_file)
        for footprint in board.footprints:
            target_layer = "User.8" if footprint.layer == "F.Cu" else "User.9"
            outline_items = [
                item for item in footprint.graphicItems if item.layer == "User.9" or item.layer == "User.8"
            ]
            for item in outline_items:
                item.layer = target_layer
        board.to_file()

        # parse arguments for the test commands
        self.args = kmake.parse_arguments([TEST_COMMAND, "--reset"])
        self.args.func(self.kpro, self.args)

        board = Board.from_file(self.kpro.pcb_file)
        for footprint in board.footprints:
            for item in footprint.graphicItems:
                self.assertNotEqual(item.layer, "User.8")

    def wireframe_presets(self, preset: str) -> None:
        self.kpro = KicadProject()
        self.args = kmake.parse_arguments([TEST_COMMAND, "-p", f"{preset}"])
        self.args.func(self.kpro, self.args)
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/wireframe/{preset}_top.gbr"))
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/wireframe/{preset}_bottom.gbr"))
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/wireframe/{preset}_top.svg"))
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/wireframe/{preset}_bottom.svg"))

    def test_wireframe_presets(self) -> None:
        # make sure test design repository doesn't have any changes
        kicad_project_repo = Repo(JETSON_ORIN_BASEBOARD_DIR)
        kicad_project_repo.git.reset("--hard", "HEAD")
        kicad_project_repo.git.clean("-fd")
        # change current directory to the test design repository
        # as kmake expects to be run from the root of the test repository
        os.chdir(JETSON_ORIN_BASEBOARD_DIR)
        # parse arguments for the test command
        self.wireframe_presets("simple")
        self.wireframe_presets("dimensions")
        self.wireframe_presets("descriptions")


if __name__ == "__main__":
    unittest.main()
