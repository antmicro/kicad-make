import unittest
import logging
from pathlib import Path
from typing import List
from kmake_test_common import KmakeTestCase


REF_OUTS = KmakeTestCase.TEST_DIR / "reference-outputs" / "jetson-orin-baseboard" / "bom"


class BomTest(KmakeTestCase, unittest.TestCase):

    def __init__(self, method_name: str = "runTest") -> None:
        KmakeTestCase.__init__(self, KmakeTestCase.TEST_DIR / "test-designs" / "jetson-orin-baseboard", "bom")
        unittest.TestCase.__init__(self, method_name)

    def template_test(self, args: List[str], reference: Path, out_path: Path, fails: bool) -> None:
        if fails:
            with self.assertLogs(level=logging.WARNING), self.assertRaises(SystemExit):
                self.run_test_command(args)
        else:
            self.run_test_command(args)

            def norm(file: Path) -> List[str]:
                return sorted([",".join([cell.replace(' "', '"') for cell in line.split(",")]) for line in open(file)])

            self.assertListEqual(norm(reference), norm(out_path))

    def test_output_file(self) -> None:
        self.template_test(
            ["--output", "bom.csv"],
            REF_OUTS / "BOM-populated.csv",
            self.target_dir / "bom.csv",
            False,
        )

    def test_default_fields(self) -> None:
        self.template_test(
            [],
            REF_OUTS / "BOM-populated.csv",
            self.target_dir / "doc" / "jetson-orin-baseboard-BOM-populated.csv",
            False,
        )

    def test_populated(self) -> None:
        self.template_test(
            ["--fields", "Reference", "Quantity", "Value", "Footprint", "Manufacturer", "MPN"],
            REF_OUTS / "BOM-populated.csv",
            self.target_dir / "doc" / "jetson-orin-baseboard-BOM-populated.csv",
            False,
        )

    def test_all(self) -> None:
        self.template_test(
            ["--all", "--fields", "Reference", "Quantity", "Value", "Footprint", "Manufacturer", "MPN"],
            REF_OUTS / "BOM-ALL.csv",
            self.target_dir / "doc" / "jetson-orin-baseboard-BOM-ALL.csv",
            False,
        )

    def test_dnp(self) -> None:
        self.template_test(
            ["--dnp", "--fields", "Reference", "Quantity", "Value", "Footprint", "Manufacturer", "MPN"],
            REF_OUTS / "BOM-DNP.csv",
            self.target_dir / "doc" / "jetson-orin-baseboard-BOM-DNP.csv",
            False,
        )

    def test_no_ignore(self) -> None:
        self.template_test(
            ["--all", "--no-ignore", "--fields", "Reference", "Quantity", "Value", "Footprint", "Manufacturer", "MPN"],
            REF_OUTS / "BOM-ALL-no-ignore.csv",
            self.target_dir / "doc" / "jetson-orin-baseboard-BOM-ALL.csv",
            False,
        )

    def test_reference_not_grouped(self) -> None:
        self.template_test(
            [
                "--all",
                "--group-references",
                "--fields",
                "Reference Designators",
                "Manufacturer",
                "Manufacturer Part Number",
                "DNP",
                "Description",
            ],
            REF_OUTS / "BOM-ALL-ReferenceNotGrouped.csv",
            self.target_dir / "doc" / "jetson-orin-baseboard-BOM-ALL-ReferenceNotGrouped.csv",
            False,
        )

    def test_invalid_field(self) -> None:
        self.template_test(
            ["--fields", "wrongField"],
            REF_OUTS / "BOM-ALL-no-ignore.csv",
            self.target_dir / "doc" / "jetson-orin-baseboard-BOM-ALL.csv",
            True,
        )


if __name__ == "__main__":
    unittest.main()
