from pathlib import Path
import unittest

from askiff import Board, Schematic
from kmake_test_common import KmakeTestCase


class GloblibTest(KmakeTestCase, unittest.TestCase):
    def __init__(self, method_name: str = "runTest") -> None:
        KmakeTestCase.__init__(self, "globlib")
        unittest.TestCase.__init__(self, method_name)

    def setUp(self) -> None:
        KmakeTestCase.setUp(self)
        self.r1_sch = self.kpro.fs_path / "receiver.kicad_sch"

    def compare_symbols_libraries(self, file_list: list[Path] | None = None) -> None:
        """
        Compare libraries of symbol used in kicad schematic files
        """
        if not file_list:
            file_list = self.kpro.fs_path.glob("*" + Schematic.fs_ext)

        for sch in file_list:
            target_sch = Schematic.from_file(sch)
            reference_sch = Schematic.from_file(self.ref_dir / sch.name)

            # globlib currently does not support non global libraries
            # so skip symbol_power_local which is included via local library table
            skip_sym_name = "symbol_power_local"
            target_symbols_libs = sorted(
                [
                    symbol.lib_id.library or ""
                    for symbol in target_sch.lib_symbols
                    if symbol.lib_id.name != skip_sym_name
                ]
            )
            reference_symbols_libs = sorted(
                [
                    symbol.lib_id.library or ""
                    for symbol in reference_sch.lib_symbols
                    if symbol.lib_id.name != skip_sym_name
                ]
            )

            self.assertListEqual(target_symbols_libs, reference_symbols_libs)

    def compare_footprints_libraries(self) -> None:
        """
        Compare libraries of footprints used in kicad schematic files
        """

        target_pcb = Board.from_file(self.kpro.pcb_file)
        reference_pcb = Board.from_file(self.ref_dir / self.kpro.pcb_file)

        target_footprint_libs = sorted([footprint.lib_id.library or "" for footprint in target_pcb.footprints])
        reference_footprint_libs = sorted([footprint.lib_id.library or "" for footprint in reference_pcb.footprints])

        self.assertListEqual(target_footprint_libs, reference_footprint_libs)

    def test_symbols(self) -> None:
        """
        Test if symbols and footprints are from global library
        """
        self.run_kmake_command(["loclib"])
        self.run_test_command(["--include-kicad-lib"])

        self.compare_symbols_libraries()
        self.compare_footprints_libraries()

    def test_exclude_pcb(self) -> None:
        """
        Test if only symbols and are globlibed when --exclude-pcb switch is used
        """
        self.run_kmake_command(["loclib"])
        self.run_test_command(["--include-kicad-lib", "--exclude-pcb"])

        self.compare_symbols_libraries()

        target_pcb = Board.from_file(self.kpro.pcb_file)
        target_footprint_libs = [footprint.lib_id.library for footprint in target_pcb.footprints]
        target_footprint_entry_names = [footprint.lib_id.name for footprint in target_pcb.footprints]

        for footprint_lib, footprint_entry_name in zip(
            target_footprint_libs, target_footprint_entry_names, strict=True
        ):
            if not footprint_entry_name.startswith("kibuzzard"):  # kibuzzards are omitted by loclib and globlib
                self.assertEqual(footprint_lib, "test_project-footprints")

    def test_list_of_schematic(self) -> None:
        """
        Test if symbols in files provided by -s flag are globlibed
        """
        self.run_kmake_command(["loclib"])
        self.run_test_command(["--include-kicad-lib", "-s", str(self.r1_sch)])

        self.compare_symbols_libraries(file_list=[self.r1_sch])

        target_pcb = Board.from_file(self.kpro.pcb_file)
        target_footprint_libs = [footprint.lib_id.library for footprint in target_pcb.footprints]
        target_footprint_entry_names = [footprint.lib_id.name for footprint in target_pcb.footprints]

        for footprint_lib, footprint_entry_name in zip(
            target_footprint_libs, target_footprint_entry_names, strict=True
        ):
            if not footprint_entry_name.startswith("kibuzzard"):  # kibuzzards are omitted by loclib and globlib
                self.assertEqual(footprint_lib, "test_project-footprints")

    def test_update_properties_symbols(self) -> None:
        """
        Test if symbol protperites are updated when --update-properties flag is used
        """
        self.run_kmake_command(["loclib"])

        sch_file = Schematic.from_file(self.r1_sch)
        symbols = sch_file.symbols

        # Check properties before update

        r1_on_pcb = False
        for symbol in symbols:
            if symbol.properties.ref.value == "R1":
                self.assertEqual(symbol.properties.get_value("Value"), "10k")
                self.assertEqual(
                    symbol.properties.get_value("Footprint"),
                    "test_project-footprints:R_0402_1005Metric",
                )
                self.assertEqual(symbol.properties.get_value("Datasheet"), "www.example.com")
                r1_on_pcb = True

        self.assertTrue(r1_on_pcb)

        self.run_test_command(["--include-kicad-lib", "--update-properties"])

        sch_file = Schematic.from_file(self.r1_sch)
        symbols = sch_file.symbols

        r1_on_pcb = False
        for symbol in symbols:
            if symbol.properties.ref.value == "R1":
                self.assertEqual(symbol.properties.get_value("Value"), "R")
                self.assertEqual(symbol.properties.get_value("Footprint"), "")
                expected_datasheet_val = "~" if self.kpro.kicad_version_major == "9" else ""
                self.assertEqual(symbol.properties.get_value("Datasheet"), expected_datasheet_val)
                r1_on_pcb = True

        self.assertTrue(r1_on_pcb)

    def test_update_properties_footprint(self) -> None:
        """
        Test if footprint properties are updated when --update-properties flag is used
        """
        self.run_kmake_command(["loclib"])

        pcb_file = Board.from_file(self.kpro.pcb_file)
        footprints = pcb_file.footprints

        r1_on_pcb = False
        for footprint in footprints:
            if footprint.properties.ref.value == "R1":
                self.assertEqual(footprint.properties.get_value("Value"), "10k")
                r1_on_pcb = True

        self.assertTrue(r1_on_pcb)
        self.run_test_command(["--include-kicad-lib", "--update-properties"])

        pcb_file = Board.from_file(self.kpro.pcb_file)
        footprints = pcb_file.footprints

        r1_on_pcb = False
        for footprint in footprints:
            if footprint.properties.ref.value == "R1":
                self.assertEqual(footprint.properties.get_value("Value"), "R")
                r1_on_pcb = True

        self.assertTrue(r1_on_pcb)

    def test_update_all_symbols(self) -> None:
        """
        Test if properties of symbols from global libs are update when --update-all switch is used
        """
        self.run_kmake_command(["loclib"])
        # Change symbol properites

        sch_file = Schematic.from_file(self.r1_sch)
        symbols = sch_file.symbols
        r1_on_sch = False

        for symbol in symbols:
            if symbol.properties.ref.value == "R1":
                symbol.properties.set("Value", "4k7")
                symbol.properties.set("Footprint", "Resistor_SMD:R_2010_5025Metric")
                symbol.properties.set("Datasheet", "www.example.com")
                r1_on_sch = True
        self.assertTrue(r1_on_sch)

        sch_file.to_file()

        # Check if symbol properties are updated
        sch_file = Schematic.from_file(self.r1_sch)
        symbols = sch_file.symbols
        r1_on_sch = False

        for symbol in symbols:
            if symbol.properties.ref.value == "R1":
                self.assertEqual(symbol.properties.get_value("Value"), "4k7")
                self.assertEqual(symbol.properties.get_value("Footprint"), "Resistor_SMD:R_2010_5025Metric")
                self.assertEqual(symbol.properties.get_value("Datasheet"), "www.example.com")

                r1_on_sch = True
        self.assertTrue(r1_on_sch)

        self.run_test_command(["--include-kicad-lib", "--update-all"])

        sch_file = Schematic.from_file(self.r1_sch)
        symbols = sch_file.symbols

        r1_on_sch = False
        for symbol in symbols:
            if symbol.properties.ref.value == "R1":
                self.assertEqual(symbol.properties.get_value("Value"), "4k7")
                self.assertEqual(symbol.properties.get_value("Footprint"), "")
                self.assertEqual(symbol.properties.get_value("Datasheet"), "www.example.com")

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
