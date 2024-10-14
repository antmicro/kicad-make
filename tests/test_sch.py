import unittest
import os

from kmake_test_common import KmakeTestCase


class SchTest(KmakeTestCase, unittest.TestCase):

    def __init__(self, method_name: str = "runTest") -> None:
        KmakeTestCase.__init__(self, KmakeTestCase.TEST_DIR / "test-designs" / "jetson-orin-baseboard", "sch")
        unittest.TestCase.__init__(self, method_name)

    def test_sch(self) -> None:
        self.run_test_command([])
        self.assertTrue(os.path.exists(self.kpro.doc_dir))
        self.assertTrue(os.path.exists(f"{self.kpro.doc_dir}/{self.kpro.name}-schematic.pdf"))

    def test_sch_theme(self) -> None:
        self.run_test_command(["-t", "Kicad Classic"])

        self.assertTrue(os.path.exists(self.kpro.doc_dir))
        self.assertTrue(os.path.exists(f"{self.kpro.doc_dir}/{self.kpro.name}-schematic.pdf"))
        # TODO: check if the theme is applied to the pdf
        # TODO: kicad doesn't fail if the theme is not found, instead it uses the default theme
        # maybe we should add this check in `sch` command


if __name__ == "__main__":
    unittest.main()
