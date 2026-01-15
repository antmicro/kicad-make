import unittest
import os

from kmake_test_common import KmakeTestCase
from kiutils.board import Board


class WireframeTest(KmakeTestCase, unittest.TestCase):

    def __init__(self, method_name: str = "runTest") -> None:
        self.layer_suffixes = ["_User_6", "_User_7", "_User_Drawings"]
        self.side_suffixes = ["top", "bottom"]
        KmakeTestCase.__init__(self, "wireframe")
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

    def wireframe_presets(self, preset: str, arg: list[str], suffix: list[list[str]]) -> None:
        self.run_test_command(["-p", f"{preset}"] + arg)
        suffix_product = [(a, b, c) for a in suffix[0] for b in suffix[1] for c in suffix[2]]
        for s in suffix_product:
            self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/wireframe/wireframe_{preset}_{s[0]}{s[1]}.{s[2]}"))

    def test_wireframe_presets_simple(self) -> None:
        self.wireframe_presets("simple", [], [self.side_suffixes, [""], ["gbr", "svg"]])

    def test_wireframe_presets_descriptions(self) -> None:
        self.wireframe_presets("descriptions", [], [self.side_suffixes, [""], ["gbr", "svg"]])

    def test_wireframe_presets_dimensions(self) -> None:
        self.wireframe_presets("dimensions", [], [self.side_suffixes, self.layer_suffixes, ["gbr", "svg"]])

    def test_wireframe_presets_dimensions_gbr(self) -> None:
        self.wireframe_presets("dimensions", ["--gerber"], [self.side_suffixes, self.layer_suffixes, ["gbr"]])

    def test_wireframe_presets_dimensions_svg(self) -> None:
        self.wireframe_presets("dimensions", ["--svg"], [self.side_suffixes, self.layer_suffixes, ["svg"]])


if __name__ == "__main__":
    unittest.main()
