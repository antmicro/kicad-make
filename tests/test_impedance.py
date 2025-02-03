import unittest
import os
from kiutils.board import Board
from pathlib import Path
from kmake_test_common import KmakeTestCase


class ImpedanceTest(KmakeTestCase, unittest.TestCase):

    def __init__(self, method_name: str = "runTest") -> None:
        KmakeTestCase.__init__(self, "impedance")
        unittest.TestCase.__init__(self, method_name)

    def test_impedence_map(self) -> None:
        self.run_test_command([])
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/impedance_maps"))
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/impedance_map.kicad_pcb"))

        board = Board.from_file(f"{self.kpro.fab_dir}/impedance_map.kicad_pcb")

        self.assertEqual(len(board.traceItems), 328)
        self.assertEqual(len(board.footprints), 0)
        self.assertEqual(len(board.zones), 0)

        for file in Path.iterdir(Path(f"{self.kpro.fab_dir}/impedance_maps")):
            self.assertTrue(file.is_file())
            self.assertTrue(file.suffix == ".gbr")
            self.assertIn("Ohm", file.name)


if __name__ == "__main__":
    unittest.main()
