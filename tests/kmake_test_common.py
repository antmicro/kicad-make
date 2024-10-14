import kmake
from pathlib import Path
import git
from typing import List
import os
from common.kicad_project import KicadProject
from common.kmake_helper import run_kicad_cli


class KmakeTestCase:
    target_dir: Path
    test_cmd: str
    kpro: KicadProject
    TEST_DIR = Path(__file__).parent.resolve()

    def __init__(self, target_dir: Path, test_cmd: str):
        self.target_dir = target_dir
        self.test_cmd = test_cmd

    def run_test_command(self, arguments: List[str]) -> None:
        "Template for running commands"
        args = kmake.parse_arguments([self.test_cmd] + arguments)
        args.func(self.kpro, args)

    def reset_repo(self) -> None:
        "Reset git repo to clean state (remove all uncommitted changes)"
        self.project_repo.git.reset("--hard", "HEAD")
        self.project_repo.git.clean("-fd")

    def setUp(self) -> None:
        # change current directory to the test design repository
        # as kmake expects to be run from the root of the test repository
        os.chdir(self.target_dir)
        self.project_repo = git.Repo(self.target_dir)

        # make sure test design repository doesn't have any changes
        self.reset_repo()
        self.kpro = KicadProject()

    def check_if_pcb_sch_opens(self) -> None:
        "Run kicad-cli to check if KiCad files are not corrupted"
        os.chdir(self.target_dir)
        run_kicad_cli(["pcb", "export", "gerbers", self.kpro.pcb_file], False)
        run_kicad_cli(["sch", "export", "pdf", self.kpro.sch_root], False)

    def tearDown(self) -> None:
        self.check_if_pcb_sch_opens()
        self.reset_repo()
