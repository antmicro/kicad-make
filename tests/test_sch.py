import unittest

from kmake_test_common import KmakeTestCase


class SchTest(KmakeTestCase, unittest.TestCase):
    def __init__(self, method_name: str = "runTest") -> None:
        KmakeTestCase.__init__(self, "sch")
        unittest.TestCase.__init__(self, method_name)

    def test_sch(self) -> None:
        self.run_test_command([])

        sch_pdf = self.kpro.doc_dir / (self.kpro.project_name + "-schematic.pdf")
        self.assertTrue(self.kpro.doc_dir.exists())
        self.assertTrue(sch_pdf.exists())

    def test_sch_theme(self) -> None:
        self.run_test_command(["-t", "Kicad Classic"])

        sch_pdf = self.kpro.doc_dir / (self.kpro.project_name + "-schematic.pdf")
        self.assertTrue(self.kpro.doc_dir.exists())
        self.assertTrue(sch_pdf.exists())
        # TODO: check if the theme is applied to the pdf
        # TODO: kicad doesn't fail if the theme is not found, instead it uses the default theme
        # maybe we should add this check in `sch` command


if __name__ == "__main__":
    unittest.main()
