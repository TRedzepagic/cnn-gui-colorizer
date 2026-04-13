#!/usr/bin/env python3
import os
import webbrowser

import dearpygui.dearpygui as dpg

from queue import Empty, Queue as ThreadQueue
from threading import Thread

from colorizer import Colorizer
from logger import Logger
from media_display_helper import MediaDisplayHelper
from model_utils import (
    MODEL_MANUAL_DOWNLOAD_URL,
    downloadMissingModelAssets,
    getMissingModelFileNames,
    getModelDirectory,
    hasModelAssets,
)
from runtime_support import APP_WINDOW_TITLE, configureProcessIdentity
from work_object import ColorizationWorkObject

DEFAULT_VIEWPORT_WIDTH = 1280
DEFAULT_VIEWPORT_HEIGHT = 720
MIN_UI_SCALE = 0.75
MAX_UI_SCALE = 3.0
CONTROL_COLUMN_RATIO = 0.33
SUPPORTED_IMAGE_EXTENSIONS = ("jpg", "jpeg", "bmp", "png")
SUPPORTED_VIDEO_EXTENSIONS = ("mp4", "avi")

logger = None
colorizer = None
displayQueue = None
mediaDisplayHelper = None
uiScaleMode = "auto"
uiScaleValue = 1.0
lastViewportSize = None
pendingUIScaleValue = None
layoutSyncPending = False
previewClearPending = False
modelDownloadQueue = None
modelDownloadInProgress = False
modelDownloadStatusMessage = ""


def formatStartupError(prefix, error):
    return "{0}: {1}".format(prefix, str(error).splitlines()[0])


def clamp(value, minimum, maximum):
    return max(minimum, min(value, maximum))


def getAutoUIScale(viewportWidth, viewportHeight):
    autoScale = max(viewportWidth / 1920.0, viewportHeight / 1080.0, 1.0)
    return round(clamp(autoScale, 1.0, 2.5), 2)


def getConfiguredUIScale():
    configuredScale = os.environ.get("COLORIZER_UI_SCALE")
    if not configuredScale:
        return None

    try:
        return clamp(float(configuredScale), MIN_UI_SCALE, MAX_UI_SCALE)
    except ValueError:
        return None


def applyUIScale(scale, updateSlider=True):
    clampedScale = clamp(scale, MIN_UI_SCALE, MAX_UI_SCALE)
    dpg.set_global_font_scale(clampedScale)
    if updateSlider and dpg.does_item_exist("uiScaleSlider"):
        dpg.set_value("uiScaleSlider", clampedScale)
    return clampedScale


def requestLayoutSync():
    global layoutSyncPending
    layoutSyncPending = True


def requestPreviewClear():
    global previewClearPending
    previewClearPending = True


def getModelMissingMessage():
    missingModelFiles = getMissingModelFileNames()
    if not missingModelFiles:
        return "Model files are ready."

    return "Model not found in {0}. Missing: {1}".format(
        getModelDirectory(),
        ", ".join(missingModelFiles),
    )


def syncModelDialogState():
    if not dpg.does_item_exist("modelMissingDialog"):
        return

    dpg.set_value("modelMissingDialogMessage", getModelMissingMessage())

    statusMessage = modelDownloadStatusMessage
    if modelDownloadInProgress and not statusMessage:
        statusMessage = "Downloading model files..."
    dpg.set_value("modelMissingDialogStatus", statusMessage)

    if dpg.does_item_exist("downloadModelButton"):
        dpg.configure_item("downloadModelButton", enabled=not modelDownloadInProgress)


def showModelMissingDialog(statusMessage=None):
    global modelDownloadStatusMessage

    if statusMessage is not None:
        modelDownloadStatusMessage = statusMessage

    syncModelDialogState()
    if dpg.does_item_exist("modelMissingDialog"):
        dpg.show_item("modelMissingDialog")


def ensureModelAvailable():
    if hasModelAssets():
        return True

    warningMessage = getModelMissingMessage()
    if logger is not None:
        logger.logMsg("Main", warningMessage, "WARNING")
    showModelMissingDialog()
    return False


def getSupportedExtensionsLabel():
    supportedExtensions = SUPPORTED_IMAGE_EXTENSIONS + SUPPORTED_VIDEO_EXTENSIONS
    return ", ".join(".{0}".format(extension) for extension in supportedExtensions)


def isVideoColorizationActive():
    return colorizer is not None and colorizer.videoColorizationInProgress.is_set()


def shouldOfferStartColorizationAction():
    if mediaDisplayHelper is None or isVideoColorizationActive():
        return False

    return mediaDisplayHelper.hasSourcePreview() and not mediaDisplayHelper.hasResultPreview()


