#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from model_utils import downloadMissingModelAssets, getMissingModelAssets, MODEL_FILE_NAMES


def parseArgs():
    parser = argparse.ArgumentParser(
        description="Build the Colorizer desktop binary with PyInstaller.",
    )
    parser.add_argument(
        "--skip-model-download",
        action="store_true",
        help="Fail instead of downloading the model assets when they are missing.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Pass --clean to PyInstaller.",
    )
    return parser.parse_args()


def main():
    args = parseArgs()
    if sys.platform == "darwin":
        print(
            "macOS packaged builds are disabled. Run the app from source on macOS.",
            file=sys.stderr,
        )
        return 1

    missingAssets = getMissingModelAssets()
    if missingAssets:
        if args.skip_model_download:
            print(
                "Missing model assets: {0}. Run scripts/download_model.py first.".format(
                    ", ".join(MODEL_FILE_NAMES[assetName] for assetName in missingAssets)
                ),
                file=sys.stderr,
            )
            return 1

        downloadMissingModelAssets()

    command = [sys.executable, "-m", "PyInstaller", "--noconfirm"]
    if args.clean:
        command.append("--clean")
    command.append("cnn-colorizer.spec")

    completedProcess = subprocess.run(command, cwd=ROOT_DIR)
    return completedProcess.returncode


if __name__ == "__main__":
    raise SystemExit(main())
