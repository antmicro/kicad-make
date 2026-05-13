import unittest

from kmake_test_common import KicadProject, KmakeTestCase


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
        for file in self.kpro.fs_path.rglob("*"):
            file = file.relative_to(self.kpro.fs_path)
            if str(file).startswith("."):
                continue
            self.assertTrue(self.old_kpro.project_name not in str(file))
            if file.is_file() and file in whitelist:
                with open(file, "r", encoding="latin-1") as f:
                    content = f.read()
                    self.assertTrue(self.old_kpro.project_name not in content)
        KmakeTestCase.tearDown(self)


if __name__ == "__main__":
    unittest.main()
