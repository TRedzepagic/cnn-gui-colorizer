import os
import queue
import sys
import tempfile
import types
import unittest
from unittest import mock

sys.modules.setdefault(
    "cv2",
    types.SimpleNamespace(
        imread=None,
        imwrite=None,
        VideoWriter=None,
        VideoWriter_fourcc=None,
    ),
)
sys.modules.setdefault("numpy", types.SimpleNamespace())

from colorizer import Colorizer


class DummyLogger:
    def __init__(self):
        self.messages = []

    def logMsg(self, source, msg, level="INFO"):
        self.messages.append((source, msg, level))


class ColorizerTests(unittest.TestCase):
    def setUp(self):
        self.colorizer = Colorizer(DummyLogger(), queue.Queue(), queue.Queue())

    def testCreateSavePathPreservesFullExtensionSplit(self):
        save_path = self.colorizer.createSavePath("./bwImages/folder.with.dots/sample.image.png")
        self.assertEqual(
            save_path,
            "./colorizedImages/folder.with.dots/sample.image_colorized.png",
        )

    def testCreateSavePathFallsBackToOutputDirectories(self):
        image_path = self.colorizer.createSavePath("/tmp/input/archive.photo.jpeg")
        video_path = self.colorizer.createSavePath("/tmp/input/archive.clip.mp4", savePathType="VID")

        self.assertEqual(image_path, "./colorizedImages/archive.photo_colorized.jpeg")
        self.assertEqual(video_path, "./colorizedVideos/archive.clip_colorized.mp4")

    def testConvertFramesToVideoStreamsFramesWithoutCollectingThem(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            for name in ["0.jpg", "1.jpg", "2.jpg"]:
                with open(os.path.join(temp_dir, name), "wb") as frame_file:
                    frame_file.write(b"frame")

            fake_frame = types.SimpleNamespace(shape=(2, 3, 3))
            writer = mock.Mock()

            with mock.patch("colorizer.cv2.imread", return_value=fake_frame) as mock_imread:
                with mock.patch("colorizer.cv2.VideoWriter_fourcc", return_value=1234):
                    with mock.patch("colorizer.cv2.VideoWriter", return_value=writer) as mock_writer:
                        self.colorizer._convertFramesToVideo(temp_dir, "out.mp4", 24)

            self.assertEqual(mock_imread.call_count, 3)
            mock_writer.assert_called_once_with("out.mp4", 1234, 24, (3, 2))
            self.assertEqual(writer.write.call_count, 3)
            writer.release.assert_called_once()

    def testColorizeBWImageTrimsProcessMemoryAfterCompletion(self):
        fakeNet = mock.Mock()
        fakeNet.colorize.return_value = object()

        with mock.patch("colorizer.cv2.imread", return_value=object()):
            with mock.patch("colorizer.cv2.imwrite", return_value=True):
                with mock.patch("colorizer.NeuralNet", return_value=fakeNet):
                    with mock.patch("colorizer.trimProcessMemory") as trimProcessMemoryMock:
                        self.colorizer.colorizeBWImage("bwImages/example.jpg")

        trimProcessMemoryMock.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
