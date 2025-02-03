import unittest
import shutil
import os

from common.kicad_project import KicadProject
from kmake_test_common import KmakeTestCase


class WhitespaceTest(KmakeTestCase, unittest.TestCase):

    def __init__(self, method_name: str = "runTest") -> None:

        KmakeTestCase.__init__(self, "gerber")
        unittest.TestCase.__init__(self, method_name)

    def test_whitespace(self) -> None:

        temp_dir = self.target_dir.with_name("test_project (copy)")
        shutil.move(self.target_dir, temp_dir)
        self.target_dir = temp_dir
        os.chdir(self.target_dir)
        self.kpro = KicadProject()
        self.run_test_command([])
        gerber_count = len(list(self.target_dir.joinpath("fab").glob("test_project-*.gbr")))
        self.assertEqual(gerber_count, 43)


if __name__ == "__main__":
    unittest.main()
