import unittest
import os

from kmake_test_common import KmakeTestCase


class StepTest(KmakeTestCase, unittest.TestCase):

    def __init__(self, method_name: str = "runTest") -> None:
        KmakeTestCase.__init__(self, "step")
        unittest.TestCase.__init__(self, method_name)

    def test_step(self) -> None:
        self.run_test_command([])
        self.assertTrue(os.path.exists(f"{self.kpro.step_model3d_dir}/{self.kpro.name}.step"))


if __name__ == "__main__":
    unittest.main()
