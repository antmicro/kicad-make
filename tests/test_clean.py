import unittest
import kmake
import os
import logging
from pathlib import Path
from git import Repo

from common.kicad_project import KicadProject

TEST_COMMAND = "clean"
TEST_DIR = Path(__file__).parent.resolve()
# path to test design repository
JETSON_ORIN_BASEBOARD_DIR = TEST_DIR / "test-designs" / "jetson-orin-baseboard"

class ExampleTest(unittest.TestCase):
    def test_clean(self) -> None:
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
        with self.assertLogs(level=logging.INFO) as log:
            # run the test command
            self.args.func(self.kpro, self.args)
        self.assertIn("Cleanup complete", log.output[-1])

        self.assertFalse(kicad_project_repo.is_dirty(untracked_files=True))

    def test_clean2(self) -> None:
        # make sure test design repository doesn't have any changes
        kicad_project_repo = Repo(JETSON_ORIN_BASEBOARD_DIR)
        kicad_project_repo.git.reset("--hard", "HEAD")
        kicad_project_repo.git.clean("-fd")
        # change current directory to the test design repository
        # as kmake expects to be run from the root of the test repository
        os.chdir(JETSON_ORIN_BASEBOARD_DIR)
        # create files to clean
        from commands.clean import extensions_to_remove, files_to_remove, startswith_to_remove, endswith_to_remove
        for ext in extensions_to_remove:
            open(JETSON_ORIN_BASEBOARD_DIR / f"test{ext}", "w").close()
        for file in files_to_remove:
            open(JETSON_ORIN_BASEBOARD_DIR / file, "w").close()

        for start in startswith_to_remove:
            open(JETSON_ORIN_BASEBOARD_DIR / f"{start}test", "w").close()
        for end in endswith_to_remove:
            open(JETSON_ORIN_BASEBOARD_DIR / f"test{end}", "w").close()

        # parse arguments for the test command
        self.args = kmake.parse_arguments([TEST_COMMAND])
        self.kpro = KicadProject()
        # you can check for messages in the logs using with self.assertLogs
        with self.assertLogs(level=logging.INFO) as log:
            # run the test command
            self.args.func(self.kpro, self.args)
        self.assertIn("Cleanup complete", log.output[-1])

        self.assertFalse(kicad_project_repo.is_dirty(untracked_files=True))

if __name__ == '__main__':
    unittest.main()
