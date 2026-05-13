import os
import shutil
import tempfile
from pathlib import Path
from typing import List

import git
from askiff.board import Board
from common.kicad_project import KicadProject as _KicadProject
from common.kmake_helper import run_kicad_cli

import kmake


class KicadProject(_KicadProject):
    def __init__(self, **kwargs) -> None:  # type: ignore
        # compat layer with old KiCadProject
        _KicadProject.__init__(self, **kwargs)
        self.pcb_file = (
            self.pcb_root.fs_path if self.pcb_root else Path.cwd() / ((self.project_name or "unknown") + Board.fs_ext)
        )
        self.dru_file = next(self.fs_path.glob("*.kicad_dru"), "")


class KmakeTestCase:
    target_dir: Path
    test_cmd: str
    kpro: KicadProject
    shared_dir: str
    TEST_DIR = Path(__file__).parent.resolve()

    def __init__(self, test_cmd: str, shared_dir: str = ""):
        self.target_dir = KmakeTestCase.TEST_DIR / "test_project"
        self.test_cmd = test_cmd
        self.ref_dir = KmakeTestCase.TEST_DIR / "reference-outputs" / test_cmd
        self.shared_dir = shared_dir

    def run_kmake_command(self, arguments: List[str]) -> None:
        "Template for running kmake commands"
        args = kmake.parse_arguments(arguments)  # type: ignore
        pro = KicadProject(local_share_path=self.shared_dir)
        args.func(pro, args)

    def run_test_command(self, arguments: List[str]) -> None:
        "Template for running tested command"
        self.run_kmake_command([self.test_cmd] + arguments)

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

        self.kpro = KicadProject(local_share_path=self.shared_dir)

    def tearDown(self) -> None:
        """Check if Kicad files are not corrupted & remove tmp directory after test"""
        self.check_if_pcb_sch_opens()
        if self.target_dir.exists():
            shutil.rmtree(self.target_dir)

    def check_if_pcb_sch_opens(self) -> None:
        "Run kicad-cli to check if KiCad files are not corrupted"
        os.chdir(self.target_dir)
        run_kicad_cli(["pcb", "export", "gerbers", self.kpro.pcb_file], False)
        run_kicad_cli(["sch", "export", "pdf", self.kpro.sch_root.fs_path], False)
