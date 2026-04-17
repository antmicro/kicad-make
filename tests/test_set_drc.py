import unittest
import logging
import json

from unittest.mock import patch
from io import StringIO
from kmake_test_common import KmakeTestCase


class SetDrcTest(KmakeTestCase, unittest.TestCase):
    def __init__(self, method_name: str = "runTest") -> None:
        KmakeTestCase.__init__(self, "set-drc", shared_dir=str(self.TEST_DIR / "share-dir"))
        unittest.TestCase.__init__(self, method_name)

    @patch("sys.stdout", new_callable=StringIO)
    def test_list_set_drc(self, stdout: StringIO) -> None:
        self.run_test_command([])

        self.assertTrue("7E" in stdout.getvalue())

    @patch("sys.stdout", new_callable=StringIO)
    def test_set_drc_empty_argument(self, stdout: StringIO) -> None:
        self.run_test_command(["-s"])

        # when '-s' is empty, we should display available DRCs
        self.assertTrue("7E" in stdout.getvalue())

    def test_set_drc_not_existing_template_argument(self) -> None:
        # we should exit with error
        with self.assertRaises(SystemExit) as cm:
            # error message is logged
            with self.assertLogs(level=logging.ERROR) as log:
                self.run_test_command(["-s", "doesnt_exist"])
            self.assertIn("Selected doesnt_exist DRC template doesn't exist", log.output[0])

        self.assertEqual(cm.exception.code, 1)

    def test_set_drc_correct_template_argument(self) -> None:
        # first make sure project rules and template rules are different
        with open(self.kpro.kicad_pro_path, "r") as f:
            project_file_content = json.load(f)
        with open(self.TEST_DIR / "share-dir" / "pcb-drc-templates" / "7E.kicad_pro", "r") as f:
            template_file_content = json.load(f)
        project_rules = project_file_content["board"]["design_settings"]["rules"]
        template_rules = template_file_content["board"]["design_settings"]["rules"]
        self.assertNotEqual(project_rules, template_rules)

        with self.assertLogs(level=logging.INFO) as log:
            self.run_test_command(["-s", "7E"])
        self.assertIn("Rules updated successfully", log.output[0])

        # now make sure project rules and template rules are the same
        with open(self.kpro.kicad_pro_path, "r") as f:
            project_file_content = json.load(f)
        with open(self.TEST_DIR / "share-dir" / "pcb-drc-templates" / "7E.kicad_pro", "r") as f:
            template_file_content = json.load(f)
        project_rules = project_file_content["board"]["design_settings"]["rules"]
        template_rules = template_file_content["board"]["design_settings"]["rules"]

        self.assertEqual(project_rules, template_rules)


if __name__ == "__main__":
    unittest.main()