def getPrimaryActionLabel():
    if shouldOfferStartColorizationAction():
        return "Start colorization"

    return "Select image or video to colorize..."


def handlePrimaryAction():
    if shouldOfferStartColorizationAction():
        sourceMedia = mediaDisplayHelper.getSourceMedia()
        if sourceMedia is not None:
            enqueueWorkObject(sourceMedia["path"], sourceMedia["mediaType"])
            return

    if not ensureModelAvailable():
        return

    dpg.show_item("file_dialog_tag")


def getGUIStartupError():
    displayName = os.environ.get("DISPLAY")
    waylandDisplay = os.environ.get("WAYLAND_DISPLAY")

    if not displayName and not waylandDisplay:
        return "No graphical display detected. Set DISPLAY or WAYLAND_DISPLAY before starting the GUI."

    if not displayName:
        return None

    try:
        from Xlib.display import Display
    except Exception:
        return None

    try:
        display = Display(displayName)
        display.close()
    except Exception as e:
        return formatStartupError(
            "Unable to open graphical display {0}".format(displayName),
            e,
        )

    return None


def enqueueWorkObject(path, mediaType):
    if not ensureModelAvailable():
        return False

    workObject = ColorizationWorkObject(path, mediaType)
    colorizer.enqueue(workObject)
    return True


def callback(sender, appData):
    try:
        selections = appData.get("selections") or {}
        for _, path in selections.items():
            extension = os.path.splitext(path)[1].lower().lstrip(".")

            if extension in SUPPORTED_IMAGE_EXTENSIONS:
                enqueueWorkObject(path, "IMAGE")
            elif extension in SUPPORTED_VIDEO_EXTENSIONS:
                enqueueWorkObject(path, "VIDEO")
            else:
                logger.logMsg(
                    "Main",
                    "Unsupported extension '.{0}'. Supported extensions: {1}".format(
                        extension,
                        getSupportedExtensionsLabel(),
                    ),
                    "WARNING",
                )
    except Exception as e:
        logger.logMsg("Main:callback", str(e), "CRITICAL")


def drainDisplayUpdates():
    try:
        while True:
            displayUpdate = displayQueue.get_nowait()
            for mediaType, path in displayUpdate.retrieve().items():
                mediaDisplayHelper.display(path, mediaType)
    except Empty:
        return
    except Exception as e:
        logger.logMsg("drainDisplayUpdates", str(e), "CRITICAL")


def discardPendingDisplayUpdates():
    if displayQueue is None:
        return

    try:
        while True:
            displayQueue.get_nowait()
    except Empty:
        return


def terminateProgram():
    try:
        if mediaDisplayHelper is not None:
            mediaDisplayHelper.terminate()
        if colorizer is not None:
            colorizer.terminateColorizer()
            colorizer.join(timeout=2)
    except Exception as e:
        if logger is not None:
            logger.logMsg("terminateProgram", str(e), "CRITICAL")
        else:
            print(str(e))


def cancelColorization():
    try:
        colorizer.cancelVideoColorization()
    except Exception as e:
        logger.logMsg("cancelColorization", str(e), "CRITICAL")


def hideVideoColorizationUIItems():
    dpg.hide_item("cancelColorizationButton")
    dpg.hide_item("progressBar")


def showVideoColorizationUIItems():
    dpg.show_item("cancelColorizationButton")
    dpg.show_item("progressBar")


def updateProgressBar():
    dpg.set_value("progressBar", colorizer.videoColorizationProgress)
    dpg.configure_item(
        "progressBar",
        overlay=str(int(colorizer.videoColorizationProgress * 100)) + "%",
    )


def handleUIScaleChange(sender, appData):
    global pendingUIScaleValue, uiScaleMode
    uiScaleMode = "manual"
    pendingUIScaleValue = clamp(appData, MIN_UI_SCALE, MAX_UI_SCALE)
    requestLayoutSync()


def resetUIScaleToAuto():
    global pendingUIScaleValue, uiScaleMode
    uiScaleMode = "auto"
    pendingUIScaleValue = None
    requestLayoutSync()


def clearPreviews():
    if isVideoColorizationActive():
        if logger is not None:
            logger.logMsg(
                "Main",
                "Cancel the active video colorization before clearing previews.",
                "WARNING",
            )
        return

    requestPreviewClear()


