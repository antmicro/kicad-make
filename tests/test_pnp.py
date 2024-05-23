import unittest
import kmake
import os
from pathlib import Path
from git import Repo

from common.kicad_project import KicadProject
from kiutils.board import Board

TEST_COMMAND = "pnp"
TEST_DIR = Path(__file__).parent.resolve()
# path to test design repository
JETSON_ORIN_BASEBOARD_DIR = TEST_DIR / "test-designs" / "jetson-orin-baseboard"

class PnpTest(unittest.TestCase):
    def test_pnp(self) -> None:
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

        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/{self.kpro.name}-top.pos"))
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/{self.kpro.name}-bottom.pos"))
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/{self.kpro.name}-top-pos.csv"))
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/{self.kpro.name}-bottom-pos.csv"))

    def test_pnp_tht(self) -> None:
        # make sure test design repository doesn't have any changes
        kicad_project_repo = Repo(JETSON_ORIN_BASEBOARD_DIR)
        kicad_project_repo.git.reset("--hard", "HEAD")
        kicad_project_repo.git.clean("-fd")
        # change current directory to the test design repository
        # as kmake expects to be run from the root of the test repository
        os.chdir(JETSON_ORIN_BASEBOARD_DIR)
        # parse arguments for the test command
        self.args = kmake.parse_arguments([TEST_COMMAND, '-t'])
        self.kpro = KicadProject()
        self.args.func(self.kpro, self.args)

        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/{self.kpro.name}-top.pos"))
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/{self.kpro.name}-bottom.pos"))
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/{self.kpro.name}-top-pos.csv"))
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/{self.kpro.name}-bottom-pos.csv"))

        board = Board.from_file(self.kpro.pcb_file)
        for footprint in board.footprints:
            # when --tht flag is used, all footprints should be included, not just SMD
            if footprint.attributes.type is not None and "smd" not in footprint.attributes.type:
                    with open(f"{self.kpro.fab_dir}/{self.kpro.name}-top.pos") as file:
                        self.assertIn(footprint.entryName, file.read())

    def test_pnp_other(self) -> None:
        # make sure test design repository doesn't have any changes
        kicad_project_repo = Repo(JETSON_ORIN_BASEBOARD_DIR)
        kicad_project_repo.git.reset("--hard", "HEAD")
        kicad_project_repo.git.clean("-fd")
        # change current directory to the test design repository
        # as kmake expects to be run from the root of the test repository
        os.chdir(JETSON_ORIN_BASEBOARD_DIR)
        # parse arguments for the test command
        self.args = kmake.parse_arguments([TEST_COMMAND, '--other'])
        self.kpro = KicadProject()
        self.args.func(self.kpro, self.args)

        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/{self.kpro.name}-top.pos"))
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/{self.kpro.name}-bottom.pos"))
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/{self.kpro.name}-top-pos.csv"))
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/{self.kpro.name}-bottom-pos.csv"))

        board = Board.from_file(self.kpro.pcb_file)
        for footprint in board.footprints:
            if footprint.attributes.type is None and footprint.attributes.excludeFromPosFiles is False:
                    with open(f"{self.kpro.fab_dir}/{self.kpro.name}-top.pos") as file:
                        self.assertIn(footprint.entryName, file.read())

    def test_pnp_excluded(self) -> None:
        # make sure test design repository doesn't have any changes
        kicad_project_repo = Repo(JETSON_ORIN_BASEBOARD_DIR)
        kicad_project_repo.git.reset("--hard", "HEAD")
        kicad_project_repo.git.clean("-fd")
        # change current directory to the test design repository
        # as kmake expects to be run from the root of the test repository
        os.chdir(JETSON_ORIN_BASEBOARD_DIR)
        # parse arguments for the test command
        self.args = kmake.parse_arguments([TEST_COMMAND, '--excluded'])
        self.kpro = KicadProject()
        self.args.func(self.kpro, self.args)

        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/{self.kpro.name}-top.pos"))
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/{self.kpro.name}-bottom.pos"))
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/{self.kpro.name}-top-pos.csv"))
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/{self.kpro.name}-bottom-pos.csv"))

        board = Board.from_file(self.kpro.pcb_file)
        for footprint in board.footprints:
            if footprint.attributes.excludeFromPosFiles is True \
                and footprint.attributes.type is not None \
                and "smd" in footprint.attributes.type:
                    with open(f"{self.kpro.fab_dir}/{self.kpro.name}-top.pos") as file:
                        self.assertIn(footprint.entryName, file.read())


if __name__ == '__main__':
    unittest.main()

