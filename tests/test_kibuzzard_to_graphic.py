import unittest
from kiutils.board import Board
import kmake
import os
from pathlib import Path
from typing import List
import tempfile
import shutil

from common.kicad_project import KicadProject

TEST_COMMAND = "kibuzzard-to-graphic"
TEST_DIR = Path(__file__).parent.resolve()
TARGET: Path
KICAD_PROJECT_DIR = TEST_DIR / "test-designs" / "project-with-kicad-lib"


class KibuzzardToGraphicTest(unittest.TestCase):
    def setUp(self) -> None:
        """Prepare test files"""
        global TARGET
        TARGET = Path(tempfile.mkdtemp())
        shutil.copytree(KICAD_PROJECT_DIR, TARGET, dirs_exist_ok=True)
        os.chdir(TARGET)

    def tearDown(self) -> None:
        """Remove tmp directory after test"""
        if os.path.exists(TARGET):
            shutil.rmtree(TARGET)

    def run_test_command(self, arguments: List[str]) -> None:
        """Execute tested command"""
        self.args = kmake.parse_arguments([TEST_COMMAND] + arguments)
        self.kpro = KicadProject()

        self.args.func(self.kpro, self.args)

    def test_kibuzzard(self) -> None:
        target_pcb_path = TARGET / "project-with-kicad-lib.kicad_pcb"
        reference_pcb_path = (
            TEST_DIR
            / "reference-outputs"
            / "project-with-kicad-lib"
            / "kibuzzard-to-graphic"
            / "project-with-kicad-lib.kicad_pcb"
        )

        target_pcb = Board().from_file(filepath=str(target_pcb_path))
        target_footprints_entry_names = [footprint.entryName for footprint in target_pcb.footprints]
        target_graphic_items = [graphic_item for graphic_item in target_pcb.graphicItems]

        self.assertIn("kibuzzard-66D96414", target_footprints_entry_names)

        # TODO: Check if kibuzzard not exists as graphic in target

        self.run_test_command([])

        target_pcb = Board().from_file(filepath=str(target_pcb_path))
        target_footprints_entry_names = sorted([footprint.entryName for footprint in target_pcb.footprints])
        target_graphic_items = [graphic_item for graphic_item in target_pcb.graphicItems]
        reference_pcb = Board().from_file(filepath=str(reference_pcb_path))
        reference_footprints_entry_names = sorted([footprint.entryName for footprint in reference_pcb.footprints])
        reference_graphic_items = [graphic_item for graphic_item in reference_pcb.graphicItems]

        self.assertListEqual(reference_footprints_entry_names, target_footprints_entry_names)
        self.assertListEqual(reference_graphic_items, target_graphic_items)
        self.assertNotIn("kibuzzard-66D96414", target_footprints_entry_names)
