import os
import shutil
import tempfile
import importlib
import inspect
from urllib import request

from runtime_support import resolveResourcePath


MODEL_FILE_NAMES = {
    "prototxt": "colorization_deploy_v2.prototxt",
    "caffemodel": "colorization_release_v2.caffemodel",
    "points": "pts_in_hull.npy",
}
MODEL_CAFFEMODEL_GOOGLE_DRIVE_FILE_ID = "1HWgaWDZjR1pSWqUBg0TzmbiVjq5WtnIi"
MODEL_MANUAL_DOWNLOAD_URL = (
    "https://drive.google.com/file/d/{0}/view?usp=drive_link".format(
        MODEL_CAFFEMODEL_GOOGLE_DRIVE_FILE_ID
    )
)

MODEL_DOWNLOAD_URLS = {
    "prototxt": (
        "https://raw.githubusercontent.com/richzhang/colorization/"
        "a1642d6ac6fc80fe08885edba34c166da09465f6/colorization/models/"
        "colorization_deploy_v2.prototxt"
    ),
    "caffemodel": (
        "https://drive.google.com/uc?export=download&id={0}".format(
            MODEL_CAFFEMODEL_GOOGLE_DRIVE_FILE_ID
        )
    ),
    "points": (
        "https://raw.githubusercontent.com/richzhang/colorization/"
        "a1642d6ac6fc80fe08885edba34c166da09465f6/colorization/resources/"
        "pts_in_hull.npy"
    ),
}
MODEL_MIN_VALID_CAFFEMODEL_BYTES = 1024 * 1024


def getModelDirectory():
    configuredModelDir = os.environ.get("COLORIZER_MODEL_DIR")
    if configuredModelDir:
        return os.path.abspath(os.path.expanduser(configuredModelDir))

    return resolveResourcePath("model")


def getModelAssetPaths(modelDir=None):
    modelDir = modelDir or getModelDirectory()
    return {
        assetName: os.path.join(modelDir, fileName)
        for assetName, fileName in MODEL_FILE_NAMES.items()
    }


def getMissingModelAssets(modelDir=None):
    return [
        assetName
        for assetName, assetPath in getModelAssetPaths(modelDir).items()
        if not os.path.exists(assetPath)
    ]


def getMissingModelFileNames(modelDir=None):
    return [
        MODEL_FILE_NAMES[assetName]
        for assetName in getMissingModelAssets(modelDir)
    ]


def hasModelAssets(modelDir=None):
    return not getMissingModelAssets(modelDir)


def _downloadFileFromUrl(url, destinationPath, quiet=False):
    os.makedirs(os.path.dirname(destinationPath), exist_ok=True)
    downloadDir = os.path.dirname(destinationPath)
    descriptor, temporaryPath = tempfile.mkstemp(
        prefix=".download-",
        suffix=".part",
        dir=downloadDir,
    )
    os.close(descriptor)

    try:
        with request.urlopen(url) as response, open(temporaryPath, "wb") as destinationFile:
            shutil.copyfileobj(response, destinationFile)
        os.replace(temporaryPath, destinationPath)
        if not quiet:
            print("Downloaded {0}".format(os.path.basename(destinationPath)))
    except Exception:
        if os.path.exists(temporaryPath):
            os.remove(temporaryPath)
        raise


def _getGdownModule():
    try:
        return importlib.import_module("gdown")
    except ImportError as exc:
        raise RuntimeError(
            "gdown is required to download the Google Drive caffemodel. "
            "Install dependencies with `pip3 install -r requirements.txt`."
        ) from exc


def _validateDownloadedCaffemodel(destinationPath):
    fileSize = os.path.getsize(destinationPath)
    if fileSize < MODEL_MIN_VALID_CAFFEMODEL_BYTES:
        with open(destinationPath, "rb") as downloadedFile:
            filePrefix = downloadedFile.read(512).lstrip()
        loweredPrefix = filePrefix.lower()
        if loweredPrefix.startswith(b"<!doctype html") or loweredPrefix.startswith(b"<html"):
            raise RuntimeError(
                "Downloaded HTML instead of the model binary from Google Drive."
            )
        raise RuntimeError(
            "Downloaded caffemodel is unexpectedly small ({0} bytes).".format(fileSize)
        )


def _downloadGoogleDriveFile(fileUrl, destinationPath, quiet=False, progressCallback=None):
    gdown = _getGdownModule()
    os.makedirs(os.path.dirname(destinationPath), exist_ok=True)

    downloadKwargs = {
        "url": fileUrl,
        "output": destinationPath,
        "quiet": quiet,
    }

    try:
        downloadSignature = inspect.signature(gdown.download)
    except (TypeError, ValueError):
        downloadSignature = None

    if downloadSignature is None or "fuzzy" in downloadSignature.parameters:
        downloadKwargs["fuzzy"] = True
    if progressCallback is not None and (
        downloadSignature is None or "progress" in downloadSignature.parameters
    ):
        downloadKwargs["progress"] = progressCallback

    downloadResult = gdown.download(**downloadKwargs)
    if not downloadResult or not os.path.exists(destinationPath):
        raise RuntimeError("gdown did not produce the expected model file.")

    _validateDownloadedCaffemodel(destinationPath)


def downloadFile(url, destinationPath, quiet=False, progressCallback=None):
    if "drive.google.com" in url:
        _downloadGoogleDriveFile(
            url,
            destinationPath,
            quiet=quiet,
            progressCallback=progressCallback,
        )
        return

    _downloadFileFromUrl(url, destinationPath, quiet=quiet)


def downloadMissingModelAssets(modelDir=None, force=False, quiet=False, progressCallback=None):
    modelDir = modelDir or getModelDirectory()
    assetPaths = getModelAssetPaths(modelDir)
    downloadedAssets = []

    for assetName, assetPath in assetPaths.items():
        if not force and os.path.exists(assetPath):
            continue

        if not quiet:
            print("Fetching {0}...".format(MODEL_FILE_NAMES[assetName]))
        assetProgressCallback = progressCallback if assetName == "caffemodel" else None
        downloadFile(
            MODEL_DOWNLOAD_URLS[assetName],
            assetPath,
            quiet=quiet,
            progressCallback=assetProgressCallback,
        )
        downloadedAssets.append(assetName)

    return downloadedAssets
