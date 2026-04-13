import os
import time

import cv2
import dearpygui.dearpygui as dpg
import numpy as np

from memory_utils import trimProcessMemory


def fitSizeWithin(sourceWidth, sourceHeight, maxWidth, maxHeight):
    if sourceWidth <= 0 or sourceHeight <= 0:
        raise ValueError("Source dimensions must be positive.")
    if maxWidth <= 0 or maxHeight <= 0:
        raise ValueError("Maximum dimensions must be positive.")

    scale = min(maxWidth / sourceWidth, maxHeight / sourceHeight)
    return max(int(sourceWidth * scale), 1), max(int(sourceHeight * scale), 1)


def getPreviewPaneMetrics(previewWidth, previewHeight):
    clampedPreviewWidth = max(int(previewWidth), 240)
    clampedPreviewHeight = max(int(previewHeight), 220)
    paneWidth = max(int((clampedPreviewWidth - 16) / 2), 180)
    paneHeight = clampedPreviewHeight
    innerWidth = max(paneWidth - 16, 64)
    innerHeight = max(paneHeight - 16, 64)
    paddingX = max(int((paneWidth - innerWidth) / 2), 0)
    paddingY = max(int((paneHeight - innerHeight) / 2), 0)

    return {
        "paneWidth": paneWidth,
        "paneHeight": paneHeight,
        "innerWidth": innerWidth,
        "innerHeight": innerHeight,
        "paddingX": paddingX,
        "paddingY": paddingY,
    }


def getCenteredPosition(containerWidth, containerHeight, itemWidth, itemHeight, paddingX=0, paddingY=0):
    if itemWidth <= 0 or itemHeight <= 0:
        raise ValueError("Item dimensions must be positive.")

    availableWidth = max(int(containerWidth) - (int(paddingX) * 2), 0)
    availableHeight = max(int(containerHeight) - (int(paddingY) * 2), 0)
    offsetX = int(paddingX) + max(int((availableWidth - itemWidth) / 2), 0)
    offsetY = int(paddingY) + max(int((availableHeight - itemHeight) / 2), 0)
    return offsetX, offsetY


def getRenderTextureSize(sourceWidth, sourceHeight, paneMetrics, existingTextureSize=None):
    if existingTextureSize is not None:
        return existingTextureSize

    return fitSizeWithin(
        sourceWidth,
        sourceHeight,
        paneMetrics["innerWidth"],
        paneMetrics["innerHeight"],
    )


def getDisplayedImageRect(textureWidth, textureHeight, paneMetrics):
    displayWidth, displayHeight = fitSizeWithin(
        textureWidth,
        textureHeight,
        paneMetrics["innerWidth"],
        paneMetrics["innerHeight"],
    )
    imageX, imageY = getCenteredPosition(
        paneMetrics["paneWidth"],
        paneMetrics["paneHeight"],
        displayWidth,
        displayHeight,
        paddingX=paneMetrics["paddingX"],
        paddingY=paneMetrics["paddingY"],
    )
    return {
        "width": displayWidth,
        "height": displayHeight,
        "x": imageX,
        "y": imageY,
    }


def inferPreviewSlot(path):
    normalizedPath = path.replace("\\", "/")
    fileName = os.path.basename(normalizedPath)
    if (
        "_colorized" in fileName
        or "/outputs/colorizedImages/" in normalizedPath
        or "/outputs/colorizedVideos/" in normalizedPath
        or "/colorizedImages/" in normalizedPath
        or "/colorizedVideos/" in normalizedPath
    ):
        return "result"
    return "source"


