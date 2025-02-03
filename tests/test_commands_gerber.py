import unittest

from kmake_test_common import KmakeTestCase


class GerberTest(KmakeTestCase, unittest.TestCase):

    def __init__(self, method_name: str = "runTest") -> None:
        KmakeTestCase.__init__(self, "gerber")
        unittest.TestCase.__init__(self, method_name)

    def test_gerber(self) -> None:
        self.run_test_command([])
        gerber_count = len(list(self.target_dir.joinpath("fab").glob("test_project-*.gbr")))
        self.assertEqual(gerber_count, 43)


if __name__ == "__main__":
    unittest.main()
