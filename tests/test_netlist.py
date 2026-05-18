import re
import unittest

from kmake_test_common import KmakeTestCase


class BomNetlist(KmakeTestCase, unittest.TestCase):
    def __init__(self, method_name: str = "runTest") -> None:
        KmakeTestCase.__init__(self, "netlist")
        unittest.TestCase.__init__(self, method_name)

    def test_netlists_equal(self) -> None:
        """Test if target and reference netlists are equal"""
        self.run_test_command([])

        ref = open(self.ref_dir / "netlist.net").readlines()
        tar = open(self.target_dir / "fab" / "netlist.net").readlines()

        lines_to_remove = []
        uri_match, source_match, tool_match, date_match = 0, 0, 0, 0
        skip_groups = 0

        for line_id, line in enumerate(tar):
            # `groups` section in netlist has no stable sort as of KiCad 10.0.3
            # ignore it entirely
            if "(groups" in line:
                skip_groups = 32
            if skip_groups:
                skip_groups -= 1
                lines_to_remove.append(line_id)

            if re.search(r"\(uri", line) is not None:
                lines_to_remove.append(line_id)
                uri_match += 1
            if re.search(r'\(source\s"/', line):
                lines_to_remove.append(line_id)
                source_match += 1
            if re.search(r"\(date\s", line) is not None:
                lines_to_remove.append(line_id)
                date_match += 1
            if re.search(r'\(tool\s"Eeschema\s\d+\.\d+\.\d+', line) is not None:
                lines_to_remove.append(line_id)
                tool_match += 1

        counter = 0
        for line_id in sorted(lines_to_remove):
            del ref[line_id - counter]
            del tar[line_id - counter]
            counter += 1

        # Check if every element was matched: uri, source, tool version, date
        self.assertEqual(uri_match, 9 if self.kpro.kicad_version_major == "9" else 10)
        self.assertEqual(source_match, 1)
        self.assertEqual(date_match, 2)  # the date occurs two times (in the netlist header and title block section)
        self.assertEqual(tool_match, 1)

        self.assertListEqual(tar, ref)
