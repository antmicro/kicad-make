import unittest

import kiutils
import kmake
import os
import logging
from pathlib import Path
from git import Repo
from typing import List

from common.kicad_project import KicadProject
from common.kmake_helper import get_property, set_property

TEST_COMMAND = "dnp"
TEST_DIR = Path(__file__).parent.resolve()

# path to test design repository
TARGET = TEST_DIR / "test-designs" / "cm4-baseboard"


class DnpTest(unittest.TestCase):
    def run_test_command(self, arguments: List[str]) -> None:
        "Template for running commands"
        self.args = kmake.parse_arguments([TEST_COMMAND] + arguments)
        self.kpro = KicadProject()
        self.args.func(self.kpro, self.args)

    def get_footprint_designator(self, footprint: kiutils.footprint) -> str:
        """Return designator of footprint"""
        for item in footprint.graphicItems:
            if item.type == "reference":
                return item.text
        return ""

    def get_symbold_designator(self, symbol: kiutils.symbol) -> str:
        """Return symbol designator"""
        return symbol.properties[0].value

    def check_symbol(self, components: List[str], dnp: bool, dnp_field: bool = False, inbom: bool = False) -> None:
        """Check if symbol have DNP fields

        Parameters:
            components: List of designator to check
            dnp: Define if component is DNP
            dnp_field: Allow component to have a DNP field (when dnp is set to False)
        """

        scheet = kiutils.schematic.Schematic().from_file(filepath="ethernet.kicad_sch")
        component_count = len(scheet.schematicSymbols)
        components_checked = 0
        for component_id in range(0, component_count):
            symbol = scheet.schematicSymbols[component_id]
            designator = self.get_symbold_designator(symbol)
            properties = symbol.properties

            if designator in components:
                if dnp_field:
                    self.assertIsNot(get_property(properties, "DNP"), None, "Symbol have DNP property")
                else:
                    self.assertIs(get_property(properties, "DNP"), None, "Symbol have DNP property")
                if dnp:
                    self.assertEqual(symbol.dnp, True, "Symbol is DNP")
                else:
                    self.assertEqual(symbol.dnp, False, "Symbol is  not DNP")
                if inbom:
                    self.assertEqual(symbol.inBom, False, "Symbol is not in BOM")
                else:
                    self.assertEqual(symbol.inBom, True, "Symbol in BOM")
                components_checked += 1

        self.assertEqual(components_checked, len(components), "Not all components checked, internal test error")

    def check_footprint(self, components: List[str], dnp: bool) -> None:
        """Check if footprints have `Exclude from position files` and `Exclude from bill of material` fields valid

        Parameters:
            component: List of designators to check
            dnp: Define if component is DNP
        """
        pcb = kiutils.board.Board().from_file(filepath="cm4-baseboard.kicad_pcb")
        footprints = pcb.footprints
        footprints_count = len(footprints)
        footprints_checked = 0
        for footprint_id in range(0, footprints_count):
            footprint = footprints[footprint_id]
            attributes = footprint.attributes
            designator = self.get_footprint_designator(footprint)
            if designator in components:
                if dnp:
                    self.assertEqual(attributes.excludeFromPosFiles, True, f"{designator} Not excluded from pos files")
                    self.assertEqual(attributes.excludeFromBom, True, f"{designator} Not excluded from BOM")
                    footprints_checked += 1
                else:
                    self.assertEqual(attributes.excludeFromPosFiles, False, f"{designator} Excluded from POS")
                    self.assertEqual(attributes.excludeFromBom, False, f"{designator} Excluded from BOM")
                    footprints_checked += 1
        self.assertEqual(footprints_checked, len(components), "Not all components checked internal test error")

    def check_paste_layer(self, footprint: kiutils.footprint) -> int:
        """Return number of pads when solder paste layer exist"""
        paste_pads = 0
        for pad in footprint.pads:
            if ("F.Paste" in pad.layers) or ("B.Paste" in pad.layers):
                paste_pads += 1
        return paste_pads

    def check_paste(self, components: List[str], dnp: bool) -> None:
        """Check if solder paste is placed at footprint pad

        Parameters:
            components: List of designators to check
            dnp: Define if component is DNP
        """
        pcb = kiutils.board.Board().from_file(filepath="cm4-baseboard.kicad_pcb")
        footprints = pcb.footprints
        footprint_count = len(footprints)
        footprints_checked = 0
        for footprint_id in range(0, footprint_count):
            footprint = footprints[footprint_id]
            designator = self.get_footprint_designator(footprint)
            if designator in components:
                paste_counter = self.check_paste_layer(footprint)
                if dnp:
                    self.assertEqual(paste_counter, 0, "Paste wasnt removed from all pads")
                else:
                    self.assertEqual(paste_counter, len(footprint.pads))
                footprints_checked += 1
        self.assertEqual(len(components), footprints_checked, "Not all components checked internal test error")

    def test_list_malformed(self) -> None:
        """Test output for -l command (list malformed)"""
        self.reset_repo()
        with self.assertLogs(level=logging.WARNING) as log:
            self.run_test_command(["-l"])
        self.assertIn(
            "There are 3 schematic components that have their DNP properties malformed:",
            log.output[0][18:96],
        )

    def test_clean_symbol(self) -> None:
        "Test if dnp symbols have `Exlude from position file` and `Do not populate` fields set correctly"
        self.reset_repo()
        self.check_symbol(["R407", "R409"], False, True, False)
        self.check_symbol(["R410"], True, False, False)
        self.check_symbol(["C404", "C405"], False)
        self.run_test_command([])
        self.check_symbol(["R407", "R409", "R410"], True, True, True)
        self.check_symbol(["C404", "C405"], False)

    def test_clean_footprint(self) -> None:
        "Test if DNP footprints have `Exclude from pos files` and `Exclude from bill of material` fields set correctly"
        self.reset_repo()
        self.check_footprint(["R407"], False)
        self.check_footprint(["R406"], False)
        self.run_test_command([])
        self.check_footprint(["R407"], True)
        self.check_footprint(["R406"], False)

    def test_remove_restore_paste(self) -> None:
        "Test if solder pasted was removed and restored from DNP components"
        self.reset_repo()
        self.check_paste(["R407"], False)
        self.check_paste(["C404"], False)
        self.run_test_command(["--remove-dnp-paste"])
        self.check_paste(["R407"], True)
        self.check_paste(["C404"], False)
        self.run_test_command(["--restore-dnp-paste"])
        self.check_paste(["R407"], False)
        self.check_paste(["C404"], False)

        self.reset_repo()
        self.check_paste(["R407"], False)
        self.run_test_command(["-rp"])
        self.check_paste(["R407"], True)
        self.run_test_command(["-sp"])
        self.check_paste(["R407"], False)

    def reset_repo(self) -> None:
        """Reset repository to HEAD"""
        kicad_project_repo = Repo(TARGET)
        kicad_project_repo.git.reset("--hard", "HEAD")
        kicad_project_repo.git.clean("-fd")

        # Plant few imperfections in project files
        sch = kiutils.schematic.Schematic().from_file(TARGET / "ethernet.kicad_sch")
        for s in sch.schematicSymbols:
            ref = self.get_symbold_designator(s)
            if ref == "R407" or ref == "R409":
                set_property(s, "DNP", "DNP")
                s.dnp = False
                s.inBom = True
            if ref == "R410":
                s.properties = [p for p in s.properties if p.key != "DNP"]  # remove DNP field
                s.dnp = True
                s.inBom = True
        sch.to_file()

        pcb = kiutils.board.Board().from_file(TARGET / "cm4-baseboard.kicad_pcb")
        for fp in pcb.footprints:
            ref = self.get_footprint_designator(fp)
            if ref == "R407":
                fp.attributes.excludeFromBom = False
                fp.attributes.excludeFromPosFiles = False
        pcb.to_file()

    def setUp(self) -> None:
        self.reset_repo()
        os.chdir(TARGET)
