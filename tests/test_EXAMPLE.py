import unittest
import logging
from unittest.mock import patch
from io import StringIO
from kmake_test_common import KmakeTestCase


class ExampleTest(KmakeTestCase, unittest.TestCase):

    # Make sure to pass design_dir & tested_cmd to super class constructor
    def __init__(self, method_name: str = "runTest") -> None:
        KmakeTestCase.__init__(
            self,
            # tested kmake command
            "get-ignore",
        )
        unittest.TestCase.__init__(self, method_name)

    # patch stdout and stderr to capture output
    # if your test doesn't check for output, you can remove this
    @patch("sys.stdout", new_callable=StringIO)
    @patch("sys.stderr", new_callable=StringIO)
    def test_example(self, stdout: StringIO, stderr: StringIO) -> None:
        # you can check for messages in the logs using with self.assertLogs
        with self.assertLogs(level=logging.WARNING) as log:
            # run the test command
            self.run_test_command([])
        self.assertIn(".gitignore already exists in", log.output[0])
        # you can check for non-zero exit codes using with self.assertRaises
        # with self.assertRaises(SystemExit) as cm:
        #    # run the test command
        #    self.run_test_command([])
        # self.assertEqual(cm.exception.code, 1)

        # you can check for messages in stdout and stderr using .getvalue()
        self.assertEqual(len(stdout.getvalue()), 0)
        self.assertEqual(len(stderr.getvalue()), 0)
        # more information can be found in the unittest documentation (https://docs.python.org/3/library/unittest.html)


if __name__ == "__main__":
    unittest.main()
