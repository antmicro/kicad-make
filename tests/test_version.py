import unittest
from unittest.mock import patch
from io import StringIO

from kmake_test_common import KmakeTestCase


class VersionTest(KmakeTestCase, unittest.TestCase):

    def __init__(self, method_name: str = "runTest") -> None:
        KmakeTestCase.__init__(self, "version")
        unittest.TestCase.__init__(self, method_name)

    @patch("sys.stdout", new_callable=StringIO)
    def test_version(self, stdout: StringIO) -> None:
        self.run_test_command([])

        out = stdout.getvalue().splitlines()
        op = [[s.strip() for s in line.partition(":")] for line in out]

        self.assertEqual([o[0] for o in op], ["kmake", "kicad", "kiutils"])
        [o[2] for o in op[0:3] if o[2][0].isdigit()]


if __name__ == "__main__":
    unittest.main()
