import unittest
import os

from kmake_test_common import KmakeTestCase
from kiutils.board import Board


class WireframeTest(KmakeTestCase, unittest.TestCase):

    def __init__(self, method_name: str = "runTest") -> None:
        KmakeTestCase.__init__(self, KmakeTestCase.TEST_DIR / "test-designs" / "jetson-orin-baseboard", "wireframe")
        unittest.TestCase.__init__(self, method_name)

    def test_wireframe_reset(self) -> None:
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

        self.run_test_command(["--reset"])

        board = Board.from_file(self.kpro.pcb_file)
        for footprint in board.footprints:
            for item in footprint.graphicItems:
                self.assertNotEqual(item.layer, "User.8")

    def wireframe_presets(self, preset: str) -> None:
        self.run_test_command(["-p", f"{preset}"])
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/wireframe/{preset}_top.gbr"))
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/wireframe/{preset}_bottom.gbr"))
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/wireframe/{preset}_top.svg"))
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/wireframe/{preset}_bottom.svg"))

    def test_wireframe_presets_simple(self) -> None:
        self.wireframe_presets("simple")

    def test_wireframe_presets_dimensions(self) -> None:
        self.wireframe_presets("dimensions")

    def test_wireframe_presets_descriptions(self) -> None:
        self.wireframe_presets("descriptions")


if __name__ == "__main__":
    unittest.main()
