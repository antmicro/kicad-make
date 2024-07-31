import unittest
from kiutils.schematic import Schematic
from kiutils.board import Board
from kiutils.symbol import SymbolLib
import kmake
import os
import tempfile
import shutil
from pathlib import Path
from typing import List

from common.kicad_project import KicadProject

TEST_COMMAND = "loclib"
TEST_DIR = Path(__file__).parent.resolve()

TARGET: Path

KICAD_PROJECT_DIR = TEST_DIR / "test-designs" / "project-with-kicad-lib"


class GloblibTest(unittest.TestCase):
    def setUp(self) -> None:
        """
        Prepare test files
        """
        global TARGET
        TARGET = Path(tempfile.mkdtemp())
        shutil.copytree(KICAD_PROJECT_DIR, TARGET, dirs_exist_ok=True)
        os.chdir(TARGET)

    def tearDown(self) -> None:
        """Remove tmp directory after test"""
        if os.path.exists(TARGET):
            shutil.rmtree(TARGET)

    def run_test_command(self, arguments: List[str]) -> None:
        self.args = kmake.parse_arguments([TEST_COMMAND] + arguments)
        self.kpro = KicadProject()

        self.args.func(self.kpro, self.args)

    def test_symbols(self) -> None:
        """
        Test if symbols and footprints are from local library
        """
        self.run_test_command([])
        target_sch_path = TARGET / "project-with-kicad-lib.kicad_sch"
        reference_sch_path = (
            TEST_DIR / "reference-outputs" / "project-with-kicad-lib" / "loclib" / "project-with-kicad-lib.kicad_sch"
        )

        target_sch = Schematic().from_file(filepath=str(target_sch_path))
        reference_sch = Schematic().from_file(filepath=str(reference_sch_path))

        target_symbols_libs = sorted([str(symbol.libraryNickname) for symbol in target_sch.libSymbols])
        reference_symbols_libs = sorted([str(symbol.libraryNickname) for symbol in reference_sch.libSymbols])

        self.assertListEqual(target_symbols_libs, reference_symbols_libs)

        target_pcb_path = TARGET / "project-with-kicad-lib.kicad_pcb"
        reference_pcb_path = (
            TEST_DIR / "reference-outputs" / "project-with-kicad-lib" / "loclib" / "project-with-kicad-lib.kicad_pcb"
        )

        target_pcb = Board().from_file(filepath=str(target_pcb_path))
        reference_pcb = Board().from_file(filepath=str(reference_pcb_path))

        target_footprint_libs = sorted([str(footprint.libraryNickname) for footprint in target_pcb.footprints])
        reference_footprint_libs = sorted([str(footprint.libraryNickname) for footprint in reference_pcb.footprints])

        self.assertListEqual(target_footprint_libs, reference_footprint_libs)

    def test_cleanup_symbols(self) -> None:
        """
        Test if unreferenced symbols are removed
        """

        # Check if +5V symbol is in cache
        target_sch_path = TARGET / "project-with-kicad-lib.kicad_sch"
        target_sch = Schematic().from_file(filepath=str(target_sch_path))
        target_symbols_libs = sorted([str(symbol.entryName) for symbol in target_sch.libSymbols])
        self.assertIn("+5V", target_symbols_libs)

        self.run_test_command(["--cleanup"])

        target_sch = Schematic().from_file(filepath=str(target_sch_path))
        target_symbols_libs = sorted([str(symbol.entryName) for symbol in target_sch.libSymbols])
        self.assertNotIn("+5V", target_symbols_libs)

    def test_force(self) -> None:
        """
        Test the --force switch
        """
        self.run_test_command([])
        kicad_power_lib_path = "/usr/share/kicad/symbols/power.kicad_sym"
        target_lib_path = TARGET / "lib" / "project-with-kicad-lib.kicad_sym"

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
