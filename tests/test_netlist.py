import unittest
import re
from kmake_test_common import KmakeTestCase
from common.kicad_project import KicadProject


class BomNetlist(KmakeTestCase, unittest.TestCase):

    def __init__(self, method_name: str = "runTest") -> None:
        KmakeTestCase.__init__(self, "netlist")
        unittest.TestCase.__init__(self, method_name)

    def test_netlists_equal(self) -> None:
        """Test if target and reference netlists are equal"""
        self.run_test_command([])

        ref = open(self.ref_dir / f"netlist-v{KicadProject().kicad_version.split('.')[0]}.net").readlines()
        tar = open(self.target_dir / "fab" / "netlist.net").readlines()

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
        count_uri = 9
        count_source = 1
        # the date occurs two times (in the netlist header and title block section)
        count_date = 2
        count_eeschema = 1
        self.assertEqual(len(lines_to_remove), count_uri + count_source + count_date + count_eeschema)

        self.assertListEqual(tar, ref)
