import unittest

from askiff import Board
from kmake_test_common import KmakeTestCase


class ImpedanceTest(KmakeTestCase, unittest.TestCase):
    def __init__(self, method_name: str = "runTest") -> None:
        KmakeTestCase.__init__(self, "impedance")
        unittest.TestCase.__init__(self, method_name)

    def test_impedence_map(self) -> None:
        self.run_test_command([])
        impedance_maps_path = self.kpro.fab_dir / "impedance_maps"
        impedance_pcb_path = self.kpro.fab_dir / "impedance_map.kicad_pcb"
        self.assertTrue(impedance_maps_path.exists())
        self.assertTrue(impedance_pcb_path.exists())

        board = Board.from_file(impedance_pcb_path)

        self.assertEqual(len(board.traces), 270)
        self.assertEqual(len(board.footprints), 0)
        self.assertEqual(len(board.zones), 0)

        for file in impedance_maps_path.iterdir():
            self.assertTrue(file.is_file())
            self.assertTrue(file.suffix == ".gbr")
            self.assertIn("Ohm", file.name)


if __name__ == "__main__":
    unittest.main()