class MediaDisplayHelper:
    def __init__(self, logger=None) -> None:
        self.logger = logger

        self.textureRegistryTag = "comparisonTextureRegistry"
        self.comparisonGroupTag = "comparisonPreviewGroup"
        self.defaultPlaceholderMessages = {
            "source": "Select an image or video to preview inside the app.",
            "result": "Waiting for colorized output.",
        }

        self.previewWidth = 640
        self.previewHeight = 360
        self._textureIndex = 0

        self.panes = {
            "source": self._createPane("source", "Black and White"),
            "result": self._createPane("result", "Colorized"),
        }

    def setLogger(self, logger):
        self.logger = logger

    def buildUi(self, parent):
        with dpg.texture_registry(tag=self.textureRegistryTag, show=False):
            pass

        dpg.add_text("Comparison Preview", parent=parent)
        with dpg.group(tag=self.comparisonGroupTag, parent=parent, horizontal=True):
            self._buildPaneUi("source")
            self._buildPaneUi("result")

        self._setPlaceholder("source", self.defaultPlaceholderMessages["source"])
        self._setPlaceholder("result", self.defaultPlaceholderMessages["result"])

    def updateLayout(self, width, height):
        self.previewWidth = max(int(width), 240)
        self.previewHeight = max(int(height), 220)

        paneMetrics = getPreviewPaneMetrics(self.previewWidth, self.previewHeight)

        for pane in self.panes.values():
            dpg.configure_item(pane["groupTag"], width=paneMetrics["paneWidth"])
            dpg.configure_item(
                pane["containerTag"],
                width=paneMetrics["paneWidth"],
                height=paneMetrics["paneHeight"],
            )
            dpg.configure_item(pane["pathTag"], wrap=paneMetrics["innerWidth"])

            if pane["frameRgb"] is not None:
                self._syncPresentedFrame(pane["slot"])

    def display(self, path, mediaType):
        slot = inferPreviewSlot(path)
        if slot == "source":
            self._prepareForNewSource(mediaType, path)

        if mediaType == "IMAGE":
            self._showImage(slot, path)
        elif mediaType == "VIDEO":
            self._showVideo(slot, path)

    def update(self):
        for slot in self.panes:
            self._updateVideoFrame(slot)
        self._updateRGBInspector()

    def terminate(self):
        for slot in self.panes:
            self._releaseVideo(slot)

    def hasBothPreviews(self):
        return all(self._paneHasMedia(slot) for slot in self.panes)

    def hasAnyPreview(self):
        return any(self._paneHasMedia(slot) for slot in self.panes)

    def hasSourcePreview(self):
        return self._paneHasMedia("source")

    def hasResultPreview(self):
        return self._paneHasMedia("result")

    def getSourceMedia(self):
        if not self.hasSourcePreview():
            return None

        sourcePane = self.panes["source"]
        return {
            "path": sourcePane["mediaPath"],
            "mediaType": sourcePane["mediaType"],
        }

    def clearPreviews(self):
        for slot in self.panes:
            self._releaseVideo(slot)
            self._setPlaceholder(slot, self.defaultPlaceholderMessages[slot])

        if dpg.does_item_exist("rgbi"):
            dpg.set_value("rgbi", "Hover either preview to inspect RGB values.")

        trimProcessMemory()
        self._log("MediaDisplayHelper", "Cleared preview buffers from memory.", "INFO")

    def _createPane(self, slot, label):
        return {
            "slot": slot,
            "label": label,
            "groupTag": "{0}PreviewGroup".format(slot),
            "statusTag": "{0}PreviewStatus".format(slot),
            "pathTag": "{0}PreviewPath".format(slot),
            "containerTag": "{0}PreviewContainer".format(slot),
            "emptyTag": "{0}PreviewEmpty".format(slot),
            "imageTag": "{0}PreviewImage".format(slot),
            "textureTag": None,
            "textureSize": None,
            "frameRgb": None,
            "mediaType": None,
            "mediaPath": None,
            "videoCapture": None,
            "videoFrameInterval": 1.0 / 24.0,
            "videoLastFrameAt": 0.0,
        }

    def _paneHasMedia(self, slot):
        pane = self.panes[slot]
        return pane["mediaPath"] is not None and pane["frameRgb"] is not None

    def _buildPaneUi(self, slot):
        pane = self.panes[slot]
        with dpg.group(tag=pane["groupTag"], horizontal=False, parent=self.comparisonGroupTag):
            dpg.add_text(pane["label"])
            dpg.add_text(tag=pane["statusTag"], default_value="No media loaded yet.")
            dpg.add_text(tag=pane["pathTag"], default_value="")
            with dpg.child_window(
                tag=pane["containerTag"],
                border=True,
                height=self.previewHeight,
            ):
                dpg.add_text("", tag=pane["emptyTag"])

    def _prepareForNewSource(self, mediaType, path):
        sourcePane = self.panes["source"]
        if sourcePane["mediaPath"] == path and sourcePane["mediaType"] == mediaType:
            return

        self._releaseVideo("result")
        self._setPlaceholder("result", self.defaultPlaceholderMessages["result"])

    def _showImage(self, slot, path):
        pane = self.panes[slot]
        if pane["mediaPath"] != path or pane["mediaType"] != "IMAGE":
            self._dropTexture(slot)
        self._releaseVideo(slot)

        frameBgr = cv2.imread(path, cv2.IMREAD_COLOR)
        if frameBgr is None:
            self._setError(slot, "Unable to load preview image: {0}".format(path))
            return

        pane["frameRgb"] = cv2.cvtColor(frameBgr, cv2.COLOR_BGR2RGB)
        pane["mediaType"] = "IMAGE"
        pane["mediaPath"] = path

        height, width = pane["frameRgb"].shape[:2]
        self._setStatus(slot, "Image preview | {0}x{1}".format(width, height), path)
        self._renderFrame(slot)

    def _showVideo(self, slot, path):
        pane = self.panes[slot]
        if pane["mediaPath"] != path or pane["mediaType"] != "VIDEO":
            self._dropTexture(slot)
        self._releaseVideo(slot)

        capture = cv2.VideoCapture(path)
        if not capture.isOpened():
            self._setError(slot, "Unable to open preview video: {0}".format(path))
            return

        ret, frameBgr = capture.read()
        if not ret or frameBgr is None:
            capture.release()
            self._setError(slot, "Unable to read frames from preview video: {0}".format(path))
            return

        fps = capture.get(cv2.CAP_PROP_FPS)
        if not fps or fps <= 0:
            fps = 24.0

        previewFps = min(fps, 30.0)
        pane["videoCapture"] = capture
        pane["videoFrameInterval"] = 1.0 / max(previewFps, 1.0)
        pane["videoLastFrameAt"] = time.monotonic()
        pane["mediaType"] = "VIDEO"
        pane["mediaPath"] = path
        pane["frameRgb"] = cv2.cvtColor(frameBgr, cv2.COLOR_BGR2RGB)

        height, width = pane["frameRgb"].shape[:2]
        self._setStatus(
            slot,
            "Video preview | {0}x{1} | {2:.2f} FPS preview".format(width, height, previewFps),
            path,
        )
        self._renderFrame(slot)

        if (
            self.panes["source"]["videoCapture"] is not None
            and self.panes["result"]["videoCapture"] is not None
        ):
            self._synchronizeVideoPair()

    def _updateVideoFrame(self, slot):
        pane = self.panes[slot]
        if pane["videoCapture"] is None:
            return

        now = time.monotonic()
        if now - pane["videoLastFrameAt"] < pane["videoFrameInterval"]:
            return

        pane["videoLastFrameAt"] = now
        ret, frameBgr = pane["videoCapture"].read()
        if not ret or frameBgr is None:
            pane["videoCapture"].set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frameBgr = pane["videoCapture"].read()

        if not ret or frameBgr is None:
            self._setError(slot, "Unable to continue preview playback for: {0}".format(pane["mediaPath"]))
            self._releaseVideo(slot)
            return

        pane["frameRgb"] = cv2.cvtColor(frameBgr, cv2.COLOR_BGR2RGB)
        self._renderFrame(slot)

    def _synchronizeVideoPair(self):
        syncTime = time.monotonic()
        for slot in ["source", "result"]:
            pane = self.panes[slot]
            pane["videoCapture"].set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frameBgr = pane["videoCapture"].read()
            if not ret or frameBgr is None:
                self._setError(slot, "Unable to synchronize preview video: {0}".format(pane["mediaPath"]))
                self._releaseVideo(slot)
                continue

            pane["frameRgb"] = cv2.cvtColor(frameBgr, cv2.COLOR_BGR2RGB)
            pane["videoLastFrameAt"] = syncTime
            self._renderFrame(slot)

    def _renderFrame(self, slot):
        pane = self.panes[slot]
        textureRgb = self._resizeForTexture(slot, pane["frameRgb"])
        textureHeight, textureWidth = textureRgb.shape[:2]
        textureData = self._createTextureData(textureRgb)

        createdTexture = self._ensureTexture(slot, textureWidth, textureHeight, textureData)
        if not createdTexture:
            dpg.set_value(pane["textureTag"], textureData)

        dpg.hide_item(pane["emptyTag"])
        if dpg.does_item_exist(pane["imageTag"]):
            dpg.show_item(pane["imageTag"])
            self._syncPresentedFrame(slot)

    def _resizeForTexture(self, slot, frameRgb):
        pane = self.panes[slot]
        sourceHeight, sourceWidth = frameRgb.shape[:2]
        paneMetrics = getPreviewPaneMetrics(self.previewWidth, self.previewHeight)
        targetWidth, targetHeight = getRenderTextureSize(
            sourceWidth,
            sourceHeight,
            paneMetrics,
            existingTextureSize=pane["textureSize"],
        )

        if (targetWidth, targetHeight) == (sourceWidth, sourceHeight):
            return frameRgb

        interpolation = cv2.INTER_AREA
        if targetWidth > sourceWidth or targetHeight > sourceHeight:
            interpolation = cv2.INTER_LINEAR

        return cv2.resize(frameRgb, (targetWidth, targetHeight), interpolation=interpolation)

    def _syncPresentedFrame(self, slot):
        pane = self.panes[slot]
        if pane["textureSize"] is None or not dpg.does_item_exist(pane["imageTag"]):
            return

        paneMetrics = getPreviewPaneMetrics(self.previewWidth, self.previewHeight)
        displayRect = getDisplayedImageRect(
            pane["textureSize"][0],
            pane["textureSize"][1],
            paneMetrics,
        )
        dpg.configure_item(
            pane["imageTag"],
            width=displayRect["width"],
            height=displayRect["height"],
        )
        dpg.set_item_pos(pane["imageTag"], [displayRect["x"], displayRect["y"]])

    def _createTextureData(self, frameRgb):
        rgba = cv2.cvtColor(frameRgb, cv2.COLOR_RGB2RGBA)
        return np.ascontiguousarray(rgba, dtype=np.float32).ravel() / 255.0

    def _ensureTexture(self, slot, width, height, textureData):
        pane = self.panes[slot]
        if pane["textureTag"] is not None and pane["textureSize"] == (width, height):
            return False

        self._dropTexture(slot)

        textureTag = "previewTexture::{0}".format(self._textureIndex)
        self._textureIndex += 1

        dpg.add_dynamic_texture(
            width=width,
            height=height,
            default_value=textureData,
            tag=textureTag,
            parent=self.textureRegistryTag,
        )
        dpg.add_image(textureTag, tag=pane["imageTag"], parent=pane["containerTag"])

        pane["textureTag"] = textureTag
        pane["textureSize"] = (width, height)
        return True

    def _updateRGBInspector(self):
        if not dpg.does_item_exist("rgbi"):
            return

        for pane in self.panes.values():
            if (
                pane["frameRgb"] is None
                or not dpg.does_item_exist(pane["imageTag"])
                or not dpg.is_item_hovered(pane["imageTag"])
            ):
                continue

            rectMin = dpg.get_item_rect_min(pane["imageTag"])
            rectSize = dpg.get_item_rect_size(pane["imageTag"])
            if rectSize[0] <= 0 or rectSize[1] <= 0:
                continue

            mouseX, mouseY = dpg.get_mouse_pos(local=True)
            relativeX = min(max((mouseX - rectMin[0]) / rectSize[0], 0.0), 0.999999)
            relativeY = min(max((mouseY - rectMin[1]) / rectSize[1], 0.0), 0.999999)

            sourceHeight, sourceWidth = pane["frameRgb"].shape[:2]
            pixelX = min(int(relativeX * sourceWidth), sourceWidth - 1)
            pixelY = min(int(relativeY * sourceHeight), sourceHeight - 1)
            red, green, blue = [int(channel) for channel in pane["frameRgb"][pixelY, pixelX]]

            dpg.set_value(
                "rgbi",
                "{0} pixel ({1}, {2}): ({3}, {4}, {5})".format(
                    pane["label"], pixelX, pixelY, red, green, blue
                ),
            )
            return

        dpg.set_value("rgbi", "Hover either preview to inspect RGB values.")

    def _setStatus(self, slot, status, path):
        pane = self.panes[slot]
        dpg.set_value(pane["statusTag"], status)
        dpg.set_value(pane["pathTag"], path)

    def _setPlaceholder(self, slot, message):
        pane = self.panes[slot]
        pane["frameRgb"] = None
        pane["mediaType"] = None
        pane["mediaPath"] = None
        self._dropTexture(slot)

        dpg.set_value(pane["statusTag"], message)
        dpg.set_value(pane["pathTag"], "")
        dpg.set_value(pane["emptyTag"], message)
        dpg.show_item(pane["emptyTag"])

    def _setError(self, slot, message):
        self._setPlaceholder(slot, message)
        self._log("MediaDisplayHelper", message, "CRITICAL")

    def _releaseVideo(self, slot):
        pane = self.panes[slot]
        if pane["videoCapture"] is not None:
            pane["videoCapture"].release()
            pane["videoCapture"] = None

    def _dropTexture(self, slot):
        pane = self.panes[slot]
        if dpg.does_item_exist(pane["imageTag"]):
            dpg.delete_item(pane["imageTag"])
        if pane["textureTag"] is not None and dpg.does_item_exist(pane["textureTag"]):
            dpg.delete_item(pane["textureTag"])

        pane["textureTag"] = None
        pane["textureSize"] = None

    def _log(self, source, message, level="INFO"):
        if self.logger is not None:
            self.logger.logMsg(source, message, level)
