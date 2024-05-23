import unittest
import kmake
import os
from pathlib import Path
from git import Repo

from common.kicad_project import KicadProject

TEST_COMMAND = "step"
TEST_DIR = Path(__file__).parent.resolve()
# path to test design repository
JETSON_ORIN_BASEBOARD_DIR = TEST_DIR / "test-designs" / "jetson-orin-baseboard"

class StepTest(unittest.TestCase):
    def test_step(self) -> None:
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
        self.args.func(self.kpro, self.args)

        self.assertTrue(os.path.exists(f"{self.kpro.step_model3d_dir}/{self.kpro.name}.step"))

if __name__ == '__main__':
    unittest.main()

