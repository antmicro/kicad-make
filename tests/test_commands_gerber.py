import unittest

from kmake_test_common import KmakeTestCase


class GerberTest(KmakeTestCase, unittest.TestCase):

    def __init__(self, method_name: str = "runTest") -> None:
        KmakeTestCase.__init__(self, KmakeTestCase.TEST_DIR / "test-designs" / "jetson-orin-baseboard", "gerber")
        unittest.TestCase.__init__(self, method_name)

    def test_gerber(self) -> None:
        self.run_test_command([])
        gerber_count = len(list(self.target_dir.joinpath("fab").glob("jetson-orin-baseboard-*.gbr")))
        self.assertEqual(gerber_count, 39)


if __name__ == "__main__":
    unittest.main()
