import unittest
from unittest import mock

from media_display_helper import (
    MediaDisplayHelper,
    fitSizeWithin,
    getCenteredPosition,
    getDisplayedImageRect,
    getPreviewPaneMetrics,
    getRenderTextureSize,
    inferPreviewSlot,
)


class MediaDisplayHelperTests(unittest.TestCase):
    def testFitSizeWithinPreservesAspectRatioForLandscape(self):
        self.assertEqual(fitSizeWithin(1920, 1080, 800, 600), (800, 450))

    def testFitSizeWithinPreservesAspectRatioForPortrait(self):
        self.assertEqual(fitSizeWithin(1000, 2000, 900, 900), (450, 900))

    def testFitSizeWithinRejectsInvalidSizes(self):
        with self.assertRaises(ValueError):
            fitSizeWithin(0, 100, 100, 100)

    def testGetPreviewPaneMetricsCalculatesInnerBounds(self):
        metrics = getPreviewPaneMetrics(1200, 500)
        self.assertEqual(metrics["paneWidth"], 592)
        self.assertEqual(metrics["paneHeight"], 500)
        self.assertEqual(metrics["innerWidth"], 576)
        self.assertEqual(metrics["innerHeight"], 484)

    def testGetCenteredPositionCentersItemInsidePaddedArea(self):
        self.assertEqual(
            getCenteredPosition(592, 500, 221, 265, paddingX=8, paddingY=8),
            (185, 117),
        )

    def testGetRenderTextureSizeKeepsExistingTextureDimensions(self):
        paneMetrics = getPreviewPaneMetrics(1600, 900)
        self.assertEqual(
            getRenderTextureSize(640, 480, paneMetrics, existingTextureSize=(320, 240)),
            (320, 240),
        )

    def testGetDisplayedImageRectCentersExistingTextureWithinPane(self):
        paneMetrics = getPreviewPaneMetrics(1200, 500)
        displayRect = getDisplayedImageRect(221, 265, paneMetrics)
        self.assertEqual(displayRect, {"width": 403, "height": 484, "x": 94, "y": 8})

    def testInferPreviewSlotDetectsColorizedOutputs(self):
        self.assertEqual(inferPreviewSlot("./colorizedImages/example_colorized.png"), "result")
        self.assertEqual(inferPreviewSlot("./colorizedVideos/example_colorized.mp4"), "result")
        self.assertEqual(inferPreviewSlot("./bwImages/example.png"), "source")

    def testClearPreviewsReleasesResourcesAndResetsState(self):
        helper = MediaDisplayHelper()
        captures = {}
        existingItems = {"rgbi"}

        for slot in ["source", "result"]:
            pane = helper.panes[slot]
            pane["textureTag"] = "testTexture::{0}".format(slot)
            pane["textureSize"] = (1, 1)
            pane["frameRgb"] = object()
            pane["mediaType"] = "IMAGE"
            pane["mediaPath"] = "/tmp/{0}.png".format(slot)
            pane["videoCapture"] = mock.Mock()
            captures[slot] = pane["videoCapture"]
            existingItems.add(pane["imageTag"])
            existingItems.add(pane["textureTag"])

        with mock.patch("media_display_helper.dpg.does_item_exist", side_effect=lambda tag: tag in existingItems):
            with mock.patch("media_display_helper.dpg.delete_item") as deleteItemMock:
                with mock.patch("media_display_helper.dpg.set_value") as setValueMock:
                    with mock.patch("media_display_helper.dpg.show_item") as showItemMock:
                        with mock.patch("media_display_helper.trimProcessMemory") as trimProcessMemoryMock:
                            self.assertTrue(helper.hasBothPreviews())
                            helper.clearPreviews()

        self.assertFalse(helper.hasBothPreviews())
        trimProcessMemoryMock.assert_called_once_with()

        setValueMock.assert_any_call("rgbi", "Hover either preview to inspect RGB values.")
        setValueMock.assert_any_call(
            helper.panes["source"]["statusTag"],
            helper.defaultPlaceholderMessages["source"],
        )
        setValueMock.assert_any_call(
            helper.panes["result"]["statusTag"],
            helper.defaultPlaceholderMessages["result"],
        )

        for slot in ["source", "result"]:
            pane = helper.panes[slot]
            captures[slot].release.assert_called_once_with()
            self.assertIsNone(pane["frameRgb"])
            self.assertIsNone(pane["mediaPath"])
            self.assertIsNone(pane["videoCapture"])
            self.assertIsNone(pane["textureTag"])
            deleteItemMock.assert_any_call(pane["imageTag"])
            deleteItemMock.assert_any_call("testTexture::{0}".format(slot))
            showItemMock.assert_any_call(pane["emptyTag"])

    def testUpdateLayoutDoesNotRebuildLoadedTextures(self):
        helper = MediaDisplayHelper()
        helper.panes["source"]["frameRgb"] = object()

        with mock.patch("media_display_helper.dpg.configure_item"):
            with mock.patch.object(helper, "_renderFrame") as renderFrameMock:
                with mock.patch.object(helper, "_syncPresentedFrame") as syncPresentedFrameMock:
                    helper.updateLayout(1400, 700)

        renderFrameMock.assert_not_called()
        syncPresentedFrameMock.assert_called_once_with("source")


if __name__ == "__main__":
    unittest.main()
