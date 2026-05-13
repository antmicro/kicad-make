import unittest
from io import StringIO
from unittest.mock import patch

from askiff import Board
from askiff.common import Position
from kmake_test_common import KicadProject, KmakeTestCase


class AuxoriginTest(KmakeTestCase, unittest.TestCase):
    def __init__(self, method_name: str = "runTest") -> None:
        KmakeTestCase.__init__(self, "aux-origin")
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
        self.assertEqual(board.setup.aux_axis_origin, Position(0, 0))

    def test_position_aux(self) -> None:
        self.run_test_command(["--position", "10", "20"])
        board = Board.from_file(KicadProject().pcb_file)
        self.assertEqual(board.setup.aux_axis_origin, Position(10, 20))

    def test_position_aux2(self) -> None:
        self.run_test_command(["--position", "10", "-20"])
        board = Board.from_file(KicadProject().pcb_file)
        self.assertEqual(board.setup.aux_axis_origin, Position(10, -20))

    def test_position_aux3(self) -> None:
        self.run_test_command(["--position", "10.25", "20.75"])
        board = Board.from_file(KicadProject().pcb_file)
        self.assertEqual(board.setup.aux_axis_origin, Position(10.25, 20.75))

    def test_side_aux(self) -> None:
        self.run_test_command(["--side", "bl"])
        board = Board.from_file(KicadProject().pcb_file)
        self.assertEqual(board.setup.aux_axis_origin, Position(119.925, 168.525))


if __name__ == "__main__":
    unittest.main()
