import unittest
import kmake
import os
from kiutils.board import Board
from typing import List
from pathlib import Path
from git import Repo

from common.kicad_project import KicadProject

TEST_COMMAND = "impedance"
TEST_DIR = Path(__file__).parent.resolve()
# path to test design repository
JETSON_ORIN_BASEBOARD_DIR = TEST_DIR / "test-designs" / "jetson-orin-baseboard"

class ImpedanceTest(unittest.TestCase):
    def setUp(self) -> None:
        # make sure test design repository doesn't have any changes
        kicad_project_repo = Repo(JETSON_ORIN_BASEBOARD_DIR)
        kicad_project_repo.git.reset("--hard", "HEAD")
        kicad_project_repo.git.clean("-fd")
        # change current directory to the test design repository
        # as kmake expects to be run from the root of the test repository
        os.chdir(JETSON_ORIN_BASEBOARD_DIR)

    def run_kmake_command(self, args: List[str]|None = None) -> None:
        command = [TEST_COMMAND]
        if args is not None:
            command.extend(args)
        self.args = kmake.parse_arguments(command)
        self.kpro = KicadProject()
        self.args.func(self.kpro, self.args)

    def test_impedence_map(self) -> None:
        self.run_kmake_command()
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/impedance_maps"))
        self.assertTrue(os.path.exists(f"{self.kpro.fab_dir}/impedance_map.kicad_pcb"))

        board = Board.from_file(f"{self.kpro.fab_dir}/impedance_map.kicad_pcb")

        self.assertEqual(len(board.traceItems), 6924)
        self.assertEqual(len(board.footprints), 0)
        self.assertEqual(len(board.zones), 0)

        for file in Path.iterdir(Path(f"{self.kpro.fab_dir}/impedance_maps")):
            self.assertTrue(file.is_file())
            self.assertTrue(file.suffix == ".gbr")
            self.assertIn("Ohm", file.name)

if __name__ == '__main__':
    unittest.main()
