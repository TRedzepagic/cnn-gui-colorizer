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

    def testMacOSAppZipUsesDitto(self):
        with tempfile.TemporaryDirectory() as tempDir:
            sourceDir = os.path.join(tempDir, "cnn-colorizer.app")
            os.makedirs(sourceDir)
            archivePath = os.path.join(tempDir, "release.zip")

            with mock.patch("scripts.package_release.subprocess.run") as runMock:
                runMock.return_value.returncode = 0
                package_release.createMacOSAppZipArchive(sourceDir, archivePath)

        runMock.assert_called_once_with(
            [
                "ditto",
                "-c",
                "-k",
                "--keepParent",
                sourceDir,
                archivePath,
            ],
            check=False,
        )

    def testMainUsesDittoForMacOSAppZip(self):
        with tempfile.TemporaryDirectory() as tempDir:
            sourceDir = os.path.join(tempDir, "cnn-colorizer.app")
            os.makedirs(sourceDir)
            outputPath = os.path.join(tempDir, "cnn-colorizer-macos.zip")

            with mock.patch("scripts.package_release.createMacOSAppZipArchive") as macArchiveMock:
                with mock.patch.object(package_release.sys, "platform", "darwin"):
                    with mock.patch("sys.argv", ["package_release.py", "--source", sourceDir, "--output", outputPath]):
                        exitCode = package_release.main()

        self.assertEqual(exitCode, 0)
        macArchiveMock.assert_called_once_with(os.path.abspath(sourceDir), os.path.abspath(outputPath))


if __name__ == "__main__":
    unittest.main()
