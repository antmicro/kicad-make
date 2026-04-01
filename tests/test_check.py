import unittest
import os
import json
from kmake_test_common import KmakeTestCase


class CheckTest(KmakeTestCase, unittest.TestCase):
    # Make sure to pass design_dir & tested_cmd to super class constructor
    def __init__(self, method_name: str = "runTest") -> None:
        KmakeTestCase.__init__(self, "check")
        unittest.TestCase.__init__(self, method_name)

    def _mask_metadata(self, file_content: dict) -> dict:
        """
        Remove last number of KiCad version from report json file
        """
        file_content["kicad_version"] = "8.0.0"
        file_content["date"] = ""
        return file_content

    def _read_jsons(self) -> tuple[dict, dict]:
        """
        Read json files
        """
        target_erc = self.target_dir / "doc" / "test_project_erc.json"

        target_drc = self.target_dir / "doc" / "test_project_drc.json"

        self.assertTrue(os.path.exists(target_erc), target_erc)

        self.assertTrue(os.path.exists(target_drc), target_drc)

        with open(target_erc, "r") as file_target:
            target_erc_json = self._mask_metadata(json.load(file_target))

        with open(target_drc, "r") as file_target:
            target_drc_json = self._mask_metadata(json.load(file_target))

        return target_erc_json, target_drc_json

    def _erc_types(self, file_content: dict) -> list[str]:
        return [violation["type"] for sheet in file_content["sheets"] for violation in sheet["violations"]]

    def _drc_types(self, file_content: dict) -> list[str]:
        return [violation["type"] for violation in file_content["violations"]]

    def test_all_report(self) -> None:
        with self.assertRaises(SystemExit) as exit_code:
            self.run_test_command(["both", "--all"])
            self.assertEqual(exit_code, 1)

        target_erc = self.target_dir / "doc" / "test_project_erc.report"
        target_drc = self.target_dir / "doc" / "test_project_drc.report"

        self.assertTrue(os.path.exists(target_erc), target_erc)

        self.assertTrue(os.path.exists(target_drc), target_drc)

        with open(target_erc, "r") as file_target:
            target_erc_content = file_target.read()

        with open(target_drc, "r") as file_target:
            target_drc_content = file_target.read()

        self.assertIn("[undefined_netclass]:", target_erc_content)
        self.assertIn("[no_connect_dangling]:", target_erc_content)
        self.assertIn("[lib_symbol_mismatch]:", target_erc_content)
        self.assertIn("[power_pin_not_driven]:", target_erc_content)
        self.assertIn("[multiple_net_names]:", target_erc_content)
        self.assertIn("[pin_not_driven]:", target_erc_content)

        self.assertIn("[solder_mask_bridge]:", target_drc_content)
        self.assertIn("[generic_error]:", target_drc_content)
        self.assertIn("[copper_edge_clearance]:", target_drc_content)
        self.assertIn("[silk_overlap]:", target_drc_content)
        self.assertIn("[lib_footprint_mismatch]:", target_drc_content)
        self.assertIn("[courtyards_overlap]:", target_drc_content)

    def test_reports_path_logged(self) -> None:
        with self.assertLogs("commands.check", level="INFO") as captured_logs:
            with self.assertRaises(SystemExit):
                self.run_test_command(["both", "--all"])

        logs = "\n".join(captured_logs.output)
        self.assertIn("At least one error exists in design", logs)
        self.assertIn(str(self.target_dir / "doc" / "test_project_erc.report"), logs)
        self.assertIn(str(self.target_dir / "doc" / "test_project_drc.report"), logs)

    def test_all(self) -> None:
        with self.assertRaises(SystemExit) as exit_code:
            self.run_test_command(["both", "--all", "--format", "json"])
            self.assertEqual(exit_code, 1)

        target_erc_json, target_drc_json = self._read_jsons()
        erc_types = self._erc_types(target_erc_json)
        drc_types = self._drc_types(target_drc_json)

        self.assertIn("undefined_netclass", erc_types)
        self.assertIn("no_connect_dangling", erc_types)
        self.assertIn("lib_symbol_mismatch", erc_types)
        self.assertIn("power_pin_not_driven", erc_types)
        self.assertIn("multiple_net_names", erc_types)
        self.assertIn("pin_not_driven", erc_types)

        self.assertIn("solder_mask_bridge", drc_types)
        self.assertIn("generic_error", drc_types)
        self.assertIn("copper_edge_clearance", drc_types)
        self.assertIn("silk_overlap", drc_types)
        self.assertIn("lib_footprint_mismatch", drc_types)
        self.assertIn("courtyards_overlap", drc_types)

    def test_errors(self) -> None:
        with self.assertRaises(SystemExit) as exit_code:
            self.run_test_command(["both", "--errors", "--format", "json"])
            self.assertEqual(exit_code, 1)

        target_erc_json, target_drc_json = self._read_jsons()
        erc_types = self._erc_types(target_erc_json)

        self.assertIn("undefined_netclass", erc_types)
        self.assertIn("power_pin_not_driven", erc_types)
        self.assertIn("pin_not_driven", erc_types)

        for violation in target_drc_json["violations"]:
            self.assertIn(violation["severity"], ["error"])

        drc_types = self._drc_types(target_drc_json)
        self.assertIn("solder_mask_bridge", drc_types)
        self.assertIn("shorting_items", drc_types)
        self.assertIn("zones_intersect", drc_types)

    def test_warnings(self) -> None:
        with self.assertRaises(SystemExit) as exit_code:
            self.run_test_command(["both", "--warnings", "--format", "json"])
            self.assertEqual(exit_code, 1)

        target_erc_json, target_drc_json = self._read_jsons()
        erc_types = self._erc_types(target_erc_json)

        self.assertIn("lib_symbol_mismatch", erc_types)
        self.assertIn("multiple_net_names", erc_types)

        for violation in target_drc_json["violations"]:
            self.assertIn(violation["severity"], ["warning"])

        drc_types = self._drc_types(target_drc_json)
        self.assertIn("lib_footprint_mismatch", drc_types)
        self.assertIn("silk_overlap", drc_types)
        self.assertIn("track_dangling", drc_types)

    def test_exclusions(self) -> None:
        with self.assertRaises(SystemExit) as exit_code:
            self.run_test_command(["both", "--exclusions", "--format", "json"])
            self.assertEqual(exit_code, 1)

        target_erc_json, target_drc_json = self._read_jsons()
        erc_types = self._erc_types(target_erc_json)

        self.assertIn("lib_symbol_mismatch", erc_types)

        for violation in target_drc_json["violations"]:
            self.assertIn(violation["severity"], ["error", "warning"])

        drc_types = self._drc_types(target_drc_json)
        self.assertIn("courtyards_overlap", drc_types)
        self.assertIn("clearance", drc_types)
        self.assertIn("lib_footprint_mismatch", drc_types)
        self.assertIn("via_dangling", drc_types)

    def test_units_mm(self) -> None:
        with self.assertRaises(SystemExit) as exit_code:
            self.run_test_command(["both", "--units", "mm", "--format", "json"])
            self.assertEqual(exit_code, 1)

        target_erc_json, target_drc_json = self._read_jsons()

        self.assertEqual(target_erc_json["coordinate_units"], "mm")
        self.assertEqual(target_drc_json["coordinate_units"], "mm")

    def test_units_inch(self) -> None:
        with self.assertRaises(SystemExit) as exit_code:
            self.run_test_command(["both", "--units", "in", "--format", "json"])
            self.assertEqual(exit_code, 1)

        target_erc_json, target_drc_json = self._read_jsons()
        self.assertEqual(target_erc_json["coordinate_units"], "in")
        self.assertEqual(target_drc_json["coordinate_units"], "in")

    def test_units_mils(self) -> None:
        with self.assertRaises(SystemExit) as exit_code:
            self.run_test_command(["both", "--units", "mils", "--format", "json"])
            self.assertEqual(exit_code, 1)

        target_erc_json, target_drc_json = self._read_jsons()

        self.assertEqual(target_erc_json["coordinate_units"], "mils")
        self.assertEqual(target_drc_json["coordinate_units"], "mils")

    def test_erc_only_report(self) -> None:
        with self.assertRaises(SystemExit) as exit_code:
            self.run_test_command(["erc"])
            self.assertEqual(exit_code, 1)

        target_erc = self.target_dir / "doc" / "test_project_erc.report"
        target_drc = self.target_dir / "doc" / "test_project_drc.report"

        self.assertTrue(os.path.exists(target_erc), target_erc)
        self.assertFalse(os.path.exists(target_drc), target_drc)

    def test_erc_only_json(self) -> None:
        with self.assertRaises(SystemExit) as exit_code:
            self.run_test_command(["erc", "--format", "json"])
            self.assertEqual(exit_code, 1)

        target_erc = self.target_dir / "doc" / "test_project_erc.json"
        target_drc = self.target_dir / "doc" / "test_project_drc.json"

        self.assertTrue(os.path.exists(target_erc), target_erc)
        self.assertFalse(os.path.exists(target_drc), target_drc)

    def test_drc_only_report(self) -> None:
        with self.assertRaises(SystemExit) as exit_code:
            self.run_test_command(["drc"])
            self.assertEqual(exit_code, 1)

        target_erc = self.target_dir / "doc" / "test_project_erc.report"
        target_drc = self.target_dir / "doc" / "test_project_drc.report"

        self.assertFalse(os.path.exists(target_erc), target_erc)
        self.assertTrue(os.path.exists(target_drc), target_drc)

    def test_drc_only_json(self) -> None:
        with self.assertRaises(SystemExit) as exit_code:
            self.run_test_command(["drc", "--format", "json"])
            self.assertEqual(exit_code, 1)

        target_erc = self.target_dir / "doc" / "test_project_erc.json"
        target_drc = self.target_dir / "doc" / "test_project_drc.json"

        self.assertFalse(os.path.exists(target_erc), target_erc)
        self.assertTrue(os.path.exists(target_drc), target_drc)


if __name__ == "__main__":
    unittest.main()
