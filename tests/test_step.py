import unittest
import os
from pathlib import Path

from kmake_test_common import KmakeTestCase

TEST_COMMAND = "step"
TEST_DIR = Path(__file__).parent.resolve()
# path to test design repository
JETSON_ORIN_BASEBOARD_DIR = TEST_DIR / "test-designs" / "jetson-orin-baseboard"


class StepTest(KmakeTestCase, unittest.TestCase):

    def __init__(self, method_name: str = "runTest") -> None:
        KmakeTestCase.__init__(self, KmakeTestCase.TEST_DIR / "test-designs" / "jetson-orin-baseboard", "step")
        unittest.TestCase.__init__(self, method_name)

    def test_step(self) -> None:
        self.run_test_command([])
        self.assertTrue(os.path.exists(f"{self.kpro.step_model3d_dir}/{self.kpro.name}.step"))


if __name__ == "__main__":
    unittest.main()
