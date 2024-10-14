import unittest
from kiutils.board import Board
from kmake_test_common import KmakeTestCase


class KibuzzardToGraphicTest(KmakeTestCase, unittest.TestCase):

    def __init__(self, method_name: str = "runTest") -> None:
        KmakeTestCase.__init__(
            self, KmakeTestCase.TEST_DIR / "test-designs" / "project-with-kicad-lib", "kibuzzard-to-graphic"
        )
        unittest.TestCase.__init__(self, method_name)

    def test_kibuzzard(self) -> None:
        target_pcb_path = self.target_dir / "project-with-kicad-lib.kicad_pcb"
        reference_pcb_path = (
            self.TEST_DIR
            / "reference-outputs"
            / "project-with-kicad-lib"
            / "kibuzzard-to-graphic"
            / "project-with-kicad-lib.kicad_pcb"
        )

        target_pcb = Board().from_file(filepath=str(target_pcb_path))
        target_footprints_entry_names = [footprint.entryName for footprint in target_pcb.footprints]
        target_graphic_items = [graphic_item for graphic_item in target_pcb.graphicItems]

        self.assertIn("kibuzzard-66D96414", target_footprints_entry_names)

        # TODO: Check if kibuzzard not exists as graphic in target

        self.run_test_command([])

        target_pcb = Board().from_file(filepath=str(target_pcb_path))
        target_footprints_entry_names = sorted([footprint.entryName for footprint in target_pcb.footprints])
        target_graphic_items = [graphic_item for graphic_item in target_pcb.graphicItems]
        reference_pcb = Board().from_file(filepath=str(reference_pcb_path))
        reference_footprints_entry_names = sorted([footprint.entryName for footprint in reference_pcb.footprints])
        reference_graphic_items = [graphic_item for graphic_item in reference_pcb.graphicItems]

        self.assertListEqual(reference_footprints_entry_names, target_footprints_entry_names)
        self.assertListEqual(reference_graphic_items, target_graphic_items)
        self.assertNotIn("kibuzzard-66D96414", target_footprints_entry_names)
