import os
import tempfile
import unittest
from unittest import mock

from scripts import package_release


class PackageReleaseTests(unittest.TestCase):
    def testCreateZipArchiveWritesDirectoryContents(self):
        with tempfile.TemporaryDirectory() as tempDir:
            sourceDir = os.path.join(tempDir, "dist", "cnn-colorizer")
            os.makedirs(sourceDir)
            sampleFile = os.path.join(sourceDir, "sample.txt")
            with open(sampleFile, "w", encoding="utf-8") as outputFile:
                outputFile.write("hello")

            archivePath = os.path.join(tempDir, "release.zip")
            package_release.createZipArchive(sourceDir, archivePath)

            self.assertTrue(os.path.exists(archivePath))

    def testMainUsesZipArchiveForZipOutputs(self):
        with tempfile.TemporaryDirectory() as tempDir:
            sourceDir = os.path.join(tempDir, "cnn-colorizer")
            os.makedirs(sourceDir)
            outputPath = os.path.join(tempDir, "cnn-colorizer-linux.zip")

            with mock.patch("scripts.package_release.createZipArchive") as zipArchiveMock:
                with mock.patch("sys.argv", ["package_release.py", "--source", sourceDir, "--output", outputPath]):
                    exitCode = package_release.main()

        self.assertEqual(exitCode, 0)
        zipArchiveMock.assert_called_once_with(os.path.abspath(sourceDir), os.path.abspath(outputPath))


if __name__ == "__main__":
    unittest.main()
