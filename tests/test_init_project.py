import unittest

import kiutils
import kmake
import os
import tempfile
import logging
from pathlib import Path
from git import List
from common.kicad_project import KicadProject
from typing import Tuple
from kiutils.items.common import TitleBlock
from datetime import date
import shutil

TEST_COMMAND = "init-project"
TARGET: Path


class InitProjectTest(unittest.TestCase):
    def setUp(self) -> None:
        """Create tmp directory before test"""
        global TARGET
        TARGET = Path(tempfile.mkdtemp())
        os.chdir(TARGET)

    def tearDown(self) -> None:
        """Remove tmp directory after test"""
        if os.path.exists(TARGET):
            shutil.rmtree(TARGET)

    def get_title_blocks(self, project_name: str = "project") -> Tuple[TitleBlock, TitleBlock]:
        """Returns TitleBlock from schematic and PCB"""
        schematic = kiutils.schematic.Schematic().from_file(filepath=f"{project_name}.{self.kpro.sch_ext}")
        sch_title_block = schematic.titleBlock
        board = kiutils.board.Board().from_file(filepath=f"{project_name}.{self.kpro.pcb_ext}")
        brd_title_block = board.titleBlock
        return sch_title_block, brd_title_block

    def get_papers(self) -> Tuple[TitleBlock, TitleBlock]:
        """Returns page settings from schematic and PCB"""
        schematic = kiutils.schematic.Schematic().from_file(filepath="project.kicad_sch")
        sch_paper = schematic.paper
        board = kiutils.board.Board().from_file(filepath="project.kicad_pcb")
        brd_paper = board.paper
        return sch_paper, brd_paper

    def set_title_blocks(self) -> None:
        """Set date and revision to schematic and PCB, date is set to 01.01.1970, revision to 1.2.3"""
        schematic = kiutils.schematic.Schematic().from_file(filepath="project.kicad_sch")
        sch_title_block = schematic.titleBlock
        sch_title_block.revision = "1.2.3"
        sch_title_block.date = "01.01.1970"
        schematic.titleBlock = sch_title_block
        schematic.to_file(filepath="project.kicad_sch")

        board = kiutils.board.Board().from_file(filepath="project.kicad_pcb")
        brd_title_block = board.titleBlock
        brd_title_block.revision = "1.2.3"
        brd_title_block.date = "01.01.1970"
        board.titleBlock = sch_title_block
        board.to_file(filepath="project.kicad_pcb")

    def template_command(self, arguments: List[str]) -> None:
        "Template for running commands"
        self.args = kmake.parse_arguments([TEST_COMMAND] + arguments)
        self.kpro = KicadProject()
        self.args.func(self.kpro, self.args)

    def test_init_files(self) -> None:
        """Check if all files were generated"""
        self.template_command(["-t", "project"])

        self.assertTrue(os.path.isfile(TARGET / Path("project.kicad_pro")))
        self.assertTrue(os.path.isfile(TARGET / Path("project.kicad_sch")))
        self.assertTrue(os.path.isfile(TARGET / Path("project.kicad_pcb")))

    def test_init_revision(self) -> None:
        """Check if revision was set to 1.0.0"""
        self.template_command(["-t", "project"])
        sch_title_block, brd_title_block = self.get_title_blocks()

        self.assertEqual(sch_title_block.revision, "1.0.0")
        self.assertEqual(brd_title_block.revision, "1.0.0")

    def test_date(self) -> None:
        """Check if date was set to current date"""
        self.template_command(["-t", "project"])
        sch_title_block, brd_title_block = self.get_title_blocks()
        timestamp = date.today().strftime("%d.%m.%Y")

        self.assertEqual(sch_title_block.date, timestamp)
        self.assertEqual(brd_title_block.date, timestamp)

    def test_init_title(self) -> None:
        """Test if title is set in schematic and PCB"""
        self.template_command(["-t", "project"])
        sch_title_block, brd_title_block = self.get_title_blocks(project_name="project")

        self.assertEqual(sch_title_block.title, "project")
        self.assertEqual(brd_title_block.title, "project")

    def test_init_true(self) -> None:
        """Test if title is set in schematic and PCB when title is set to True"""
        self.template_command(["-t", "True"])
        sch_title_block, brd_title_block = self.get_title_blocks(project_name="True")

        self.assertEqual(sch_title_block.title, "True")
        self.assertEqual(brd_title_block.title, "True")

    def test_init_none(self) -> None:
        """Test if title is set in schematic and PCB when title is set to None"""
        self.template_command(["-t", "None"])
        sch_title_block, brd_title_block = self.get_title_blocks(project_name="None")

        self.assertEqual(sch_title_block.title, "None")
        self.assertEqual(brd_title_block.title, "None")

    def test_init_special_chars(self) -> None:
        """Test if title is set in schematic and PCB, when special characters are used"""
        self.template_command(["-t", "!@#$%_"])
        sch_title_block, brd_title_block = self.get_title_blocks(project_name="!@#$%_")

        self.assertEqual(sch_title_block.title, "!@#$%_")
        self.assertEqual(brd_title_block.title, "!@#$%_")

    def test_init_title_long(self) -> None:
        """Same as test_init_title but long arguments are used"""

        self.template_command(["--title", "project"])
        sch_title_block, brd_title_block = self.get_title_blocks()

        self.assertEqual(sch_title_block.title, "project")
        self.assertEqual(brd_title_block.title, "project")

    def test_company(self) -> None:
        """Test if company was set correctly"""

        self.template_command(["-t", "project", "-c", "antmicro"])
        sch_title_block, brd_title_block = self.get_title_blocks()

        self.assertEqual(sch_title_block.company, "antmicro")
        self.assertEqual(brd_title_block.company, "antmicro")

    def test_company_true(self) -> None:
        """Test if company title was set correctly, when title is set to True"""
        self.template_command(["-t", "project", "-c", "True"])
        sch_title_block, brd_title_block = self.get_title_blocks()

        self.assertEqual(sch_title_block.company, "True")
        self.assertEqual(brd_title_block.company, "True")

    def test_company_none(self) -> None:
        """Test if company title was set correctly, when title is set to True"""
        self.template_command(["-t", "project", "-c", "None"])
        sch_title_block, brd_title_block = self.get_title_blocks()

        self.assertEqual(sch_title_block.company, "None")
        self.assertEqual(brd_title_block.company, "None")

    def test_company_special_chars(self) -> None:
        """Test if company title can handle special chars"""
        self.template_command(["-t", "project", "-c", "!_@#$%"])
        sch_title_block, brd_title_block = self.get_title_blocks()

        self.assertEqual(sch_title_block.company, "!_@#$%")
        self.assertEqual(brd_title_block.company, "!_@#$%")

    def test_company_long(self) -> None:
        self.template_command(["-t", "project", "-c", "antmicro"])
        sch_title_block, brd_title_block = self.get_title_blocks()

        self.assertEqual(sch_title_block.company, "antmicro")
        self.assertEqual(brd_title_block.company, "antmicro")

    def test_size(self) -> None:
        "Test if size is set correctly"

        self.template_command(["-t", "project", "-s", "A0"])
        sch_paper, brd_file = self.get_papers()

        self.assertEqual(sch_paper.paperSize, "A0")
        self.assertEqual(brd_file.paperSize, "A0")

    def test_size_incorrect_size(self) -> None:
        """Test init-project behavior when size is set unexisting format"""

        with self.assertRaises(SystemExit) as status:
            with self.assertLogs(level=logging.ERROR) as log:
                self.template_command(["-t", "project", "-s", "Z3"])
        self.assertEqual(status.exception.code, -1)
        self.assertIn("Selected page is not range", log.output[1])

    def test_size_long(self) -> None:
        "Test if size is set correctly"

        self.template_command(["-t", "project", "--size", "A0"])
        sch_paper, brd_file = self.get_papers()

        self.assertEqual(sch_paper.paperSize, "A0")
        self.assertEqual(brd_file.paperSize, "A0")

    def test_reset(self) -> None:
        """Check if kmake init-project block unattended changes"""
        self.template_command(["-t", "project", "-c", "company", "-s", "A5"])

        with self.assertRaises(SystemExit) as status:
            with self.assertLogs(level=logging.WARNING) as log:
                self.template_command(["-t", "project 2", "-c", "company 2", "-s", "A0"])
        self.assertEqual(status.exception.code, -1)
        self.assertEqual("Project title mismatch, project 2 is not the same as project", log.output[0][30:])

    def test_reload(self) -> None:
        """Test if only company, title and size fields are set with -r flag"""
        self.template_command(["-t", "project", "-c", "company", "-s", "A5", "-r"])
        self.set_title_blocks()
        sch_title_block, brd_title_block = self.get_title_blocks()
        sch_paper, brd_paper = self.get_papers()

        self.assertEqual(sch_title_block.title, "project")
        self.assertEqual(brd_title_block.title, "project")
        self.assertEqual(sch_title_block.company, "company")
        self.assertEqual(brd_title_block.company, "company")
        self.assertEqual(sch_paper.paperSize, "A5")
        self.assertEqual(brd_paper.paperSize, "A5")
        self.assertEqual(sch_title_block.date, "01.01.1970")
        self.assertEqual(brd_title_block.date, "01.01.1970")
        self.assertEqual(sch_title_block.revision, "1.2.3")
        self.assertEqual(brd_title_block.revision, "1.2.3")

    def test_reload_long(self) -> None:
        """Test if only company, title and size fields are set with -r flag"""
        self.template_command(["-t", "project", "-c", "company", "-s", "A5", "--reload"])
        self.set_title_blocks()
        sch_title_block, brd_title_block = self.get_title_blocks()
        sch_paper, brd_paper = self.get_papers()

        self.assertEqual(sch_title_block.title, "project")
        self.assertEqual(brd_title_block.title, "project")
        self.assertEqual(sch_title_block.company, "company")
        self.assertEqual(brd_title_block.company, "company")
        self.assertEqual(sch_paper.paperSize, "A5")
        self.assertEqual(brd_paper.paperSize, "A5")
        self.assertEqual(sch_title_block.date, "01.01.1970")
        self.assertEqual(brd_title_block.date, "01.01.1970")
        self.assertEqual(sch_title_block.revision, "1.2.3")
        self.assertEqual(brd_title_block.revision, "1.2.3")

    def test_force_title(self) -> None:
        """Test if title can be changed with force"""
        self.template_command(["-t", "project"])
        sch_title_block, brd_title_block = self.get_title_blocks()

        self.assertEqual(sch_title_block.title, "project")
        self.assertEqual(brd_title_block.title, "project")

        self.template_command(["-t", "device", "--force-title"])
        sch_title_block, brd_title_block = self.get_title_blocks()

        self.assertEqual(sch_title_block.title, "device")
        self.assertEqual(brd_title_block.title, "device")

    def test_unattended_title_change(self) -> None:
        """Check if title can't be changed accidentally"""
        self.template_command(["-t", "project"])

        with self.assertRaises(SystemExit) as status:
            with self.assertLogs(level=logging.WARNING) as log:
                self.template_command(["-t", "device"])

        self.assertEqual(status.exception.code, -1)
        self.assertIn("Project title mismatch, device is not the same as project", log.output[0])
