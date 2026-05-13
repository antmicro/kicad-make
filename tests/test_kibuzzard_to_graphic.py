import unittest

from askiff import Board
from kmake_test_common import KmakeTestCase


class KibuzzardToGraphicTest(KmakeTestCase, unittest.TestCase):
    def __init__(self, method_name: str = "runTest") -> None:
        KmakeTestCase.__init__(self, "kibuzzard-to-graphic")
        unittest.TestCase.__init__(self, method_name)

    def test_kibuzzard(self) -> None:
        target_pcb = Board.from_file(self.kpro.pcb_file)
        target_footprints_entry_names = [footprint.lib_id.name for footprint in target_pcb.footprints]

        self.assertIn("kibuzzard-67891646", target_footprints_entry_names)

        # TODO: Check if kibuzzard not exists as graphic in target

        self.run_test_command([])

        target_pcb = Board.from_file(self.kpro.pcb_file)
        target_footprints_entry_names = sorted([footprint.lib_id.name for footprint in target_pcb.footprints])
        target_graphic_items = sorted(target_pcb.graphic_items, key=lambda x: x.uuid)
        reference_pcb = Board.from_file(self.ref_dir / self.kpro.pcb_file)
        reference_footprints_entry_names = sorted([footprint.lib_id.name for footprint in reference_pcb.footprints])
        reference_graphic_items = sorted(reference_pcb.graphic_items, key=lambda x: x.uuid)

        self.assertListEqual(reference_footprints_entry_names, target_footprints_entry_names)
        self.assertListEqual(reference_graphic_items, target_graphic_items)
        self.assertNotIn("kibuzzard-67891646", target_footprints_entry_names)
