#!/usr/bin/env python3
import argparse
import os
import shutil
import sys
import tarfile
import zipfile


def parseArgs():
    parser = argparse.ArgumentParser(
        description="Archive a built release directory for GitHub releases.",
    )
    parser.add_argument(
        "--source",
        required=True,
        help="Path to the built release directory.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Archive path to create.",
    )
    return parser.parse_args()


def createZipArchive(sourceDir, outputPath):
    with zipfile.ZipFile(outputPath, "w", compression=zipfile.ZIP_DEFLATED) as archiveFile:
        for rootDir, _, fileNames in os.walk(sourceDir):
            for fileName in fileNames:
                absolutePath = os.path.join(rootDir, fileName)
                relativePath = os.path.relpath(absolutePath, os.path.dirname(sourceDir))
                archiveFile.write(absolutePath, relativePath)


def createTarGzArchive(sourceDir, outputPath):
    with tarfile.open(outputPath, "w:gz") as archiveFile:
        archiveFile.add(sourceDir, arcname=os.path.basename(sourceDir))


def main():
    args = parseArgs()
    sourceDir = os.path.abspath(args.source)
    outputPath = os.path.abspath(args.output)

    if not os.path.isdir(sourceDir):
        print("Release directory not found: {0}".format(sourceDir), file=sys.stderr)
        return 1

    os.makedirs(os.path.dirname(outputPath), exist_ok=True)
    if os.path.exists(outputPath):
        os.remove(outputPath)

    if outputPath.endswith(".zip"):
        createZipArchive(sourceDir, outputPath)
    elif outputPath.endswith(".tar.gz"):
        createTarGzArchive(sourceDir, outputPath)
    else:
        print("Unsupported archive format for {0}".format(outputPath), file=sys.stderr)
        return 1

    print(outputPath)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
