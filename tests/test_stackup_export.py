import unittest
import os

from kmake_test_common import KmakeTestCase


class StackupExportTest(KmakeTestCase, unittest.TestCase):

    def __init__(self, method_name: str = "runTest") -> None:
        KmakeTestCase.__init__(
            self, KmakeTestCase.TEST_DIR / "test-designs" / "jetson-orin-baseboard", "stackup-export"
        )
        unittest.TestCase.__init__(self, method_name)

    def test_stackup_export(self) -> None:
        self.run_test_command([])
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/stackup.json"))

    def test_stackup_export_output(self) -> None:
        self.run_test_command(["-o", "fab/test_output_filename.json"])
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/test_output_filename.json"))

    def test_stackup_legacy(self) -> None:
        self.run_test_command(["--legacy-csv"])
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/stackup.csv"))

    def test_stackup_legacy_output(self) -> None:
        self.run_test_command(["--legacy-csv", "-o", "fab/test_output_filename.csv"])
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/test_output_filename.csv"))


if __name__ == "__main__":
    unittest.main()
