import unittest
from kmake_test_common import KmakeTestCase
from kiutils.schematic import Schematic
from kiutils.board import Board


class NOPTest(KmakeTestCase, unittest.TestCase):

    def __init__(self, method_name: str = "runTest") -> None:
        KmakeTestCase.__init__(self, "nop")
        unittest.TestCase.__init__(self, method_name)

    def test_load_save(self) -> None:
        """Load and save all project files without doing any changes"""

        for sch_path in self.target_dir.glob("*.kicad_sch"):
            sch = Schematic().from_file(sch_path)
            sch.to_file()

        pcb = Board().from_file(self.kpro.pcb_file)
        pcb.to_file()
        for d in self.project_repo.index.diff(None):
            self.assertEqual(d.diff, "", f"Difference found in {d.a_path}:\n{d.diff}")
