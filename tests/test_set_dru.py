import logging
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from kmake_test_common import KmakeTestCase

from commands.set_drc import read_dru_file


class SetDruTest(KmakeTestCase, unittest.TestCase):
    def __init__(self, method_name: str = "runTest") -> None:
        KmakeTestCase.__init__(self, "set-dru", shared_dir=str(self.TEST_DIR / "share-dir"))
        unittest.TestCase.__init__(self, method_name)

    @patch("sys.stdout", new_callable=StringIO)
    def test_list_set_dru(self, stdout: StringIO) -> None:
        self.run_test_command([])

        self.assertTrue("K410T-devboard" in stdout.getvalue())

    @patch("sys.stdout", new_callable=StringIO)
    def test_set_dru_empty_argument(self, stdout: StringIO) -> None:
        self.run_test_command(["-u"])

        # when '-u' is empty, we should display available DRUs
        self.assertTrue("K410T-devboard" in stdout.getvalue())

    def test_set_dru_not_existing_template_argument(self) -> None:
        # we should exit with error
        with self.assertRaises(SystemExit) as cm:
            # error message is logged
            with self.assertLogs(level=logging.ERROR) as log:
                self.run_test_command(["-u", "doesnt_exist"])
            self.assertIn("Selected doesnt_exist DRU template doesn't exist", log.output[0])

        self.assertEqual(cm.exception.code, 1)

    def test_set_dru_correct_template_argument(self) -> None:
        with self.assertLogs(level=logging.INFO) as log:
            self.run_test_command(["-u", "K410T-devboard"])
        self.assertIn("Rules updated successfully", log.output[0])

        dru_template = read_dru_file(
            Path(self.TEST_DIR / "share-dir" / "pcb-drc-templates" / "K410T-devboard.kicad_dru")
        )
        dru_target = read_dru_file(self.kpro.dru_file)
        for rule in dru_template.rules:
            self.assertIn(rule, dru_target.rules)


if __name__ == "__main__":
    unittest.main()
