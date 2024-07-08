import unittest
import kmake
import re
import os
from pathlib import Path
from git import Repo
from common.kicad_project import KicadProject


TEST_COMMAND = "netlist"
TEST_DIR = Path(__file__).parent.resolve()
# path to test design repository
TARGET = TEST_DIR / "test-designs" / "sdi-mipi-bridge-hw"
REF_OUTS = TEST_DIR / "reference-outputs" / "sdi-mipi-bridge" / "netlist"


class BomNetlist(unittest.TestCase):
    def setUp(self) -> None:
        """Prepare test data"""
        # make sure test design repository doesn't have any changes
        test_repo = Repo(TARGET)
        test_repo.git.reset("--hard", "HEAD")
        test_repo.git.clean("-fd")
        os.chdir(TARGET)

    def test_netlists_equal(self) -> None:
        """Test if target and reference netlists are equal"""
        self.args = kmake.parse_arguments([TEST_COMMAND])
        self.kpro = KicadProject()

        self.args.func(self.kpro, self.args)

        ref = open(REF_OUTS / f"netlist-v{self.kpro.kicad_version.split('.')[0]}.net").readlines()
        tar = open(TARGET / "fab" / "netlist.net").readlines()

        lines_to_remove = []
        uri_match = False
        source_match = False
        tool_match = False

        for line_id, line in enumerate(tar):
            if re.search(r"\(uri", line) is not None:
                lines_to_remove.append(line_id)
                uri_match = True
            if re.search(r'\(source\s"/', line):
                lines_to_remove.append(line_id)
                source_match = True
            if (
                re.search(
                    r"\(date\s",
                    line,
                )
                is not None
            ):
                lines_to_remove.append(line_id)
            if re.search(r'\(tool\s"Eeschema\s\d\.\d\.\d', line) is not None:
                lines_to_remove.append(line_id)
                tool_match = True

        counter = 0
        for line_id in sorted(lines_to_remove):
            del ref[line_id - counter]
            del tar[line_id - counter]
            counter += 1

        self.assertTrue(uri_match)
        self.assertTrue(source_match)
        self.assertTrue(tool_match)

        # Check if every element was matched:uri, source, tool version, date
        # the date occurs two times (in the netlist header and title block section)
        self.assertEqual(len(lines_to_remove), 5)

        self.assertListEqual(tar, ref)
