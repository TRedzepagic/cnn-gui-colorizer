import inspect
import os
import sys
import tempfile
import unittest
from unittest import mock

import model_utils


class ModelUtilsTests(unittest.TestCase):
    def testCaffemodelUrlsUseGoogleDrive(self):
        self.assertIn(
            model_utils.MODEL_CAFFEMODEL_GOOGLE_DRIVE_FILE_ID,
            model_utils.MODEL_MANUAL_DOWNLOAD_URL,
        )
        self.assertIn(
            model_utils.MODEL_CAFFEMODEL_GOOGLE_DRIVE_FILE_ID,
            model_utils.MODEL_DOWNLOAD_URLS["caffemodel"],
        )

    def testGetModelDirectoryUsesEnvironmentOverride(self):
        with mock.patch.dict(os.environ, {"COLORIZER_MODEL_DIR": "~/colorizer-models"}):
            expectedPath = os.path.abspath(os.path.expanduser("~/colorizer-models"))
            self.assertEqual(model_utils.getModelDirectory(), expectedPath)

    def testGetMissingModelAssetsOnlyReportsMissingFiles(self):
        with tempfile.TemporaryDirectory() as tempDir:
            assetPaths = model_utils.getModelAssetPaths(tempDir)
            with open(assetPaths["prototxt"], "wb"):
                pass
            with open(assetPaths["points"], "wb"):
                pass

            self.assertEqual(model_utils.getMissingModelAssets(tempDir), ["caffemodel"])
            self.assertEqual(
                model_utils.getMissingModelFileNames(tempDir),
                ["colorization_release_v2.caffemodel"],
            )

    def testDownloadMissingModelAssetsOnlyFetchesMissingFiles(self):
        with tempfile.TemporaryDirectory() as tempDir:
            assetPaths = model_utils.getModelAssetPaths(tempDir)
            with open(assetPaths["prototxt"], "wb"):
                pass

            with mock.patch("model_utils.downloadFile") as downloadFileMock:
                downloadedAssets = model_utils.downloadMissingModelAssets(modelDir=tempDir, quiet=True)

        self.assertEqual(downloadedAssets, ["caffemodel", "points"])
        self.assertEqual(downloadFileMock.call_count, 2)
        downloadFileMock.assert_any_call(
            model_utils.MODEL_DOWNLOAD_URLS["caffemodel"],
            assetPaths["caffemodel"],
            quiet=True,
        )
        downloadFileMock.assert_any_call(
            model_utils.MODEL_DOWNLOAD_URLS["points"],
            assetPaths["points"],
            quiet=True,
        )

    def testDownloadFileUsesGdownForGoogleDriveUrls(self):
        fakeGdown = mock.Mock()
        fakeGdown.download.return_value = "/tmp/colorization_release_v2.caffemodel"
        fakeGdown.download.__signature__ = inspect.Signature(
            parameters=[
                inspect.Parameter("url", inspect.Parameter.POSITIONAL_OR_KEYWORD),
                inspect.Parameter("output", inspect.Parameter.POSITIONAL_OR_KEYWORD),
                inspect.Parameter("quiet", inspect.Parameter.POSITIONAL_OR_KEYWORD),
                inspect.Parameter("fuzzy", inspect.Parameter.POSITIONAL_OR_KEYWORD),
            ]
        )

        with tempfile.TemporaryDirectory() as tempDir:
            destinationPath = os.path.join(tempDir, "colorization_release_v2.caffemodel")
            with open(destinationPath, "wb") as downloadedFile:
                downloadedFile.write(b"\x00" * model_utils.MODEL_MIN_VALID_CAFFEMODEL_BYTES)

            with mock.patch.dict(sys.modules, {"gdown": fakeGdown}):
                model_utils.downloadFile(
                    model_utils.MODEL_DOWNLOAD_URLS["caffemodel"],
                    destinationPath,
                    quiet=True,
                )

        fakeGdown.download.assert_called_once_with(
            url=model_utils.MODEL_DOWNLOAD_URLS["caffemodel"],
            output=destinationPath,
            quiet=True,
            fuzzy=True,
        )

    def testDownloadFileUsesLegacyGdownSignatureWithoutFuzzy(self):
        fakeGdown = mock.Mock()
        fakeGdown.download = mock.Mock(return_value="/tmp/colorization_release_v2.caffemodel")
        fakeGdown.download.__signature__ = inspect.Signature(
            parameters=[
                inspect.Parameter("url", inspect.Parameter.POSITIONAL_OR_KEYWORD),
                inspect.Parameter("output", inspect.Parameter.POSITIONAL_OR_KEYWORD),
                inspect.Parameter("quiet", inspect.Parameter.POSITIONAL_OR_KEYWORD),
            ]
        )

        with tempfile.TemporaryDirectory() as tempDir:
            destinationPath = os.path.join(tempDir, "colorization_release_v2.caffemodel")
            with open(destinationPath, "wb") as downloadedFile:
                downloadedFile.write(b"\x00" * model_utils.MODEL_MIN_VALID_CAFFEMODEL_BYTES)

            with mock.patch.dict(sys.modules, {"gdown": fakeGdown}):
                model_utils.downloadFile(
                    model_utils.MODEL_DOWNLOAD_URLS["caffemodel"],
                    destinationPath,
                    quiet=True,
                )

        fakeGdown.download.assert_called_once_with(
            url=model_utils.MODEL_DOWNLOAD_URLS["caffemodel"],
            output=destinationPath,
            quiet=True,
        )

    def testValidateDownloadedCaffemodelRejectsHtmlInterstitial(self):
        with tempfile.TemporaryDirectory() as tempDir:
            destinationPath = os.path.join(tempDir, "colorization_release_v2.caffemodel")
            with open(destinationPath, "wb") as downloadedFile:
                downloadedFile.write(b"<!DOCTYPE html><html><body>Drive warning</body></html>")

            with self.assertRaisesRegex(RuntimeError, "Downloaded HTML"):
                model_utils._validateDownloadedCaffemodel(destinationPath)


if __name__ == "__main__":
    unittest.main()
