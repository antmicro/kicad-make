import unittest
import os

from kiutils.board import Board
from kmake_test_common import KmakeTestCase


class PnpTest(KmakeTestCase, unittest.TestCase):

    def __init__(self, method_name: str = "runTest") -> None:
        KmakeTestCase.__init__(self, KmakeTestCase.TEST_DIR / "test-designs" / "jetson-orin-baseboard", "pnp")
        unittest.TestCase.__init__(self, method_name)

    def test_pnp(self) -> None:
        self.run_test_command([])

        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/{self.kpro.name}-top.pos"))
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/{self.kpro.name}-bottom.pos"))
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/{self.kpro.name}-top-pos.csv"))
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/{self.kpro.name}-bottom-pos.csv"))

    def test_pnp_tht(self) -> None:
        self.run_test_command(["-t"])

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
        self.run_test_command(["--other"])

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
        self.run_test_command(["--excluded"])

        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/{self.kpro.name}-top.pos"))
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/{self.kpro.name}-bottom.pos"))
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/{self.kpro.name}-top-pos.csv"))
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/{self.kpro.name}-bottom-pos.csv"))

        board = Board.from_file(self.kpro.pcb_file)
        for footprint in board.footprints:
            if (
                footprint.attributes.excludeFromPosFiles is True
                and footprint.attributes.type is not None
                and "smd" in footprint.attributes.type
            ):
                with open(f"{self.kpro.fab_dir}/{self.kpro.name}-top.pos") as file:
                    self.assertIn(footprint.entryName, file.read())


if __name__ == "__main__":
    unittest.main()