def processPendingLayout():
    global layoutSyncPending, pendingUIScaleValue, uiScaleValue

    if pendingUIScaleValue is not None:
        uiScaleValue = applyUIScale(pendingUIScaleValue, updateSlider=False)
        pendingUIScaleValue = None

    if not layoutSyncPending:
        return

    syncMainWindowLayout()
    layoutSyncPending = False


def processPendingPreviewClear():
    global previewClearPending

    if not previewClearPending or mediaDisplayHelper is None:
        return

    discardPendingDisplayUpdates()
    mediaDisplayHelper.clearPreviews()
    previewClearPending = False


def _downloadModelAssetsWorker():
    try:
        downloadedAssets = downloadMissingModelAssets(quiet=True)
        modelDownloadQueue.put(
            {
                "status": "success",
                "downloadedAssets": downloadedAssets,
            }
        )
    except Exception as e:
        modelDownloadQueue.put(
            {
                "status": "error",
                "message": str(e),
            }
        )


def startModelDownload():
    global modelDownloadInProgress, modelDownloadStatusMessage

    if modelDownloadInProgress:
        return

    modelDownloadInProgress = True
    modelDownloadStatusMessage = "Downloading model files..."
    syncModelDialogState()
    Thread(target=_downloadModelAssetsWorker, daemon=True).start()


def openModelDownloadPage():
    global modelDownloadStatusMessage

    try:
        opened = webbrowser.open(MODEL_MANUAL_DOWNLOAD_URL)
        if not opened:
            raise RuntimeError("Unable to open the model download page in a browser.")

        modelDownloadStatusMessage = "Opened the model download page in the default browser."
        syncModelDialogState()
    except Exception as e:
        errorMessage = "Unable to open the model download page: {0}".format(str(e))
        if logger is not None:
            logger.logMsg("Main", errorMessage, "CRITICAL")
        showModelMissingDialog(errorMessage)


def processModelDownloadEvents():
    global modelDownloadInProgress, modelDownloadStatusMessage

    if modelDownloadQueue is None:
        return

    try:
        while True:
            downloadEvent = modelDownloadQueue.get_nowait()
            modelDownloadInProgress = False

            if downloadEvent["status"] == "success":
                downloadedAssets = downloadEvent.get("downloadedAssets") or []
                modelDownloadStatusMessage = ""
                if logger is not None:
                    if downloadedAssets:
                        logger.logMsg("Main", "Model download complete.", "INFO")
                    else:
                        logger.logMsg("Main", "Model files are already present.", "INFO")

                syncModelDialogState()
                if hasModelAssets() and dpg.does_item_exist("modelMissingDialog"):
                    dpg.hide_item("modelMissingDialog")
            else:
                errorMessage = "Model download failed: {0}".format(downloadEvent["message"])
                if logger is not None:
                    logger.logMsg("Main", errorMessage, "CRITICAL")
                showModelMissingDialog(errorMessage)
    except Empty:
        return


def syncPreviewControlState():
    if mediaDisplayHelper is None:
        return

    if dpg.does_item_exist("selectMediaButton"):
        dpg.configure_item(
            "selectMediaButton",
            label=getPrimaryActionLabel(),
        )

    if not dpg.does_item_exist("clearPreviewsButton"):
        return

    dpg.configure_item(
        "clearPreviewsButton",
        enabled=mediaDisplayHelper.hasAnyPreview() and not isVideoColorizationActive(),
    )


def calculateLayoutMetrics(viewportWidth, viewportHeight, uiScaleValue):
    pageMargin = max(int(24 * uiScaleValue), 16)
    controlColumnWidth = min(
        max(int(viewportWidth * CONTROL_COLUMN_RATIO), 260),
        max(viewportWidth - (pageMargin * 2), 260),
    )
    controlSideWidth = max(int((viewportWidth - controlColumnWidth) / 2), 0)

    contentWidth = max(viewportWidth - (pageMargin * 2), 320)
    contentSideWidth = max(int((viewportWidth - contentWidth) / 2), 0)

    buttonHeight = max(int(50 * uiScaleValue), 50)
    sliderWidth = controlColumnWidth
    headerControlsHeight = max(int(240 * uiScaleValue), 210)
    headerGap = max(int(20 * uiScaleValue), 12)
    contentHeight = max(viewportHeight - headerControlsHeight - headerGap - pageMargin, 320)
    comparisonHeight = max(int(contentHeight * 0.52), 300)
    contentChromeHeight = max(int(112 * uiScaleValue), 96)
    logSectionHeight = max(contentHeight - comparisonHeight - contentChromeHeight, 180)

    return {
        "pageMargin": pageMargin,
        "controlColumnWidth": controlColumnWidth,
        "controlSideWidth": controlSideWidth,
        "contentWidth": contentWidth,
        "contentSideWidth": contentSideWidth,
        "buttonHeight": buttonHeight,
        "sliderWidth": sliderWidth,
        "headerControlsHeight": headerControlsHeight,
        "headerGap": headerGap,
        "contentHeight": contentHeight,
        "comparisonHeight": comparisonHeight,
        "logSectionHeight": logSectionHeight,
    }


