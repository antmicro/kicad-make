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
    def test_wireframe(self) -> None:
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

        board = Board.from_file(self.kpro.pcb_file)
        for footprint in board.footprints:
            if footprint.layer == "F.Cu":
                for item in footprint.graphicItems:
                    self.assertNotEqual(item.layer, "User.9")
            else:
                for item in footprint.graphicItems:
                    self.assertNotEqual(item.layer, "User.8")

    def test_wireframe_reset(self) -> None:
        # make sure test design repository doesn't have any changes
        kicad_project_repo = Repo(JETSON_ORIN_BASEBOARD_DIR)
        kicad_project_repo.git.reset("--hard", "HEAD")
        kicad_project_repo.git.clean("-fd")
        # change current directory to the test design repository
        # as kmake expects to be run from the root of the test repository
        os.chdir(JETSON_ORIN_BASEBOARD_DIR)
        # parse arguments for the test command
        self.args = kmake.parse_arguments([TEST_COMMAND, "--reset"])
        self.kpro = KicadProject()
        self.args.func(self.kpro, self.args)

        board = Board.from_file(self.kpro.pcb_file)
        for footprint in board.footprints:
            for item in footprint.graphicItems:
                self.assertNotEqual(item.layer, "User.8")

    def test_wireframe_export(self) -> None:
        # make sure test design repository doesn't have any changes
        kicad_project_repo = Repo(JETSON_ORIN_BASEBOARD_DIR)
        kicad_project_repo.git.reset("--hard", "HEAD")
        kicad_project_repo.git.clean("-fd")
        # change current directory to the test design repository
        # as kmake expects to be run from the root of the test repository
        os.chdir(JETSON_ORIN_BASEBOARD_DIR)
        # parse arguments for the test command
        self.args = kmake.parse_arguments([TEST_COMMAND, "--export"])
        self.kpro = KicadProject()
        self.args.func(self.kpro, self.args)

        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/wireframe/wireframe_top.gbr"))
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/wireframe/wireframe_bottom.gbr"))
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/wireframe/wireframe_top.svg"))
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/wireframe/wireframe_bottom.svg"))

    def test_wireframe_export_reset(self) -> None:
        # make sure test design repository doesn't have any changes
        kicad_project_repo = Repo(JETSON_ORIN_BASEBOARD_DIR)
        kicad_project_repo.git.reset("--hard", "HEAD")
        kicad_project_repo.git.clean("-fd")
        # change current directory to the test design repository
        # as kmake expects to be run from the root of the test repository
        os.chdir(JETSON_ORIN_BASEBOARD_DIR)
        # parse arguments for the test command
        self.args = kmake.parse_arguments([TEST_COMMAND, "--export", "--reset"])
        self.kpro = KicadProject()
        self.args.func(self.kpro, self.args)

        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/wireframe/wireframe_top.gbr"))
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/wireframe/wireframe_bottom.gbr"))
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/wireframe/wireframe_top.svg"))
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/wireframe/wireframe_bottom.svg"))

if __name__ == '__main__':
    unittest.main()

