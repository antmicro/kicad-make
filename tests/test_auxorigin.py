import unittest
from unittest.mock import patch
from io import StringIO
from kmake_test_common import KmakeTestCase

from common.kicad_project import KicadProject
from kiutils.board import Board
from kiutils.schematic import Position


class AuxoriginTest(KmakeTestCase, unittest.TestCase):

    def __init__(self, method_name: str = "runTest") -> None:
        KmakeTestCase.__init__(self, KmakeTestCase.TEST_DIR / "test-designs" / "jetson-orin-baseboard", "aux-origin")
        unittest.TestCase.__init__(self, method_name)

    @patch("sys.stdout", new_callable=StringIO)
    def test_no_argument(self, stdout: StringIO) -> None:
        # we should exit with error
        with self.assertRaises(SystemExit) as cm:
            self.run_test_command([])
            self.assertIn("usage: kmake aux-origin [-h] (-r | -s {tl,tr,bl,br} | -p x_pos y_pos)", stdout.getvalue())

        self.assertEqual(cm.exception.code, 2)

    def test_reset_aux(self) -> None:
        self.run_test_command(["--reset"])
        board = Board.from_file(KicadProject().pcb_file)
        self.assertEqual(board.setup.auxAxisOrigin, Position(0, 0))

    def test_position_aux(self) -> None:
        self.run_test_command(["--position", "10", "20"])
        board = Board.from_file(KicadProject().pcb_file)
        self.assertEqual(board.setup.auxAxisOrigin, Position(10, 20))

    def test_position_aux2(self) -> None:
        self.run_test_command(["--position", "10", "-20"])
        board = Board.from_file(KicadProject().pcb_file)
        self.assertEqual(board.setup.auxAxisOrigin, Position(10, -20))

    def test_position_aux3(self) -> None:
        self.run_test_command(["--position", "10.25", "20.75"])
        board = Board.from_file(KicadProject().pcb_file)
        self.assertEqual(board.setup.auxAxisOrigin, Position(10.25, 20.75))

    def test_side_aux(self) -> None:
        self.run_test_command(["--side", "bl"])
        board = Board.from_file(KicadProject().pcb_file)
        self.assertEqual(board.setup.auxAxisOrigin, Position(29.75, 128.75))


if __name__ == "__main__":
    unittest.main()
