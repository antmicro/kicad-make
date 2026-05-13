import os
import unittest

from askiff import Board
from askiff.footprint import FootprintType
from kmake_test_common import KmakeTestCase


class PnpTest(KmakeTestCase, unittest.TestCase):
    def __init__(self, method_name: str = "runTest") -> None:
        KmakeTestCase.__init__(self, "pnp")
        unittest.TestCase.__init__(self, method_name)

    def test_pnp(self) -> None:
        self.run_test_command([])

        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/{self.kpro.project_name}-top.pos"))
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/{self.kpro.project_name}-bottom.pos"))
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/{self.kpro.project_name}-top-pos.csv"))
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/{self.kpro.project_name}-bottom-pos.csv"))

    def test_pnp_skips_dnp_footprints_by_default(self) -> None:
        self.run_test_command([])

        with open(f"{self.kpro.fab_dir}/{self.kpro.project_name}-bottom.pos") as file:
            self.assertNotIn("D3", file.read())

    def test_pnp_tht(self) -> None:
        self.run_test_command(["-t"])

        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/{self.kpro.project_name}-top.pos"))
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/{self.kpro.project_name}-bottom.pos"))
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/{self.kpro.project_name}-top-pos.csv"))
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/{self.kpro.project_name}-bottom-pos.csv"))
        with open(f"{self.kpro.fab_dir}/{self.kpro.project_name}-top.pos") as file:
            csv_content = file.read()

        board = Board.from_file(self.kpro.pcb_file)
        for fp in board.footprints:
            # when --tht flag is used, all footprints should be included, not just SMD
            if fp.attributes.fp_type == FootprintType.THT:
                self.assertIn(fp.lib_id.name, csv_content)

    def test_pnp_other(self) -> None:
        self.run_test_command(["--other"])

        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/{self.kpro.project_name}-top.pos"))
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/{self.kpro.project_name}-bottom.pos"))
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/{self.kpro.project_name}-top-pos.csv"))
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/{self.kpro.project_name}-bottom-pos.csv"))
        with open(f"{self.kpro.fab_dir}/{self.kpro.project_name}-top.pos") as file:
            csv_content = file.read()

        board = Board.from_file(self.kpro.pcb_file)
        for fp in board.footprints:
            if fp.attributes.fp_type == FootprintType.UNSPECIFIED and not fp.attributes.exclude_from_pos_files:
                self.assertIn(fp.lib_id.name, csv_content)

    def test_pnp_excluded(self) -> None:
        self.run_test_command(["--excluded"])

        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/{self.kpro.project_name}-top.pos"))
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/{self.kpro.project_name}-bottom.pos"))
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/{self.kpro.project_name}-top-pos.csv"))
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/{self.kpro.project_name}-bottom-pos.csv"))
        with open(f"{self.kpro.fab_dir}/{self.kpro.project_name}-top.pos") as file:
            csv_content = file.read()

        board = Board.from_file(self.kpro.pcb_file)
        for fp in board.footprints:
            if fp.attributes.exclude_from_pos_files and fp.attributes.fp_type == FootprintType.SMD:
                self.assertIn(fp.lib_id.name, csv_content)

        with open(f"{self.kpro.fab_dir}/{self.kpro.project_name}-bottom.pos") as file:
            self.assertNotIn("D3", file.read())

    def test_pnp_dnp(self) -> None:
        self.run_test_command(["--dnp"])

        with open(f"{self.kpro.fab_dir}/{self.kpro.project_name}-bottom.pos") as file:
            self.assertIn("D3", file.read())


if __name__ == "__main__":
    unittest.main()
