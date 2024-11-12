import kmake
from pathlib import Path
import git
from typing import List
import os
from common.kicad_project import KicadProject
from common.kmake_helper import run_kicad_cli
import shutil
import tempfile


class KmakeTestCase:
    target_dir: Path
    test_cmd: str
    kpro: KicadProject
    TEST_DIR = Path(__file__).parent.resolve()

    def __init__(self, test_cmd: str):
        self.target_dir = KmakeTestCase.TEST_DIR / "test_project"
        self.test_cmd = test_cmd
        self.ref_dir = KmakeTestCase.TEST_DIR / "reference-outputs" / test_cmd

    def run_test_command(self, arguments: List[str]) -> None:
        "Template for running commands"
        args = kmake.parse_arguments([self.test_cmd] + arguments)
        args.func(self.kpro, args)

    def setUp(self) -> None:
        """Copy test project to temp dir & prepare KiCad project and git repo"""
        temp_dir = Path(tempfile.mkdtemp())
        shutil.copytree(
            self.target_dir,
            temp_dir,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("assets", "lib", "img", "doc", ".git"),
        )
        self.target_dir = temp_dir

        # change current directory to the test design repository
        # as kmake expects to be run from the root of the test repository
        os.chdir(self.target_dir)

        self.project_repo = git.Repo.init(None)
        self.project_repo.git.add(all=True)
        self.project_repo.index.commit("initial")

        self.kpro = KicadProject()
        self.migrate_project()

    def tearDown(self) -> None:
        """Check if Kicad files are not corrupted & remove tmp directory after test"""
        self.check_if_pcb_sch_opens()
        if os.path.exists(self.target_dir):
            shutil.rmtree(self.target_dir)

    def check_if_pcb_sch_opens(self) -> None:
        "Run kicad-cli to check if KiCad files are not corrupted"
        os.chdir(self.target_dir)
        run_kicad_cli(["pcb", "export", "gerbers", self.kpro.pcb_file], False)
        run_kicad_cli(["sch", "export", "pdf", self.kpro.sch_root], False)

    def migrate_project(self) -> None:
        """Ensure that test project version is the same as KiCad"""
        try:
            from pcbnew import LoadBoard, SaveBoard  # type:ignore  # noqa: F403

            for file in Path.cwd().glob("*.kicad_pcb"):
                # Migrate pcb
                pcb = LoadBoard(file)  # type: ignore  # noqa: F405
                SaveBoard(file, pcb)  # type: ignore  # noqa: F405
        except ModuleNotFoundError:
            print("`pcbnew` module not found! Skipping project migration.")
        self.project_repo.git.add(all=True)
        self.project_repo.index.commit("Migrate project to tested KiCad version")
