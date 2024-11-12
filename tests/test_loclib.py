import unittest
from kiutils.schematic import Schematic
from kiutils.board import Board
from kiutils.symbol import SymbolLib
from kmake_test_common import KmakeTestCase
from pathlib import Path


class LoclibTest(KmakeTestCase, unittest.TestCase):

    def __init__(self, method_name: str = "runTest") -> None:
        KmakeTestCase.__init__(self, "loclib")
        unittest.TestCase.__init__(self, method_name)

    def test_symbols(self) -> None:
        """
        Test if symbols and footprints are from local library
        """
        self.run_test_command([])

        for sch in Path(self.kpro.dir).glob(".kicad_sch"):
            target_sch = Schematic().from_file(filepath=str(sch))
            reference_sch = Schematic().from_file(filepath=str(self.ref_dir / sch.name))

            target_symbols_libs = sorted([str(symbol.libraryNickname) for symbol in target_sch.libSymbols])
            reference_symbols_libs = sorted([str(symbol.libraryNickname) for symbol in reference_sch.libSymbols])

            self.assertListEqual(target_symbols_libs, reference_symbols_libs)

        target_pcb = Board().from_file(filepath=str(self.kpro.pcb_file))
        reference_pcb = Board().from_file(filepath=str(self.ref_dir / self.kpro.pcb_file))

        target_footprint_libs = sorted([str(footprint.libraryNickname) for footprint in target_pcb.footprints])
        reference_footprint_libs = sorted([str(footprint.libraryNickname) for footprint in reference_pcb.footprints])

        self.assertListEqual(target_footprint_libs, reference_footprint_libs)

    def test_cleanup_symbols(self) -> None:
        """
        Test if unreferenced symbols are removed
        """

        # Check if +5V symbol is in cache
        target_sch = Schematic().from_file(filepath=str(self.kpro.sch_root))
        target_symbols_libs = sorted([str(symbol.entryName) for symbol in target_sch.libSymbols])
        self.assertIn("DIAC", target_symbols_libs)

        self.run_test_command(["--cleanup"])

        target_sch = Schematic().from_file(filepath=str(self.kpro.sch_root))
        target_symbols_libs = sorted([str(symbol.entryName) for symbol in target_sch.libSymbols])
        self.assertNotIn("DIAC", target_symbols_libs)

    def test_force(self) -> None:
        """
        Test the --force switch
        """
        self.run_test_command([])

        self.check_if_pcb_sch_opens()
        kicad_power_lib_path = "/usr/share/kicad/symbols/power.kicad_sym"
        target_lib_path = self.target_dir / "lib" / "test_project.kicad_sym"

        kicad_lib = SymbolLib().from_file(filepath=str(kicad_power_lib_path))
        target_lib = SymbolLib().from_file(filepath=str(target_lib_path))
        target_lib.symbols = target_lib.symbols + kicad_lib.symbols
        target_lib.to_file(filepath=str(target_lib_path))

        target_lib = SymbolLib().from_file(filepath=str(target_lib_path))
        target_symbols = sorted([str(symbol.entryName) for symbol in target_lib.symbols])
        self.assertIn("VCC", target_symbols)

        self.run_test_command(["--force"])

        target_lib = SymbolLib().from_file(filepath=str(target_lib_path))
        target_symbols = sorted([str(symbol.entryName) for symbol in target_lib.symbols])
        self.assertNotIn("VCC", target_symbols)


if __name__ == "__main__":
    unittest.main()
