import unittest
import kmake
import os
from pathlib import Path
from git import Repo

from common.kicad_project import KicadProject

COMMAND = "rename"
TEST_NAME = COMMAND

TEST_DIR = Path(__file__).parent.resolve()
JETSON_ORIN_BASEBOARD_DIR = TEST_DIR / "test-designs" / "jetson-orin-baseboard"
RESULT_DIR = TEST_DIR / "results" / TEST_NAME


class RenameTest(unittest.TestCase):
    def setUp(self) -> None:
        kicad_project_repo = Repo(JETSON_ORIN_BASEBOARD_DIR)
        kicad_project_repo.git.reset("--hard", "HEAD")
        kicad_project_repo.git.clean("-fd")
        os.chdir(JETSON_ORIN_BASEBOARD_DIR)
        self.args = kmake.parse_arguments([COMMAND, "new_cool_design_name"])
        self.kpro = KicadProject()

    def test(self) -> None:
        self.args.func(self.kpro, self.args)

    def tearDown(self) -> None:
        whitelist = [
            ".kicad_pro",
            ".kicad_pcb",
            ".kicad_sch",
            ".kicad_mod",
            ".kicad_sym",
            ".kicad_prl",
            ".kicad_dru",
            ".md",
            ".txt",
            ".rst",
            ".json",
            ".csv",
            ".gbr",
            ".svg",
            ".xml",
            "sym-lib-table",
            "fp-lib-table",
            "fp-cache-table",
        ]
        for file in Path(self.kpro.dir).rglob("*"):
            file = file.relative_to(self.kpro.dir)
            if str(file).startswith("."):
                continue
            self.assertTrue(self.kpro.name not in str(file))
            if file.is_file() and file in whitelist:
                with open(file, "r", encoding="latin-1") as f:
                    content = f.read()
                    self.assertTrue(self.kpro.name not in content)


if __name__ == "__main__":
    unittest.main()