def syncMainWindowLayout(sender=None, appData=None):
    global uiScaleValue

    viewportWidth = max(dpg.get_viewport_client_width(), 640)
    viewportHeight = max(dpg.get_viewport_client_height(), 480)
    if uiScaleMode == "auto":
        uiScaleValue = applyUIScale(getAutoUIScale(viewportWidth, viewportHeight))

    layoutMetrics = calculateLayoutMetrics(viewportWidth, viewportHeight, uiScaleValue)

    dpg.configure_item("mainWindow", width=viewportWidth, height=viewportHeight)
    dpg.configure_item("headerLeftSpacer", width=layoutMetrics["controlSideWidth"])
    dpg.configure_item("headerRightSpacer", width=layoutMetrics["controlSideWidth"])
    dpg.configure_item(
        "headerControlsContainer",
        width=layoutMetrics["controlColumnWidth"],
        height=layoutMetrics["headerControlsHeight"],
    )
    dpg.configure_item("contentLeftSpacer", width=layoutMetrics["contentSideWidth"])
    dpg.configure_item("contentRightSpacer", width=layoutMetrics["contentSideWidth"])
    dpg.configure_item("contentContainer", width=layoutMetrics["contentWidth"], height=layoutMetrics["contentHeight"])
    dpg.configure_item("logSection", width=layoutMetrics["contentWidth"], height=layoutMetrics["logSectionHeight"])

    dpg.configure_item(
        "selectMediaButton",
        width=layoutMetrics["controlColumnWidth"],
        height=layoutMetrics["buttonHeight"],
    )
    dpg.configure_item(
        "cancelColorizationButton",
        width=layoutMetrics["contentWidth"],
        height=layoutMetrics["buttonHeight"],
    )
    dpg.configure_item("progressBar", width=layoutMetrics["contentWidth"])
    dpg.configure_item("uiScaleSlider", width=layoutMetrics["sliderWidth"])
    dpg.configure_item(
        "uiScaleAutoButton",
        width=layoutMetrics["sliderWidth"],
        height=layoutMetrics["buttonHeight"],
    )
    dpg.configure_item(
        "clearPreviewsButton",
        width=layoutMetrics["sliderWidth"],
        height=layoutMetrics["buttonHeight"],
    )
    dpg.configure_item("rgbi", wrap=layoutMetrics["contentWidth"])

    if mediaDisplayHelper is not None:
        mediaDisplayHelper.updateLayout(
            layoutMetrics["contentWidth"],
            layoutMetrics["comparisonHeight"],
        )
    if logger is not None:
        logger.syncLayout(layoutMetrics["contentWidth"], layoutMetrics["logSectionHeight"])


