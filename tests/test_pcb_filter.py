import unittest
import kmake
import os
from pathlib import Path
from typing import List
from git import Repo
from kiutils.board import Board
from kiutils.footprint import Footprint
from kiutils.items.fpitems import FpText
from kiutils.items.brditems import Via

from common.kicad_project import KicadProject
from common.kmake_helper import run_kicad_cli

TEST_COMMAND = "pcb-filter"
TEST_DIR = Path(__file__).parent.resolve()
# path to test design repository
DESIGN_DIR = TEST_DIR / "test-designs" / "cm4-baseboard"


class PCBFilterTest(unittest.TestCase):
    def command_test(self, args: List[str], name: str) -> None:
        # change current directory to the test design repository
        # as kmake expects to be run from the root of the test repository
        os.chdir(DESIGN_DIR)
        try:
            os.mkdir("out")
        except FileExistsError:
            pass
        self.outfile = str(DESIGN_DIR / "out" / f"{name}.kicad_pcb")
        # parse arguments for the test command
        self.args = kmake.parse_arguments([TEST_COMMAND] + args + ["-o", self.outfile])
        self.kpro = KicadProject()
        self.args.func(self.kpro, self.args)
        self.outpcb = BoardStats(self.outfile)
        self.refpcb = self.inpcb

    def setUp(self) -> None:
        kicad_project_repo = Repo(DESIGN_DIR)
        kicad_project_repo.git.reset("--hard", "HEAD")
        kicad_project_repo.git.clean("-fd")
        self.inpcb = BoardStats(str(DESIGN_DIR / "cm4-baseboard.kicad_pcb"))

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

        # run kicad-cli over generated file to check if its still valid Kicad-file

        cmd = ["pcb", "export", "pos", self.outfile]
        run_kicad_cli(cmd, False)

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
        self.refpcb.references = self.refpcb.footprintsT + self.refpcb.footprintsB
        self.refpcb.values = self.refpcb.footprintsT + self.refpcb.footprintsB

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
        self.refpcb.references = self.refpcb.footprintsT
        self.refpcb.values = self.refpcb.footprintsT

    def test_pcb_filter_partial_side_top(self) -> None:
        self.command_test(["-s", "top", "-ao", "J"], "partial_side_top")
        self.refpcb.footprintsB = self.refpcb.footprintsB_J
        self.refpcb.references = self.refpcb.footprintsT + self.refpcb.footprintsB
        self.refpcb.values = self.refpcb.footprintsT + self.refpcb.footprintsB

    def test_pcb_filter_side_bottom(self) -> None:
        self.command_test(["-s", "bottom"], "side_bottom")
        self.refpcb.footprintsT = 0
        self.refpcb.footprintsT_J = 0
        self.refpcb.references = self.refpcb.footprintsB
        self.refpcb.values = self.refpcb.footprintsB

    def test_pcb_filter_partial_side_bottom(self) -> None:
        self.command_test(["-s", "bottom", "-ao", "J"], "partial_side_bottom")
        self.refpcb.footprintsT = self.refpcb.footprintsT_J
        self.refpcb.references = self.refpcb.footprintsT + self.refpcb.footprintsB
        self.refpcb.values = self.refpcb.footprintsT + self.refpcb.footprintsB

    def test_pcb_filter_layers(self) -> None:
        self.command_test(["-l", "User.9,Edge.Cuts,User.Drawings"], "layers")
        self.refpcb.graphicItems = 12  # some graphics items should be left: SHA, Testpoints/connectors descriptions,..
        self.refpcb.footprintsT_J = 0
        self.refpcb.footprintsB_J = 0
        self.refpcb.references = 0
        self.refpcb.values = 0

    def test_pcb_filter_values(self) -> None:
        self.command_test(["-v"], "values")
        self.refpcb.values = 0

    def test_pcb_filter_references(self) -> None:
        self.command_test(["-r"], "references")
        self.refpcb.references = 0
        self.refpcb.footprintsT_J = 0
        self.refpcb.footprintsB_J = 0


class BoardStats:
    def __init__(self, board: str):
        pcb = Board.from_file(board)
        self.footprintsT = len([fp for fp in pcb.footprints if fp.layer == "F.Cu"])
        self.footprintsB = len([fp for fp in pcb.footprints if fp.layer == "B.Cu"])
        self.footprintsT_J = len([fp for fp in pcb.footprints if fp.layer == "F.Cu" and self.ref_match(fp, "J")])
        self.footprintsB_J = len([fp for fp in pcb.footprints if fp.layer == "B.Cu" and self.ref_match(fp, "J")])
        self.references = len([fp for fp in pcb.footprints if self.ref_match(fp)])
        self.values = len([fp for fp in pcb.footprints if self.ref_match(fp, field="value")])
        self.zones = len(pcb.zones)
        self.dimensions = len(pcb.dimensions)
        self.stackup = len([g for g in pcb.groups if g.name == "group-boardStackUp"])
        self.vias = len([item for item in pcb.traceItems if isinstance(item, Via)])
        self.tracks = len([item for item in pcb.traceItems if not isinstance(item, Via)])
        self.graphicItems = len([g for g in pcb.graphicItems if g.layer in ["User.9", "Edge.Cuts", "User.Drawings"]])

    @staticmethod
    def ref_match(fp: Footprint, ref: str = "*", field: str = "reference") -> bool:
        for item in fp.graphicItems:
            if not isinstance(item, FpText):
                continue
            if item.type != field:
                continue
            if ref == "*" or item.text.removeprefix(ref)[0].isdecimal():
                return True
            return False
        return False


if __name__ == "__main__":
    unittest.main()
