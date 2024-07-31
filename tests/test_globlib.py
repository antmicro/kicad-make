import unittest
from kiutils.schematic import Schematic
from kiutils.board import Board
import kmake
import os
from pathlib import Path
from typing import List
import tempfile
import shutil

from common.kicad_project import KicadProject

TEST_COMMAND = "globlib"
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

    def loclib_test_project(self) -> None:
        """
        Loclib test project
        """
        os.chdir(TARGET)

        args = kmake.parse_arguments(["loclib"])
        kpro = KicadProject()
        args.func(kpro, args)

    def compare_symbols_libraries(self) -> None:
        """
        Compare libraries of symbol used in kicad schematic files
        """

        target_sch_path = TARGET / "project-with-kicad-lib.kicad_sch"

        reference_sch_path = (
            TEST_DIR / "reference-outputs" / "project-with-kicad-lib" / "globlib" / "project-with-kicad-lib.kicad_sch"
        )

        target_sch = Schematic().from_file(filepath=str(target_sch_path))
        reference_sch = Schematic().from_file(filepath=str(reference_sch_path))

        target_symbols_libs = sorted([str(symbol.libraryNickname) for symbol in target_sch.libSymbols])
        reference_symbols_libs = sorted([str(symbol.libraryNickname) for symbol in reference_sch.libSymbols])

        self.assertListEqual(target_symbols_libs, reference_symbols_libs)

    def compare_footprints_libraries(self) -> None:
        """
        Compare libraries of footprints used in kicad schematic files
        """

        target_pcb_path = TARGET / "project-with-kicad-lib.kicad_pcb"
        reference_pcb_path = (
            TEST_DIR / "reference-outputs" / "project-with-kicad-lib" / "globlib" / "project-with-kicad-lib.kicad_pcb"
        )

        target_pcb = Board().from_file(filepath=str(target_pcb_path))
        reference_pcb = Board().from_file(filepath=str(reference_pcb_path))

        target_footprint_libs = sorted([str(footprint.libraryNickname) for footprint in target_pcb.footprints])
        reference_footprint_libs = sorted([str(footprint.libraryNickname) for footprint in reference_pcb.footprints])

        self.assertListEqual(target_footprint_libs, reference_footprint_libs)

    def test_symbols(self) -> None:
        """
        Test if symbols and footprints are from global library
        """
        self.loclib_test_project()
        self.run_test_command(["--include-kicad-lib"])

        self.compare_symbols_libraries()
        self.compare_footprints_libraries()

    def test_exclude_pcb(self) -> None:
        """
        Test if only symbols and are globlibed when --exclude-pcb switch is used
        """
        self.loclib_test_project()
        self.run_test_command(["--include-kicad-lib", "--exclude-pcb"])

        self.compare_symbols_libraries()

        target_pcb_path = TARGET / "project-with-kicad-lib.kicad_pcb"
        target_pcb = Board().from_file(filepath=str(target_pcb_path))
        target_footprint_libs = [footprint.libraryNickname for footprint in target_pcb.footprints]

        for footprint_lib in target_footprint_libs:
            self.assertEqual(footprint_lib, "project-with-kicad-lib-footprints")

    def test_list_of_schematic(self) -> None:
        """
        Test if symbols in files provided by -s flag are globlibed
        """
        self.loclib_test_project()
        self.run_test_command(["--include-kicad-lib", "-s", "project-with-kicad-lib.kicad_sch"])

        self.compare_symbols_libraries()

        target_pcb_path = TARGET / "project-with-kicad-lib.kicad_pcb"
        target_pcb = Board().from_file(filepath=str(target_pcb_path))
        target_footprint_libs = [footprint.libraryNickname for footprint in target_pcb.footprints]

        for footprint_lib in target_footprint_libs:
            self.assertEqual(footprint_lib, "project-with-kicad-lib-footprints")

    def test_update_properties_symbols(self) -> None:
        """
        Test if symbol protperites are updated when --update-properties flag is used
        """
        self.loclib_test_project()

        sch_path = TARGET / "project-with-kicad-lib.kicad_sch"
        sch_file = Schematic().from_file(filepath=str(sch_path))
        symbols = sch_file.schematicSymbols

        # Check properties before update

        r1_on_pcb = False
        for symbol in symbols:
            if symbol.instances[0].paths[0].reference == "R1":
                self.assertEqual(symbol.properties[1].value, "4k7")
                self.assertEqual(
                    symbol.properties[2].value,
                    "project-with-kicad-lib-footprints:R_0402_1005Metric_Pad0.72x0.64mm_HandSolder",
                )
                self.assertEqual(symbol.properties[3].value, "www.example.com")
                r1_on_pcb = True

        self.assertTrue(r1_on_pcb)

        self.run_test_command(["--include-kicad-lib", "--update-properties"])

        sch_file = Schematic().from_file(filepath=str(sch_path))
        symbols = sch_file.schematicSymbols

        r1_on_pcb = False
        for symbol in symbols:
            if symbol.instances[0].paths[0].reference == "R1":
                self.assertEqual(symbol.properties[1].value, "R_Small")  # Symbol value
                self.assertEqual(
                    symbol.properties[2].value,
                    "",
                )  #  Footprint
                self.assertEqual(symbol.properties[3].value, "~")  # Datascheet
                r1_on_pcb = True

        self.assertTrue(r1_on_pcb)

    def test_update_properties_footprint(self) -> None:
        """
        Test if footprint protperites are updated when --update-properties flag is used
        """
        self.loclib_test_project()

        pcb_path = TARGET / "project-with-kicad-lib.kicad_pcb"
        pcb_file = Board().from_file(filepath=str(pcb_path))
        footprints = pcb_file.footprints

        r1_on_pcb = False
        for footprint in footprints:
            if footprint.graphicItems[0].text == "R1":
                self.assertEqual(footprint.graphicItems[1].text, "4k7")
                r1_on_pcb = True

        self.assertTrue(r1_on_pcb)
        self.run_test_command(["--include-kicad-lib", "--update-properties"])

        pcb_file = Board().from_file(filepath=str(pcb_path))
        footprints = pcb_file.footprints

        r1_on_pcb = False
        for footprint in footprints:
            if footprint.graphicItems[0].text == "R1":
                self.assertEqual(footprint.graphicItems[1].text, "R_Small")
                r1_on_pcb = True

        self.assertTrue(r1_on_pcb)

    def test_update_all_symbols(self) -> None:
        """
        Test if properties of symbols from global libs are update when --update-all switch is used
        """
        self.loclib_test_project()
        # Change symbol properites
        sch_path = TARGET / "project-with-kicad-lib.kicad_sch"

        sch_file = Schematic().from_file(filepath=str(sch_path))
        symbols = sch_file.schematicSymbols
        r1_on_sch = False

        for symbol in symbols:
            if symbol.instances[0].paths[0].reference == "R1":
                symbol.properties[1].value = "4k7"  # Symbol value
                symbol.properties[2].value = "Resistor_SMD:R_2010_5025Metric"  # Footprint
                symbol.properties[3].value = "www.example.com"  # Datascheet

                r1_on_sch = True
        self.assertTrue(r1_on_sch)

        sch_file.to_file(filepath=str(sch_path))

        # Check if symbol properties are updated
        sch_file = Schematic().from_file(filepath=str(sch_path))
        symbols = sch_file.schematicSymbols
        r1_on_sch = False

        for symbol in symbols:
            if symbol.instances[0].paths[0].reference == "R1":
                self.assertEqual(symbol.properties[1].value, "4k7")  # Symbol value
                self.assertEqual(symbol.properties[2].value, "Resistor_SMD:R_2010_5025Metric")  # Footprint
                self.assertEqual(symbol.properties[3].value, "www.example.com")  # Datascheet

                r1_on_sch = True
        self.assertTrue(r1_on_sch)

        self.run_test_command(["--include-kicad-lib", "--update-all"])

        sch_file = Schematic().from_file(filepath=str(sch_path))
        symbols = sch_file.schematicSymbols

        r1_on_sch = False
        for symbol in symbols:
            if symbol.instances[0].paths[0].reference == "R1":
                self.assertEqual(symbol.properties[1].value, "4k7")  # Symbol value
                self.assertEqual(symbol.properties[2].value, "")  # Footprint
                self.assertEqual(symbol.properties[3].value, "www.example.com")  # Datascheet

                r1_on_sch = True
        self.assertTrue(r1_on_sch)

    def test_without_loclib(self) -> None:
        """
        Test if symbols are from global library
        """
        self.run_test_command(["--include-kicad-lib", "--update-all"])

        self.compare_symbols_libraries()
        self.compare_footprints_libraries()


if __name__ == "__main__":
    unittest.main()
