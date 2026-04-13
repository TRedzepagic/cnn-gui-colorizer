import unittest
from unittest import mock

from scripts import build_binary


class BuildBinaryTests(unittest.TestCase):
    def testMainUsesSkipModelDownloadFlagName(self):
        with mock.patch("scripts.build_binary.getMissingModelAssets", return_value=["caffemodel"]):
            with mock.patch("sys.stderr"):
                with mock.patch("sys.argv", ["build_binary.py", "--skip-model-download"]):
                    exitCode = build_binary.main()

        self.assertEqual(exitCode, 1)


if __name__ == "__main__":
    unittest.main()
