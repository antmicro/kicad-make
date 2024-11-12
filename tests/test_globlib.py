import unittest
from kiutils.schematic import Schematic
from kiutils.board import Board
import kmake
from kmake_test_common import KmakeTestCase
from common.kmake_helper import get_property, set_property
from pathlib import Path


class GloblibTest(KmakeTestCase, unittest.TestCase):

    def __init__(self, method_name: str = "runTest") -> None:
        KmakeTestCase.__init__(self, "globlib")
        unittest.TestCase.__init__(self, method_name)

    def setUp(self) -> None:
        super().setUp()
        self.r1_sch = str(Path(self.kpro.dir) / "receiver.kicad_sch")

    def loclib_test_project(self) -> None:
        """
        Loclib test project
        """

        args = kmake.parse_arguments(["loclib"])
        args.func(self.kpro, args)

    def compare_symbols_libraries(self) -> None:
        """
        Compare libraries of symbol used in kicad schematic files
        """

        for sch in Path(self.kpro.dir).glob(".kicad_sch"):
            target_sch = Schematic().from_file(filepath=str(sch))
            reference_sch = Schematic().from_file(filepath=str(self.ref_dir / sch.name))

            target_symbols_libs = sorted([str(symbol.libraryNickname) for symbol in target_sch.libSymbols])
            reference_symbols_libs = sorted([str(symbol.libraryNickname) for symbol in reference_sch.libSymbols])

            self.assertListEqual(target_symbols_libs, reference_symbols_libs)

    def compare_footprints_libraries(self) -> None:
        """
        Compare libraries of footprints used in kicad schematic files
        """

        target_pcb = Board().from_file(filepath=str(self.kpro.pcb_file))
        reference_pcb = Board().from_file(filepath=str(self.ref_dir / self.kpro.pcb_file))

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

        target_pcb = Board().from_file(filepath=str(self.kpro.pcb_file))
        target_footprint_libs = [footprint.libraryNickname for footprint in target_pcb.footprints]
        target_footprint_entry_names = [footprint.entryName for footprint in target_pcb.footprints]

        for footprint_lib, footprint_entry_name in zip(target_footprint_libs, target_footprint_entry_names):
            if not footprint_entry_name.startswith("kibuzzard"):  # kibuzzards are omitted by loclib and globlib
                self.assertEqual(footprint_lib, "test_project-footprints")

    def test_list_of_schematic(self) -> None:
        """
        Test if symbols in files provided by -s flag are globlibed
        """
        self.loclib_test_project()
        self.run_test_command(["--include-kicad-lib", "-s", self.r1_sch])

        self.compare_symbols_libraries()

        target_pcb = Board().from_file(filepath=str(self.kpro.pcb_file))
        target_footprint_libs = [footprint.libraryNickname for footprint in target_pcb.footprints]
        target_footprint_entry_names = [footprint.entryName for footprint in target_pcb.footprints]

        for footprint_lib, footprint_entry_name in zip(target_footprint_libs, target_footprint_entry_names):
            if not footprint_entry_name.startswith("kibuzzard"):  # kibuzzards are omitted by loclib and globlib
                self.assertEqual(footprint_lib, "test_project-footprints")

    def test_update_properties_symbols(self) -> None:
        """
        Test if symbol protperites are updated when --update-properties flag is used
        """
        self.loclib_test_project()

        sch_file = Schematic().from_file(filepath=self.r1_sch)
        symbols = sch_file.schematicSymbols

        # Check properties before update

        r1_on_pcb = False
        for symbol in symbols:
            if get_property(symbol, "Reference") == "R1":
                self.assertEqual(get_property(symbol, "Value"), "10k")
                self.assertEqual(
                    get_property(symbol, "Footprint"),
                    "test_project-footprints:R_0402_1005Metric",
                )
                self.assertEqual(get_property(symbol, "Datasheet"), "www.example.com")
                r1_on_pcb = True

        self.assertTrue(r1_on_pcb)

        self.run_test_command(["--include-kicad-lib", "--update-properties"])

        sch_file = Schematic().from_file(filepath=self.r1_sch)
        symbols = sch_file.schematicSymbols

        r1_on_pcb = False
        for symbol in symbols:
            if get_property(symbol, "Reference") == "R1":
                self.assertEqual(get_property(symbol, "Value"), "R")
                self.assertEqual(get_property(symbol, "Footprint"), "")
                self.assertEqual(get_property(symbol, "Datasheet"), "~")
                r1_on_pcb = True

        self.assertTrue(r1_on_pcb)

    def test_update_properties_footprint(self) -> None:
        """
        Test if footprint properties are updated when --update-properties flag is used
        """
        self.loclib_test_project()

        pcb_file = Board().from_file(filepath=str(self.kpro.pcb_file))
        footprints = pcb_file.footprints

        r1_on_pcb = False
        for footprint in footprints:
            if get_property(footprint, "Reference") == "R1":
                self.assertEqual(get_property(footprint, "Value"), "10k")
                r1_on_pcb = True

        self.assertTrue(r1_on_pcb)
        self.run_test_command(["--include-kicad-lib", "--update-properties"])

        pcb_file = Board().from_file(filepath=str(self.kpro.pcb_file))
        footprints = pcb_file.footprints

        r1_on_pcb = False
        for footprint in footprints:
            if get_property(footprint, "Reference") == "R1":
                self.assertEqual(get_property(footprint, "Value"), "R")
                r1_on_pcb = True

        self.assertTrue(r1_on_pcb)

    def test_update_all_symbols(self) -> None:
        """
        Test if properties of symbols from global libs are update when --update-all switch is used
        """
        self.loclib_test_project()
        # Change symbol properites

        sch_file = Schematic().from_file(filepath=self.r1_sch)
        symbols = sch_file.schematicSymbols
        r1_on_sch = False

        for symbol in symbols:
            if get_property(symbol, "Reference") == "R1":
                set_property(symbol, "Value", "4k7")
                set_property(symbol, "Footprint", "Resistor_SMD:R_2010_5025Metric")
                set_property(symbol, "Datasheet", "www.example.com")
                r1_on_sch = True
        self.assertTrue(r1_on_sch)

        sch_file.to_file(filepath=self.r1_sch)

        # Check if symbol properties are updated
        sch_file = Schematic().from_file(filepath=self.r1_sch)
        symbols = sch_file.schematicSymbols
        r1_on_sch = False

        for symbol in symbols:
            if get_property(symbol, "Reference") == "R1":
                self.assertEqual(get_property(symbol, "Value"), "4k7")
                self.assertEqual(get_property(symbol, "Footprint"), "Resistor_SMD:R_2010_5025Metric")
                self.assertEqual(get_property(symbol, "Datasheet"), "www.example.com")

                r1_on_sch = True
        self.assertTrue(r1_on_sch)

        self.run_test_command(["--include-kicad-lib", "--update-all"])

        sch_file = Schematic().from_file(filepath=self.r1_sch)
        symbols = sch_file.schematicSymbols

        r1_on_sch = False
        for symbol in symbols:
            if get_property(symbol, "Reference") == "R1":
                self.assertEqual(get_property(symbol, "Value"), "4k7")
                self.assertEqual(get_property(symbol, "Footprint"), "")
                self.assertEqual(get_property(symbol, "Datasheet"), "www.example.com")

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
