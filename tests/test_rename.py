import unittest
from pathlib import Path

from kmake_test_common import KmakeTestCase
from common.kicad_project import KicadProject


class RenameTest(KmakeTestCase, unittest.TestCase):

    def __init__(self, method_name: str = "runTest") -> None:
        KmakeTestCase.__init__(self, "rename")
        unittest.TestCase.__init__(self, method_name)

    def test(self) -> None:
        self.old_kpro = self.kpro
        self.run_test_command(["new_cool_design_name"])
        self.kpro = KicadProject()

    def tearDown(self) -> None:
        whitelist = [
            ".kicad_pro",
            ".kicad_pcb",
            ".kicad_sch",
            ".kicad_mod",
            ".kicad_sym",
            ".kicad_prl",
            ".kicad_dru",
            ".md",
            ".txt",
            ".rst",
            ".json",
            ".csv",
            ".gbr",
            ".svg",
            ".xml",
            "sym-lib-table",
            "fp-lib-table",
            "fp-cache-table",
        ]
        for file in Path(self.kpro.dir).rglob("*"):
            file = file.relative_to(self.kpro.dir)
            if str(file).startswith("."):
                continue
            self.assertTrue(self.old_kpro.name not in str(file))
            if file.is_file() and file in whitelist:
                with open(file, "r", encoding="latin-1") as f:
                    content = f.read()
                    self.assertTrue(self.old_kpro.name not in content)
        super().tearDown()


if __name__ == "__main__":
    unittest.main()