if __name__ == "__main__":
    try:
        configureProcessIdentity()

        guiStartupError = getGUIStartupError()
        if guiStartupError is not None:
            raise SystemExit(guiStartupError)

        configuredScale = getConfiguredUIScale()
        if configuredScale is not None:
            uiScaleMode = "manual"
            uiScaleValue = configuredScale

        logQueue = ThreadQueue()
        displayQueue = ThreadQueue()
        workQueue = ThreadQueue()
        modelDownloadQueue = ThreadQueue()

        dpg.create_context()
        mediaDisplayHelper = MediaDisplayHelper()

        with dpg.file_dialog(directory_selector=False, show=False, callback=callback, tag="file_dialog_tag"):
            dpg.add_file_extension(".*")
            dpg.add_file_extension("", color=(150, 255, 150, 255))
            dpg.add_file_extension(".jpeg", color=(0, 255, 0, 255))
            dpg.add_file_extension(".jpg", color=(0, 255, 0, 255))
            dpg.add_file_extension(".png", color=(0, 255, 0, 255))
            dpg.add_file_extension(".bmp", color=(0, 255, 0, 255))
            dpg.add_file_extension(".mp4", color=(0, 255, 0, 255))
            dpg.add_file_extension(".avi", color=(0, 255, 0, 255))

        with dpg.window(
            tag="mainWindow",
            no_title_bar=False,
            no_close=False,
            no_bring_to_front_on_focus=False,
            no_move=False,
        ) as root:
            with dpg.group(tag="headerLayoutGroup", horizontal=True):
                dpg.add_spacer(tag="headerLeftSpacer")
                with dpg.child_window(
                    tag="headerControlsContainer",
                    border=False,
                    no_scrollbar=True,
                    height=160,
                ):
                    dpg.add_button(
                        label="Select image or video to colorize...",
                        tag="selectMediaButton",
                        height=50,
                        callback=handlePrimaryAction,
                    )
                    dpg.add_slider_float(
                        label="UI scale",
                        tag="uiScaleSlider",
                        min_value=MIN_UI_SCALE,
                        max_value=MAX_UI_SCALE,
                        default_value=uiScaleValue,
                        callback=handleUIScaleChange,
                    )
                    dpg.add_button(
                        label="Auto scale",
                        tag="uiScaleAutoButton",
                        callback=resetUIScaleToAuto,
                    )
                    dpg.add_button(
                        label="Clear previews",
                        tag="clearPreviewsButton",
                        callback=clearPreviews,
                        enabled=False,
                    )
                dpg.add_spacer(tag="headerRightSpacer")

            dpg.add_spacer(height=12)

            with dpg.group(tag="contentLayoutGroup", horizontal=True):
                dpg.add_spacer(tag="contentLeftSpacer")
                with dpg.child_window(
                    tag="contentContainer",
                    border=False,
                    no_scrollbar=True,
                ):
                    dpg.add_button(
                        label="Cancel video colorization",
                        tag="cancelColorizationButton",
                        height=50,
                        callback=cancelColorization,
                    )
                    dpg.add_progress_bar(tag="progressBar", overlay="0%")
                    dpg.add_text(tag="rgbi", default_value="Hover either preview to inspect RGB values.")
                    mediaDisplayHelper.buildUi(parent="contentContainer")
                    with dpg.group(
                        tag="logSection",
                    ):
                        pass
                    hideVideoColorizationUIItems()
                dpg.add_spacer(tag="contentRightSpacer")

        with dpg.window(
            label="Model not found",
            tag="modelMissingDialog",
            modal=True,
            show=False,
            no_resize=True,
            no_move=True,
            no_collapse=True,
            no_close=True,
            autosize=True,
        ):
            dpg.add_text("The model weights are required before colorization can start.")
            dpg.add_text(tag="modelMissingDialogMessage", default_value="", wrap=520)
            dpg.add_text(tag="modelMissingDialogStatus", default_value="", wrap=520)
            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Download model",
                    tag="downloadModelButton",
                    callback=startModelDownload,
                )
                dpg.add_button(
                    label="Open download page",
                    tag="openModelDownloadPageButton",
                    callback=openModelDownloadPage,
                )
                dpg.add_button(
                    label="Close",
                    callback=lambda: dpg.hide_item("modelMissingDialog"),
                )

        logger = Logger("logSection", logQueue=logQueue)
        mediaDisplayHelper.setLogger(logger)

        colorizer = Colorizer(logger, displayQueue=displayQueue, workerQueue=workQueue)
        colorizer.start()

        dpg.create_viewport(
            title=APP_WINDOW_TITLE,
            resizable=True,
            width=DEFAULT_VIEWPORT_WIDTH,
            height=DEFAULT_VIEWPORT_HEIGHT,
        )
        dpg.setup_dearpygui()
        dpg.show_viewport()
        dpg.set_primary_window("mainWindow", True)
        dpg.maximize_viewport()
        applyUIScale(uiScaleValue)
        syncMainWindowLayout()
        if not hasModelAssets():
            showModelMissingDialog()
        lastViewportSize = (
            dpg.get_viewport_client_width(),
            dpg.get_viewport_client_height(),
        )
        dpg.set_exit_callback(terminateProgram)

        while dpg.is_dearpygui_running():
            currentViewportSize = (
                dpg.get_viewport_client_width(),
                dpg.get_viewport_client_height(),
            )
            if currentViewportSize != lastViewportSize:
                requestLayoutSync()
                lastViewportSize = currentViewportSize

            processPendingLayout()
            logger.drainLogUpdates()
            drainDisplayUpdates()
            processModelDownloadEvents()
            processPendingPreviewClear()
            mediaDisplayHelper.update()
            syncPreviewControlState()

            if colorizer.videoColorizationInProgress.is_set():
                showVideoColorizationUIItems()
                updateProgressBar()
            else:
                hideVideoColorizationUIItems()

            dpg.render_dearpygui_frame()
        else:
            dpg.destroy_context()
    except Exception as e:
        print(e)
        if logger is not None:
            logger.logMsg("Main", str(e), "CRITICAL")
