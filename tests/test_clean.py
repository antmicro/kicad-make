import unittest
import logging
from kmake_test_common import KmakeTestCase


class ExampleTest(KmakeTestCase, unittest.TestCase):

    def __init__(self, method_name: str = "runTest") -> None:
        KmakeTestCase.__init__(self, "clean")
        unittest.TestCase.__init__(self, method_name)

    def test_clean(self) -> None:
        # you can check for messages in the logs using with self.assertLogs
        with self.assertLogs(level=logging.INFO) as log:
            self.run_test_command([])
        self.assertIn("Cleanup complete", log.output[-1])

        self.assertFalse(self.project_repo.is_dirty(untracked_files=True))

    def test_clean2(self) -> None:
        from commands.clean import extensions_to_remove, files_to_remove, startswith_to_remove, endswith_to_remove

        for ext in extensions_to_remove:
            open(self.target_dir / f"test{ext}", "w").close()
        for file in files_to_remove:
            open(self.target_dir / file, "w").close()

        for start in startswith_to_remove:
            open(self.target_dir / f"{start}test", "w").close()
        for end in endswith_to_remove:
            open(self.target_dir / f"test{end}", "w").close()

        # you can check for messages in the logs using with self.assertLogs
        with self.assertLogs(level=logging.INFO) as log:
            self.run_test_command([])
        self.assertIn("Cleanup complete", log.output[-1])

        self.assertFalse(self.project_repo.is_dirty(untracked_files=True))


if __name__ == "__main__":
    unittest.main()
