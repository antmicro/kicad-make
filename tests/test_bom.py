import unittest
import kmake
import os
import logging
from pathlib import Path
from git import Repo
from typing import List

from common.kicad_project import KicadProject

TEST_COMMAND = "bom"
TEST_DIR = Path(__file__).parent.resolve()
# path to test design repository
TARGET = TEST_DIR / "test-designs" / "jetson-orin-baseboard"
REF_OUTS = TEST_DIR / "reference-outputs" / "jetson-orin-baseboard" / "bom"


class BomTest(unittest.TestCase):
    def template_test(self, args: List[str], refrence: Path, out_path: Path, fails: bool) -> None:
        self.args = kmake.parse_arguments([TEST_COMMAND] + args)
        self.kpro = KicadProject()

        if fails:
            with self.assertLogs(level=logging.WARNING), self.assertRaises(SystemExit):
                self.args.func(self.kpro, self.args)
        else:
            self.args.func(self.kpro, self.args)

        self.assertListEqual(sorted(list(open(refrence))), sorted(list(open(out_path))))

    def test_populated(self) -> None:
        self.template_test(
            [], REF_OUTS / "BOM-populated.csv", TARGET / "doc" / "jetson-orin-baseboard-BOM-populated.csv", False
        )

    def test_all(self) -> None:
        self.template_test(
            ["--all"], REF_OUTS / "BOM-ALL.csv", TARGET / "doc" / "jetson-orin-baseboard-BOM-ALL.csv", False
        )

    def test_dnp(self) -> None:
        self.template_test(
            ["--dnp"], REF_OUTS / "BOM-DNP.csv", TARGET / "doc" / "jetson-orin-baseboard-BOM-DNP.csv", False
        )

    def test_no_ignore(self) -> None:
        self.template_test(
            ["--all", "--no-ignore"],
            REF_OUTS / "BOM-ALL-no-ignore.csv",
            TARGET / "doc" / "jetson-orin-baseboard-BOM-ALL.csv",
            False,
        )

    def test_circuithub(self) -> None:
        self.template_test(
            ["--all", "--format", "CircuitHub"],
            REF_OUTS / "BOM-ALL-CircuitHub.csv",
            TARGET / "doc" / "jetson-orin-baseboard-BOM-ALL-CircuitHub.csv",
            False,
        )

    def setUp(self) -> None:
        # make sure test design repository doesn't have any changes
        kicad_project_repo = Repo(TARGET)
        kicad_project_repo.git.reset("--hard", "HEAD")
        kicad_project_repo.git.clean("-fd")
        # change current directory to the test design repository
        # as kmake expects to be run from the root of the test repository
        os.chdir(TARGET)


if __name__ == "__main__":
    unittest.main()
