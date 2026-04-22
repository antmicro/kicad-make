import logging
import unittest
from typing import List
from kmake_test_common import KmakeTestCase, get_property, set_property, remove_property
from kiutils.schematic import Schematic
from kiutils.board import Board
import argparse
from commands.prettify import run as prettify


class DnpTest(KmakeTestCase, unittest.TestCase):
    def __init__(self, method_name: str = "runTest") -> None:
        KmakeTestCase.__init__(self, "dnp")
        unittest.TestCase.__init__(self, method_name)

    def setUp(self) -> None:
        KmakeTestCase.setUp(self)
        self.reset_repo()

    def check_symbol(self, components: List[str], dnp: bool, dnp_field: bool = False) -> None:
        """Check if symbols have DNP attribute

        Parameters:
            components: List of designators to check
            dnp: Define if component is DNP
            dnp_field: Allow component to have a DNP field (when dnp is set to False)
        """

        scheet = Schematic().from_file(filepath="receiver.kicad_sch")
        component_count = len(scheet.schematicSymbols)
        components_checked = 0
        for component_id in range(0, component_count):
            symbol = scheet.schematicSymbols[component_id]
            designator = get_property(symbol, "Reference")

            if designator in components:
                if dnp_field:
                    self.assertIsNot(get_property(symbol, "DNP"), None, "Symbol doesn't have DNP property")
                else:
                    self.assertIs(get_property(symbol, "DNP"), None, "Symbol has DNP property")
                if dnp:
                    self.assertTrue(symbol.dnp, "Symbol is not DNP")
                else:
                    self.assertFalse(symbol.dnp, "Symbol is DNP")
                components_checked += 1

        self.assertEqual(components_checked, len(components), "Not all components checked, internal test error")

    def check_footprint(self, components: List[str], dnp: bool) -> None:
        """Check if footprints have `Do not populate` attribute valid

        Parameters:
            component: List of designators to check
            dnp: Define if component is DNP
        """
        pcb = Board().from_file(filepath=self.kpro.pcb_file)
        footprints = pcb.footprints
        footprints_count = len(footprints)
        footprints_checked = 0
        for footprint_id in range(0, footprints_count):
            footprint = footprints[footprint_id]
            designator = get_property(footprint, "Reference")
            if designator in components:
                if dnp:
                    self.assertEqual(footprint.attributes.dnp, True, f"{designator} not set to 'Do not populate'")
                    footprints_checked += 1
                else:
                    self.assertEqual(footprint.attributes.dnp, False, f"{designator} set to 'Do not populate'")
                    footprints_checked += 1
        self.assertEqual(footprints_checked, len(components), "Not all components checked internal test error")

    def test_list_malformed(self) -> None:
        """Test output for only listing malformed DNP properties"""
        with self.assertLogs(level=logging.WARNING) as log:
            with self.assertRaises(SystemExit) as se:
                self.run_test_command(["-l"])
        self.assertIn(
            "Malformed DNP properties found in 2 schematic components:",
            log.output[0][21:78],
        )
        self.assertEqual(se.exception.code, 1)

    def test_clean_symbol(self) -> None:
        "Test if dnp symbols have `Do not populate` attribute set correctly"
        self.check_symbol(["R1", "R2"], False, True)
        self.check_symbol(["R3"], True, False)
        self.check_symbol(["C26", "C27"], False, False)
        self.run_test_command(["--fix-legacy"])
        self.check_symbol(["R1", "R2", "R3"], True, False)
        self.check_symbol(["C26", "C27"], False, False)

    def test_clean_footprint(self) -> None:
        "Test if DNP footprints have `Do not populate` attribute set correctly"
        self.check_footprint(["R1"], False)
        self.check_footprint(["R6"], False)
        self.run_test_command([])
        self.check_footprint(["R1"], True)
        self.check_footprint(["R6"], False)

    def reset_repo(self) -> None:
        """Reset repository to HEAD"""
        self.project_repo.git.reset("--hard", "HEAD")
        self.project_repo.git.clean("-fd")

        # Plant few imperfections in project files
        sch = Schematic().from_file(self.target_dir / "receiver.kicad_sch")
        for s in sch.schematicSymbols:
            ref = get_property(s, "Reference")
            if ref == "R1" or ref == "R2":
                set_property(s, "DNP", "DNP")
                s.dnp = False
            if ref == "R3":
                s.properties = remove_property(s, "DNP")
                s.dnp = True
        sch.to_file()

        pcb = Board().from_file(self.kpro.pcb_file)
        for fp in pcb.footprints:
            if get_property(fp, "Reference") == "R1":
                fp.attributes.dnp = False
                fp.attributes.excludeFromBom = True
        pcb.to_file()
        prettify(self.kpro, argparse.Namespace())
