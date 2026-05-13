import unittest
from pathlib import Path

from askiff import Board, Schematic, SymbolFile
from kmake_test_common import KmakeTestCase


class LoclibTest(KmakeTestCase, unittest.TestCase):
    def __init__(self, method_name: str = "runTest") -> None:
        KmakeTestCase.__init__(self, "loclib")
        unittest.TestCase.__init__(self, method_name)

    def test_symbols(self) -> None:
        """
        Test if symbols and footprints are from local library
        """
        self.run_test_command([])

        for sch in Path(self.kpro.fs_path).glob(".kicad_sch"):
            target_sch = Schematic.from_file(sch)
            reference_sch = Schematic.from_file(self.ref_dir / sch.name)

            target_symbols_libs = sorted([symbol.lib_id.library or "" for symbol in target_sch.lib_symbols])
            reference_symbols_libs = sorted([symbol.lib_id.library or "" for symbol in reference_sch.lib_symbols])

            self.assertListEqual(target_symbols_libs, reference_symbols_libs)

        target_pcb = Board.from_file(self.kpro.pcb_file)
        reference_pcb = Board.from_file(self.ref_dir / self.kpro.pcb_file)

        target_footprint_libs = sorted([footprint.lib_id.library or "" for footprint in target_pcb.footprints])
        reference_footprint_libs = sorted([footprint.lib_id.library or "" for footprint in reference_pcb.footprints])

        self.assertListEqual(target_footprint_libs, reference_footprint_libs)

    def test_cleanup_symbols(self) -> None:
        """
        Test if unreferenced symbols are removed
        """

        # Check if +5V symbol is in cache
        target_sch = Schematic.from_file(self.kpro.sch_root.fs_path)
        target_symbols_libs = sorted([symbol.lib_id.name for symbol in target_sch.lib_symbols])
        self.assertIn("DIAC", target_symbols_libs)

        self.run_test_command(["--cleanup"])

        target_sch = Schematic.from_file(self.kpro.sch_root.fs_path)
        target_symbols_libs = sorted([symbol.lib_id.name for symbol in target_sch.lib_symbols])
        self.assertNotIn("DIAC", target_symbols_libs)

    def test_force(self) -> None:
        """
        Test the --force switch
        """
        self.run_test_command([])

        self.check_if_pcb_sch_opens()
        kicad_power_lib_path = Path("/usr/share/kicad/symbols/power.kicad_sym")
        target_lib_path = self.target_dir / "lib" / "test_project.kicad_sym"

        kicad_lib = SymbolFile.from_file(kicad_power_lib_path)
        target_lib = SymbolFile.from_file(target_lib_path)
        target_lib.symbols = target_lib.symbols + kicad_lib.symbols
        target_lib.to_file()

        target_lib = SymbolFile.from_file(target_lib_path)
        target_symbols = sorted([symbol.lib_id.name for symbol in target_lib.symbols])
        self.assertIn("VCC", target_symbols)

        self.run_test_command(["--force"])

        target_lib = SymbolFile.from_file(target_lib_path)
        target_symbols = sorted([str(symbol.lib_id.name) for symbol in target_lib.symbols])
        self.assertNotIn("VCC", target_symbols)


if __name__ == "__main__":
    unittest.main()
