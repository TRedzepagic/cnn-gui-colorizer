#!/usr/bin/env python3
import argparse
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from model_utils import downloadMissingModelAssets, getMissingModelAssets, getModelDirectory
from model_utils import MODEL_FILE_NAMES


def parseArgs():
    parser = argparse.ArgumentParser(
        description="Download the Colorizer model assets into the configured model directory.",
    )
    parser.add_argument(
        "--target-dir",
        dest="targetDir",
        default=None,
        help="Override the destination model directory.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download files even if they already exist.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Only check whether the model assets exist.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output.",
    )
    return parser.parse_args()


def main():
    args = parseArgs()
    modelDir = args.targetDir or getModelDirectory()
    missingAssets = getMissingModelAssets(modelDir)

    if args.check:
        if missingAssets:
            print(
                "Missing model assets in {0}: {1}".format(
                    modelDir,
                    ", ".join(MODEL_FILE_NAMES[assetName] for assetName in missingAssets),
                )
            )
            return 1

        print("Model assets are present in {0}".format(modelDir))
        return 0

    downloadedAssets = downloadMissingModelAssets(
        modelDir=modelDir,
        force=args.force,
        quiet=args.quiet,
    )

    if not args.quiet:
        if downloadedAssets:
            print("Model assets ready in {0}".format(modelDir))
        else:
            print("Model assets already present in {0}".format(modelDir))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
