import unittest
from pathlib import Path

from askiff.board import Board, Via
from askiff.common_pcb import BoardSide, Layer, LayerSet, LayerSilkS
from askiff.footprint import FpProperty
from kmake_test_common import KmakeTestCase


class PCBFilterTest(KmakeTestCase, unittest.TestCase):
    def __init__(self, method_name: str = "runTest") -> None:
        KmakeTestCase.__init__(self, "pcb-filter")
        unittest.TestCase.__init__(self, method_name)

    def command_test(self, args: list[str]) -> None:
        self.run_test_command(args + ["-o", str(self.kpro.pcb_file)])
        self.outpcb = BoardStats(self.kpro.pcb_file)
        self.refpcb = self.inpcb

    def setUp(self) -> None:
        KmakeTestCase.setUp(self)
        self.check_ref_val = False
        self.inpcb = BoardStats(self.kpro.pcb_file)

    def tearDown(self) -> None:
        self.assertEqual(self.refpcb.footprintsT, self.outpcb.footprintsT)
        self.assertEqual(self.refpcb.footprintsB, self.outpcb.footprintsB)
        self.assertEqual(self.refpcb.footprintsT_J, self.outpcb.footprintsT_J)
        self.assertEqual(self.refpcb.footprintsB_J, self.outpcb.footprintsB_J)
        if self.check_ref_val:
            self.assertEqual(self.refpcb.references_visible, self.outpcb.references_visible)
            self.assertEqual(self.refpcb.values, self.outpcb.values)
        self.assertEqual(self.refpcb.zones, self.outpcb.zones)
        self.assertEqual(self.refpcb.dimensions, self.outpcb.dimensions)
        self.assertEqual(self.refpcb.stackup, self.outpcb.stackup)
        self.assertEqual(self.refpcb.vias, self.outpcb.vias)
        self.assertEqual(self.refpcb.tracks, self.outpcb.tracks)
        self.assertEqual(self.refpcb.graphic_items, self.outpcb.graphic_items)

        KmakeTestCase.tearDown(self)

    def test_pcb_filter_allow(self) -> None:
        self.command_test(["-x", "+J"])
        self.refpcb.footprintsT = self.refpcb.footprintsT_J
        self.refpcb.footprintsB = self.refpcb.footprintsB_J

    def test_pcb_filter_exclude(self) -> None:
        self.command_test(["-x='-J'"])
        self.refpcb.footprintsT -= self.refpcb.footprintsT_J
        self.refpcb.footprintsB -= self.refpcb.footprintsB_J
        self.refpcb.footprintsT_J = 0
        self.refpcb.footprintsB_J = 0

    def test_pcb_filter_vias(self) -> None:
        self.command_test(["--vias"])
        self.refpcb.vias = 0

    def test_pcb_filter_zones(self) -> None:
        self.command_test(["-z"])
        self.refpcb.zones = 0

    def test_pcb_filter_tracks(self) -> None:
        self.command_test(["-t"])
        self.refpcb.tracks = 0

    def test_pcb_filter_dimensions(self) -> None:
        self.command_test(["-d"])
        self.refpcb.dimensions = 0

    def test_pcb_filter_stackup(self) -> None:
        self.command_test(["--stackup"])
        self.refpcb.stackup = 0

    def test_pcb_filter_side_top(self) -> None:
        self.command_test(["-s", "top"])
        self.refpcb.footprintsB = 0
        self.refpcb.footprintsB_J = 0

    def test_pcb_filter_partial_side_top(self) -> None:
        self.command_test(["-s", "top", "-xo", "+J"])
        self.refpcb.footprintsB = self.refpcb.footprintsB_J

    def test_pcb_filter_side_bottom(self) -> None:
        self.command_test(["-s", "bottom"])
        self.refpcb.footprintsT = 0
        self.refpcb.footprintsT_J = 0

    def test_pcb_filter_partial_side_bottom(self) -> None:
        self.command_test(["-s", "bottom", "-xo", "+J"])
        self.refpcb.footprintsT = self.refpcb.footprintsT_J

    def test_pcb_filter_layers(self) -> None:
        self.command_test(["-l", "User.9,Edge.Cuts,User.Drawings"])
        self.refpcb.graphic_items = (
            16  # some graphics items should be left: SHA, Testpoints/connectors descriptions, Board Edge, ..
            # 2x test-point description + 1x PCB SHA + 2x manual error text
            # on edge.cuts: 5x bezier + 5x board outline + 1x circle
        )
        self.check_ref_val = True
        self.refpcb.references_visible = 0
        self.refpcb.values = 0

    def test_pcb_filter_values(self) -> None:
        self.command_test(["-v"])
        self.check_ref_val = True
        self.refpcb.values = 0

    def test_pcb_filter_references(self) -> None:
        self.command_test(["-r"])
        self.check_ref_val = True
        self.refpcb.references_visible = 0

    def test_pcb_filter_keep_only_pad_one(self) -> None:
        self.command_test(["--first-pads-only"])
        self.assertEqual(self.refpcb.pads_one, self.outpcb.pads)


class BoardStats:
    def __init__(self, board: Path):
        pcb = Board.from_file(board)
        self.footprintsT = len([fp for fp in pcb.footprints if fp.side == BoardSide.FRONT])
        self.footprintsB = len([fp for fp in pcb.footprints if fp.side == BoardSide.BACK])
        self.footprintsT_J = len(
            [fp for fp in pcb.footprints if fp.side == BoardSide.FRONT and fp.properties.ref.value.startswith("J")]
        )
        self.footprintsB_J = len(
            [fp for fp in pcb.footprints if fp.side == BoardSide.BACK and fp.properties.ref.value.startswith("J")]
        )
        self.references_visible = len([fp for fp in pcb.footprints if not fp.properties.ref.hide])
        self.values = len([fp for fp in pcb.footprints if not fp.properties.get("Value", FpProperty).hide])
        self.zones = len(pcb.zones)
        self.dimensions = len(pcb.dimensions)
        self.stackup = len([g for g in pcb.groups if g.name == "group-boardStackUp"])
        self.vias = len([item for item in pcb.traces if isinstance(item, Via)])
        self.tracks = len([item for item in pcb.traces if not isinstance(item, Via)])
        layers = LayerSet(Layer.USER(9), Layer.EDGE_CUTS, Layer.DRAWINGS, *LayerSilkS.all)
        self.graphic_items = len([g for g in pcb.graphic_items if hasattr(g, "layer") and g.layer in layers])
        self.pads_one = sum([len([pad for pad in fp.pads if pad.number in ["1", "A1"]]) for fp in pcb.footprints])
        self.pads = sum([len(fp.pads) for fp in pcb.footprints])


if __name__ == "__main__":
    unittest.main()
