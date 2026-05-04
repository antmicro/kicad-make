import unittest
from typing import List
from kmake_test_common import KmakeTestCase


class LogosTest(KmakeTestCase, unittest.TestCase):
    def __init__(self, method_name: str = "runTest") -> None:
        KmakeTestCase.__init__(self, "logos")
        unittest.TestCase.__init__(self, method_name)

    def inner(self, args: List[str], reflogo: str) -> None:
        self.run_test_command(args)
        changed_files = [item.a_path for item in self.project_repo.index.diff(None)]
        logo = "\n".join([line.strip().strip('"') for line in reflogo.splitlines()])
        for file in changed_files:
            if not file:
                continue
            with open(file, "r") as f:
                file_contents = "\n".join([line.strip().strip('"') for line in f.readlines()])
                self.assertTrue(logo in file_contents)

        self.assertTrue(len(self.project_repo.untracked_files) == 0)

    def test_logos_custom_path(self) -> None:
        with open(self.ref_dir / "test_logo", "r") as f:
            logo_snippet = f.read()
        self.inner(["test_logo", "-p", str(self.ref_dir)], logo_snippet)


if __name__ == "__main__":
    unittest.main()
