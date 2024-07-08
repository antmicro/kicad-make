import unittest
import kmake
import os
from pathlib import Path
from git import Repo
from unittest.mock import patch
from io import StringIO

from common.kicad_project import KicadProject
from kiutils.board import Board
from kiutils.schematic import Position

COMMAND = "aux-origin"
TEST_NAME = COMMAND

TEST_DIR = Path(__file__).parent.resolve()
JETSON_ORIN_BASEBOARD_DIR = TEST_DIR / "test-designs" / "jetson-orin-baseboard"
RESULT_DIR = TEST_DIR / "results" / TEST_NAME


class AuxoriginTest(unittest.TestCase):
    @patch("sys.stdout", new_callable=StringIO)
    def test_no_argument(self, stdout: StringIO) -> None:
        kicad_project_repo = Repo(JETSON_ORIN_BASEBOARD_DIR)
        kicad_project_repo.git.reset("--hard", "HEAD")
        kicad_project_repo.git.clean("-fd")
        os.chdir(JETSON_ORIN_BASEBOARD_DIR)
        # we should exit with error
        with self.assertRaises(SystemExit) as cm:
            self.args = kmake.parse_arguments([COMMAND])
            self.assertIn("usage: kmake aux-origin [-h] (-r | -s {tl,tr,bl,br} | -p x_pos y_pos)", stdout.getvalue())

        self.assertEqual(cm.exception.code, 2)

    def test_reset_aux(self) -> None:
        kicad_project_repo = Repo(JETSON_ORIN_BASEBOARD_DIR)
        kicad_project_repo.git.reset("--hard", "HEAD")
        kicad_project_repo.git.clean("-fd")
        os.chdir(JETSON_ORIN_BASEBOARD_DIR)
        self.args = kmake.parse_arguments([COMMAND, "--reset"])
        self.kpro = KicadProject()
        self.args.func(self.kpro, self.args)

        board = Board.from_file(self.kpro.pcb_file)
        self.assertEqual(board.setup.auxAxisOrigin, Position(0, 0))

    def test_position_aux(self) -> None:
        kicad_project_repo = Repo(JETSON_ORIN_BASEBOARD_DIR)
        kicad_project_repo.git.reset("--hard", "HEAD")
        kicad_project_repo.git.clean("-fd")
        os.chdir(JETSON_ORIN_BASEBOARD_DIR)
        self.args = kmake.parse_arguments([COMMAND, "--position", "10", "20"])
        self.kpro = KicadProject()
        self.args.func(self.kpro, self.args)

        board = Board.from_file(self.kpro.pcb_file)
        self.assertEqual(board.setup.auxAxisOrigin, Position(10, 20))

    def test_position_aux2(self) -> None:
        kicad_project_repo = Repo(JETSON_ORIN_BASEBOARD_DIR)
        kicad_project_repo.git.reset("--hard", "HEAD")
        kicad_project_repo.git.clean("-fd")
        os.chdir(JETSON_ORIN_BASEBOARD_DIR)
        self.args = kmake.parse_arguments([COMMAND, "--position", "10", "-20"])
        self.kpro = KicadProject()
        self.args.func(self.kpro, self.args)

        board = Board.from_file(self.kpro.pcb_file)
        self.assertEqual(board.setup.auxAxisOrigin, Position(10, -20))

    def test_position_aux3(self) -> None:
        kicad_project_repo = Repo(JETSON_ORIN_BASEBOARD_DIR)
        kicad_project_repo.git.reset("--hard", "HEAD")
        kicad_project_repo.git.clean("-fd")
        os.chdir(JETSON_ORIN_BASEBOARD_DIR)
        self.args = kmake.parse_arguments([COMMAND, "--position", "10.25", "20.75"])
        self.kpro = KicadProject()
        self.args.func(self.kpro, self.args)

        board = Board.from_file(self.kpro.pcb_file)
        self.assertEqual(board.setup.auxAxisOrigin, Position(10.25, 20.75))

    def test_side_aux(self) -> None:
        kicad_project_repo = Repo(JETSON_ORIN_BASEBOARD_DIR)
        kicad_project_repo.git.reset("--hard", "HEAD")
        kicad_project_repo.git.clean("-fd")
        os.chdir(JETSON_ORIN_BASEBOARD_DIR)
        self.args = kmake.parse_arguments([COMMAND, "--side", "bl"])
        self.kpro = KicadProject()
        self.args.func(self.kpro, self.args)

        board = Board.from_file(self.kpro.pcb_file)
        self.assertEqual(board.setup.auxAxisOrigin, Position(29.75, 128.75))


if __name__ == "__main__":
    unittest.main()
