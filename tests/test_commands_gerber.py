import unittest
from typing import List
from pathlib import Path

from kmake_test_common import KmakeTestCase

GERBER_FLASH_APERTURE = "D03*"


class GerberTest(KmakeTestCase, unittest.TestCase):

    def __init__(self, method_name: str = "runTest") -> None:
        KmakeTestCase.__init__(self, "gerber")
        unittest.TestCase.__init__(self, method_name)

    def count_pads(self, file_paths: List[Path]) -> int:
        count = 0
        for file_path in file_paths:
            if file_path.exists():
                with open(file_path) as f:
                    count += sum(1 for line in f if GERBER_FLASH_APERTURE in line)
        return count

    def test_gerber(self) -> None:
        self.run_test_command([])
        gerber_count = len(list(self.target_dir.joinpath("fab").glob("test_project-*.gbr")))
        self.assertEqual(gerber_count, 43)
        gbr_dir = self.target_dir / "fab"
        paste_files = [gbr_dir / f"{self.kpro.name}-F_Paste.gbr", gbr_dir / f"{self.kpro.name}-B_Paste.gbr"]
        base_pads = self.count_pads(paste_files)
        self.assertEqual(base_pads, 303, "Different number of pads on paste layers after 'kmake gerber'")
        self.run_test_command(["--add-tht-paste"])
        with_tht_pads = self.count_pads(paste_files)
        self.assertEqual(
            with_tht_pads, 323, "Different number of pads on paste layers after 'kmake gerber --add-tht-paste'"
        )
        self.run_test_command(["--remove-dnp-paste"])
        without_dnp_pads = self.count_pads(paste_files)
        self.assertEqual(
            without_dnp_pads, 278, "Different number of pads on paste layers after 'kmake gerber --remove-dnp-paste'"
        )

        # `kmake gerber` should not modify original files
        self.run_test_command([])
        base_pads = self.count_pads(paste_files)
        self.assertEqual(base_pads, 303, "Different number of pads on paste layers after 'kmake gerber'")


if __name__ == "__main__":
    unittest.main()
