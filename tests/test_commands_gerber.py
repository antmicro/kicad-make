import unittest
from pathlib import Path

from kmake_test_common import KmakeTestCase

RESULT_DIR = KmakeTestCase.TEST_DIR / "results" / "gerber"


class GerberTest(KmakeTestCase, unittest.TestCase):

    def __init__(self, method_name: str = "runTest") -> None:
        KmakeTestCase.__init__(self, KmakeTestCase.TEST_DIR / "test-designs" / "jetson-orin-baseboard", "gerber")
        unittest.TestCase.__init__(self, method_name)

    def test_gerber(self) -> None:
        self.run_test_command([])

        changed_files = [item.a_path for item in self.project_repo.index.diff(None)]
        RESULT_DIR.mkdir(exist_ok=True, parents=True)
        for file in changed_files:
            Path(file).rename(Path(RESULT_DIR) / Path(file).name)
        for file in self.project_repo.untracked_files:
            Path(file).rename(Path(RESULT_DIR) / Path(file).name)

    def test_gerber_noedge(self) -> None:
        self.run_test_command(["--noedge"])

        changed_files = [item.a_path for item in self.project_repo.index.diff(None)]
        RESULT_DIR.mkdir(exist_ok=True, parents=True)
        for file in changed_files:
            Path(file).rename(Path(RESULT_DIR) / Path(file).name)
        for file in self.project_repo.untracked_files:
            Path(file).rename(Path(RESULT_DIR) / Path(file).name)


if __name__ == "__main__":
    unittest.main()
