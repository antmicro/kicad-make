import unittest
import kmake
import os
import logging
from unittest.mock import patch
from pathlib import Path
from git import Repo
from io import StringIO

from common.kicad_project import KicadProject

TEST_COMMAND = "get-ignore"
TEST_DIR = Path(__file__).parent.resolve()
# path to test design repository
JETSON_ORIN_BASEBOARD_DIR = TEST_DIR / "test-designs" / "jetson-orin-baseboard"

class ExampleTest(unittest.TestCase):
    # patch stdout and stderr to capture output
    # if your test doesn't check for output, you can remove this
    @patch('sys.stdout', new_callable=StringIO)
    @patch('sys.stderr', new_callable=StringIO)
    def test_example(self, stdout: StringIO, stderr: StringIO) -> None:
        # make sure test design repository doesn't have any changes
        kicad_project_repo = Repo(JETSON_ORIN_BASEBOARD_DIR)
        kicad_project_repo.git.reset("--hard", "HEAD")
        kicad_project_repo.git.clean("-fd")
        # change current directory to the test design repository
        # as kmake expects to be run from the root of the test repository
        os.chdir(JETSON_ORIN_BASEBOARD_DIR)
        # parse arguments for the test command
        self.args = kmake.parse_arguments([TEST_COMMAND])
        self.kpro = KicadProject()
        # you can check for messages in the logs using with self.assertLogs
        with self.assertLogs(level=logging.WARNING) as log:
            # run the test command
            self.args.func(self.kpro, self.args)
        self.assertIn(".gitignore already exists in", log.output[0])
        # you can check for non-zero exit codes using with self.assertRaises
        #with self.assertRaises(SystemExit) as cm:
        #    # run the test command
        #    self.args.func(self.kpro, self.args)
        #self.assertEqual(cm.exception.code, 1)

        # you can check for messages in stdout and stderr using .getvalue()
        self.assertEqual(len(stdout.getvalue()), 0)
        self.assertEqual(len(stderr.getvalue()), 0)
        # more information can be found in the unittest documentation (https://docs.python.org/3/library/unittest.html)

if __name__ == '__main__':
    unittest.main()
