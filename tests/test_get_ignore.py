import unittest
from kmake_test_common import KmakeTestCase


class GitIgnoreTest(KmakeTestCase, unittest.TestCase):

    def __init__(self, method_name: str = "runTest") -> None:
        KmakeTestCase.__init__(self, "get-ignore")
        unittest.TestCase.__init__(self, method_name)

    def test(self) -> None:
        (self.target_dir / ".gitignore").unlink(missing_ok=True)
        self.run_test_command([])
        self.assertTrue((self.target_dir / ".gitignore").exists())


if __name__ == "__main__":
    unittest.main()
