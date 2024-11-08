import unittest
from typing import List
from kiutils.board import Board
from kiutils.footprint import Footprint
from kiutils.items.brditems import Via
from kmake_test_common import KmakeTestCase
from common.kmake_helper import get_property


class PCBFilterTest(KmakeTestCase, unittest.TestCase):

    def __init__(self, method_name: str = "runTest") -> None:
        KmakeTestCase.__init__(self, KmakeTestCase.TEST_DIR / "test-designs" / "cm4-baseboard", "pcb-filter")
        unittest.TestCase.__init__(self, method_name)

    def command_test(self, args: List[str], name: str) -> None:
        self.run_test_command(args + ["-o", self.kpro.pcb_file])
        self.outpcb = BoardStats(self.kpro.pcb_file)
        self.refpcb = self.inpcb

    def setUp(self) -> None:
        super().setUp()
        self.inpcb = BoardStats(str(self.kpro.pcb_file))

    def tearDown(self) -> None:
        self.assertEqual(self.refpcb.footprintsT, self.outpcb.footprintsT)
        self.assertEqual(self.refpcb.footprintsB, self.outpcb.footprintsB)
        self.assertEqual(self.refpcb.footprintsT_J, self.outpcb.footprintsT_J)
        self.assertEqual(self.refpcb.footprintsB_J, self.outpcb.footprintsB_J)
        self.assertEqual(self.refpcb.references, self.outpcb.references)
        self.assertEqual(self.refpcb.values, self.outpcb.values)
        self.assertEqual(self.refpcb.zones, self.outpcb.zones)
        self.assertEqual(self.refpcb.dimensions, self.outpcb.dimensions)
        self.assertEqual(self.refpcb.stackup, self.outpcb.stackup)
        self.assertEqual(self.refpcb.vias, self.outpcb.vias)
        self.assertEqual(self.refpcb.tracks, self.outpcb.tracks)
        self.assertEqual(self.refpcb.graphicItems, self.outpcb.graphicItems)

        super().tearDown()

    def test_pcb_filter_allow(self) -> None:
        self.command_test(["-a", "J"], "allow")
        self.refpcb.footprintsT = self.refpcb.footprintsT_J
        self.refpcb.footprintsB = self.refpcb.footprintsB_J
        self.refpcb.references = self.refpcb.footprintsT + self.refpcb.footprintsB
        self.refpcb.values = self.refpcb.footprintsT + self.refpcb.footprintsB

    def test_pcb_filter_exclude(self) -> None:
        self.command_test(["-e", "J"], "exlude")
        self.refpcb.footprintsT -= self.refpcb.footprintsT_J
        self.refpcb.footprintsB -= self.refpcb.footprintsB_J
        self.refpcb.footprintsT_J = 0
        self.refpcb.footprintsB_J = 0
        self.refpcb.references = (
            self.refpcb.footprintsT + self.refpcb.footprintsB - 4
        )  # 4 = 2x logo + virtual CM4 module + virtual m.2
        self.refpcb.values = self.refpcb.footprintsT + self.refpcb.footprintsB - 2  # 2 = 2x logo

    def test_pcb_filter_vias(self) -> None:
        self.command_test(["--vias"], "vias")
        self.refpcb.vias = 0

    def test_pcb_filter_zones(self) -> None:
        self.command_test(["-z"], "zones")
        self.refpcb.zones = 0

    def test_pcb_filter_tracks(self) -> None:
        self.command_test(["-t"], "tracks")
        self.refpcb.tracks = 0

    def test_pcb_filter_dimensions(self) -> None:
        self.command_test(["-d"], "dimensions")
        self.refpcb.dimensions = 0

    def test_pcb_filter_stackup(self) -> None:
        self.command_test(["--stackup"], "stackup")
        self.refpcb.stackup = 0

    def test_pcb_filter_side_top(self) -> None:
        self.command_test(["-s", "top"], "side_top")
        self.refpcb.footprintsB = 0
        self.refpcb.footprintsB_J = 0
        self.refpcb.references = self.refpcb.footprintsT - 3  # 3 = 2x logo + virtual CM4 module
        self.refpcb.values = self.refpcb.footprintsT - 2  # 2 = 2x logo

    def test_pcb_filter_partial_side_top(self) -> None:
        self.command_test(["-s", "top", "-ao", "J"], "partial_side_top")
        self.refpcb.footprintsB = self.refpcb.footprintsB_J
        self.refpcb.references = (
            self.refpcb.footprintsT + self.refpcb.footprintsB - 3
        )  # 3 = 2x logo + virtual CM4 module
        self.refpcb.values = self.refpcb.footprintsT + self.refpcb.footprintsB - 2  # 2 = 2x logo

    def test_pcb_filter_side_bottom(self) -> None:
        self.command_test(["-s", "bottom"], "side_bottom")
        self.refpcb.footprintsT = 0
        self.refpcb.footprintsT_J = 0
        self.refpcb.references = self.refpcb.footprintsB - 1  # 1 = virtual m.2
        self.refpcb.values = self.refpcb.footprintsB

    def test_pcb_filter_partial_side_bottom(self) -> None:
        self.command_test(["-s", "bottom", "-ao", "J"], "partial_side_bottom")
        self.refpcb.footprintsT = self.refpcb.footprintsT_J
        self.refpcb.references = self.refpcb.footprintsT + self.refpcb.footprintsB - 1  # 1 = virtual m.2
        self.refpcb.values = self.refpcb.footprintsT + self.refpcb.footprintsB

    def test_pcb_filter_layers(self) -> None:
        self.command_test(["-l", "User.9,Edge.Cuts,User.Drawings"], "layers")
        self.refpcb.graphicItems = 12  # some graphics items should be left: SHA, Testpoints/connectors descriptions,..
        self.refpcb.references = 0
        self.refpcb.values = 0

    def test_pcb_filter_values(self) -> None:
        self.command_test(["-v"], "values")
        self.refpcb.values = 0

    def test_pcb_filter_references(self) -> None:
        self.command_test(["-r"], "references")
        self.refpcb.references = 0


class BoardStats:
    def __init__(self, board: str):
        pcb = Board.from_file(board)
        self.footprintsT = len([fp for fp in pcb.footprints if fp.layer == "F.Cu"])
        self.footprintsB = len([fp for fp in pcb.footprints if fp.layer == "B.Cu"])
        self.footprintsT_J = len(
            [fp for fp in pcb.footprints if fp.layer == "F.Cu" and get_property(fp, "Reference").startswith("J")]
        )
        self.footprintsB_J = len(
            [fp for fp in pcb.footprints if fp.layer == "B.Cu" and get_property(fp, "Reference").startswith("J")]
        )
        self.references = len([fp for fp in pcb.footprints if self.prop_visible(fp, "Reference")])
        self.values = len([fp for fp in pcb.footprints if self.prop_visible(fp, "Value")])
        self.zones = len(pcb.zones)
        self.dimensions = len(pcb.dimensions)
        self.stackup = len([g for g in pcb.groups if g.name == "group-boardStackUp"])
        self.vias = len([item for item in pcb.traceItems if isinstance(item, Via)])
        self.tracks = len([item for item in pcb.traceItems if not isinstance(item, Via)])
        self.graphicItems = len([g for g in pcb.graphicItems if g.layer in ["User.9", "Edge.Cuts", "User.Drawings"]])

    @staticmethod
    def prop_visible(fp: Footprint, field: str) -> bool:
        for prop in fp.properties:
            if prop.key != field:
                continue
            return not prop.hide
        return False


if __name__ == "__main__":
    unittest.main()
