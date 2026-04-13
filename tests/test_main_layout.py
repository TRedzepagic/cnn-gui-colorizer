import unittest
from unittest import mock
import queue

import main
from main import calculateLayoutMetrics


class MainLayoutTests(unittest.TestCase):
    def tearDown(self):
        main.uiScaleMode = "auto"
        main.uiScaleValue = 1.0
        main.pendingUIScaleValue = None
        main.lastViewportResizeAt = 0.0
        main.layoutSyncPending = False
        main.previewClearPending = False
        main.modelDownloadQueue = None
        main.modelDownloadInProgress = False
        main.modelDownloadStatusMessage = ""
        main.modelDownloadProgressValue = 0.0
        main.modelDownloadProgressOverlay = "0%"
        main.displayQueue = None
        main.colorizer = None
        main.mediaDisplayHelper = None
        main.logger = None

    def testCalculateLayoutMetricsCentersControlColumn(self):
        metrics = calculateLayoutMetrics(1800, 1200, 1.0)
        self.assertEqual(metrics["controlColumnWidth"], int(1800 * 0.33))
        self.assertEqual(metrics["controlSideWidth"] * 2 + metrics["controlColumnWidth"], 1800)

    def testCalculateLayoutMetricsKeepsContentWithinSharedMargins(self):
        metrics = calculateLayoutMetrics(1600, 1000, 1.5)
        self.assertEqual(metrics["contentSideWidth"] * 2 + metrics["contentWidth"], 1600)
        self.assertGreaterEqual(metrics["logSectionHeight"], 180)
        self.assertGreaterEqual(metrics["comparisonHeight"], 300)

    def testGetAutoUIScaleUsesConservativeScaleForFrozenLinuxBundle(self):
        with mock.patch("main.isFrozenLinuxApp", return_value=True):
            self.assertEqual(main.getAutoUIScale(3840, 2160), 1.0)

    def testHandleUIScaleChangeDefersLayoutMutation(self):
        with mock.patch("main.applyUIScale") as applyUIScaleMock:
            with mock.patch("main.syncMainWindowLayout") as syncLayoutMock:
                main.handleUIScaleChange(None, 1.8)

        self.assertEqual(main.uiScaleMode, "manual")
        self.assertEqual(main.pendingUIScaleValue, 1.8)
        self.assertTrue(main.layoutSyncPending)
        applyUIScaleMock.assert_not_called()
        syncLayoutMock.assert_not_called()

    def testResetUIScaleToAutoDefersLayoutMutation(self):
        main.pendingUIScaleValue = 1.9

        with mock.patch("main.syncMainWindowLayout") as syncLayoutMock:
            main.resetUIScaleToAuto()

        self.assertEqual(main.uiScaleMode, "auto")
        self.assertIsNone(main.pendingUIScaleValue)
        self.assertTrue(main.layoutSyncPending)
        syncLayoutMock.assert_not_called()

    def testProcessPendingLayoutAppliesQueuedManualScaleOnMainLoop(self):
        main.pendingUIScaleValue = 2.1
        main.layoutSyncPending = True

        with mock.patch("main.applyUIScale", return_value=2.1) as applyUIScaleMock:
            with mock.patch("main.syncMainWindowLayout") as syncLayoutMock:
                main.processPendingLayout()

        applyUIScaleMock.assert_called_once_with(2.1, updateSlider=False)
        syncLayoutMock.assert_called_once_with()
        self.assertEqual(main.uiScaleValue, 2.1)
        self.assertIsNone(main.pendingUIScaleValue)
        self.assertFalse(main.layoutSyncPending)

    def testProcessPendingLayoutWaitsForViewportResizeToSettle(self):
        main.layoutSyncPending = True
        main.lastViewportResizeAt = 10.0

        with mock.patch("main.time.monotonic", return_value=10.05):
            with mock.patch("main.syncMainWindowLayout") as syncLayoutMock:
                main.processPendingLayout()

        syncLayoutMock.assert_not_called()
        self.assertTrue(main.layoutSyncPending)

    def testCenterModelMissingDialogUsesViewportCenter(self):
        with mock.patch("main.dpg.does_item_exist", return_value=True):
            with mock.patch("main.dpg.get_viewport_client_width", return_value=1400):
                with mock.patch("main.dpg.get_viewport_client_height", return_value=900):
                    with mock.patch("main.dpg.set_item_pos") as setItemPosMock:
                        main.centerModelMissingDialog()

        setItemPosMock.assert_called_once_with(
            "modelMissingDialog",
            [
                int((1400 - main.MODEL_DIALOG_WINDOW_WIDTH) / 2),
                int((900 - main.MODEL_DIALOG_WINDOW_HEIGHT) / 2),
            ],
        )

    def testClearPreviewsDefersCleanupToMainLoop(self):
        with mock.patch("main.mediaDisplayHelper") as mediaDisplayHelperMock:
            main.clearPreviews()
            self.assertTrue(main.previewClearPending)

            main.processPendingPreviewClear()

        mediaDisplayHelperMock.clearPreviews.assert_called_once_with()
        self.assertFalse(main.previewClearPending)

    def testClearPreviewsRefusesWhileVideoColorizationIsActive(self):
        main.colorizer = mock.Mock()
        main.colorizer.videoColorizationInProgress.is_set.return_value = True
        main.logger = mock.Mock()

        main.clearPreviews()

        self.assertFalse(main.previewClearPending)
        main.logger.logMsg.assert_called_once_with(
            "Main",
            "Cancel the active video colorization before clearing previews.",
            "WARNING",
        )

    def testProcessPendingPreviewClearFlushesDisplayQueue(self):
        main.previewClearPending = True
        main.displayQueue = queue.Queue()
        main.displayQueue.put(object())
        main.displayQueue.put(object())
        main.mediaDisplayHelper = mock.Mock()

        main.processPendingPreviewClear()

        main.mediaDisplayHelper.clearPreviews.assert_called_once_with()
        self.assertTrue(main.displayQueue.empty())
        self.assertFalse(main.previewClearPending)

    def testSyncPreviewControlStateEnablesClearButtonWhenAnyPreviewExists(self):
        main.mediaDisplayHelper = mock.Mock()
        main.mediaDisplayHelper.hasAnyPreview.return_value = True
        main.mediaDisplayHelper.hasSourcePreview.return_value = False
        main.mediaDisplayHelper.hasResultPreview.return_value = False

        with mock.patch("main.dpg.does_item_exist", return_value=True):
            with mock.patch("main.dpg.configure_item") as configureItemMock:
                main.syncPreviewControlState()

        self.assertEqual(configureItemMock.call_count, 2)
        configureItemMock.assert_any_call("selectMediaButton", label="Select image or video to colorize...")
        configureItemMock.assert_any_call("clearPreviewsButton", enabled=True)

    def testSyncPreviewControlStateDisablesClearButtonWhileVideoColorizationIsActive(self):
        main.mediaDisplayHelper = mock.Mock()
        main.mediaDisplayHelper.hasAnyPreview.return_value = True
        main.mediaDisplayHelper.hasSourcePreview.return_value = False
        main.mediaDisplayHelper.hasResultPreview.return_value = False
        main.colorizer = mock.Mock()
        main.colorizer.videoColorizationInProgress.is_set.return_value = True

        with mock.patch("main.dpg.does_item_exist", return_value=True):
            with mock.patch("main.dpg.configure_item") as configureItemMock:
                main.syncPreviewControlState()

        self.assertEqual(configureItemMock.call_count, 2)
        configureItemMock.assert_any_call("selectMediaButton", label="Select image or video to colorize...")
        configureItemMock.assert_any_call("clearPreviewsButton", enabled=False)

    def testCallbackListsSupportedExtensionsForUnsupportedFiles(self):
        main.logger = mock.Mock()

        main.callback(None, {"selections": {"bad": "/tmp/example.txt"}})

        main.logger.logMsg.assert_called_once_with(
            "Main",
            "Unsupported extension '.txt'. Supported extensions: .jpg, .jpeg, .bmp, .png, .mp4, .avi",
            "WARNING",
        )

    def testEnqueueWorkObjectShowsModelDialogWhenModelIsMissing(self):
        main.colorizer = mock.Mock()

        with mock.patch("main.hasModelAssets", return_value=False):
            with mock.patch("main.showModelMissingDialog") as showDialogMock:
                result = main.enqueueWorkObject("/tmp/example.jpg", "IMAGE")

        self.assertFalse(result)
        main.colorizer.enqueue.assert_not_called()
        showDialogMock.assert_called_once_with()

    def testHandlePrimaryActionShowsModelDialogBeforeOpeningPicker(self):
        main.mediaDisplayHelper = mock.Mock()
        main.mediaDisplayHelper.hasSourcePreview.return_value = False
        main.mediaDisplayHelper.hasResultPreview.return_value = False

        with mock.patch("main.hasModelAssets", return_value=False):
            with mock.patch("main.showModelMissingDialog") as showDialogMock:
                with mock.patch("main.dpg.show_item") as showItemMock:
                    main.handlePrimaryAction()

        showDialogMock.assert_called_once_with()
        showItemMock.assert_not_called()

    def testProcessModelDownloadEventsHidesDialogAfterSuccessfulDownload(self):
        main.modelDownloadQueue = queue.Queue()
        main.modelDownloadQueue.put({"status": "success", "downloadedAssets": ["caffemodel"]})
        main.modelDownloadInProgress = True
        main.logger = mock.Mock()

        with mock.patch("main.hasModelAssets", return_value=True):
            with mock.patch("main.syncModelDialogState") as syncDialogMock:
                with mock.patch("main.dpg.does_item_exist", return_value=True):
                    with mock.patch("main.dpg.hide_item") as hideItemMock:
                        main.processModelDownloadEvents()

        self.assertFalse(main.modelDownloadInProgress)
        self.assertEqual(main.modelDownloadStatusMessage, "")
        syncDialogMock.assert_called_once_with()
        hideItemMock.assert_called_once_with("modelMissingDialog")
        main.logger.logMsg.assert_called_once_with("Main", "Model download complete.", "INFO")

    def testProcessModelDownloadEventsShowsErrorStatusAfterFailure(self):
        main.modelDownloadQueue = queue.Queue()
        main.modelDownloadQueue.put({"status": "error", "message": "network down"})
        main.modelDownloadInProgress = True
        main.logger = mock.Mock()

        with mock.patch("main.showModelMissingDialog") as showDialogMock:
            main.processModelDownloadEvents()

        self.assertFalse(main.modelDownloadInProgress)
        showDialogMock.assert_called_once_with("Model download failed: network down")
        main.logger.logMsg.assert_called_once_with(
            "Main",
            "Model download failed: network down",
            "CRITICAL",
        )

    def testProcessModelDownloadEventsUpdatesProgressState(self):
        main.modelDownloadQueue = queue.Queue()
        main.modelDownloadQueue.put(
            {
                "status": "progress",
                "progressValue": 0.5,
                "overlay": "50% (61.5 MB / 123.0 MB)",
            }
        )
        main.modelDownloadInProgress = True

        with mock.patch("main.syncModelDialogState") as syncDialogMock:
            main.processModelDownloadEvents()

        self.assertEqual(main.modelDownloadProgressValue, 0.5)
        self.assertEqual(main.modelDownloadProgressOverlay, "50% (61.5 MB / 123.0 MB)")
        syncDialogMock.assert_called_once_with()
        self.assertTrue(main.modelDownloadInProgress)

    def testCopyModelDownloadLinkUsesClipboard(self):
        with mock.patch("main.dpg.set_clipboard_text") as setClipboardTextMock:
            with mock.patch("main.syncModelDialogState") as syncDialogMock:
                main.copyModelDownloadLink()

        setClipboardTextMock.assert_called_once_with(main.MODEL_MANUAL_DOWNLOAD_URL)
        self.assertEqual(
            main.modelDownloadStatusMessage,
            "Copied the model download link to the clipboard.",
        )
        syncDialogMock.assert_called_once_with()

    def testGetPrimaryActionLabelUsesStartColorizationWhenSourcePreviewHasNoResult(self):
        main.mediaDisplayHelper = mock.Mock()
        main.mediaDisplayHelper.hasSourcePreview.return_value = True
        main.mediaDisplayHelper.hasResultPreview.return_value = False

        self.assertEqual(main.getPrimaryActionLabel(), "Start colorization")

    def testHandlePrimaryActionEnqueuesLoadedSourceWhenRestartIsAvailable(self):
        main.mediaDisplayHelper = mock.Mock()
        main.mediaDisplayHelper.hasSourcePreview.return_value = True
        main.mediaDisplayHelper.hasResultPreview.return_value = False
        main.mediaDisplayHelper.getSourceMedia.return_value = {
            "path": "/tmp/example.mp4",
            "mediaType": "VIDEO",
        }

        with mock.patch("main.enqueueWorkObject") as enqueueWorkObjectMock:
            with mock.patch("main.dpg.show_item") as showItemMock:
                main.handlePrimaryAction()

        enqueueWorkObjectMock.assert_called_once_with("/tmp/example.mp4", "VIDEO")
        showItemMock.assert_not_called()

    def testHandlePrimaryActionShowsPickerWhenResultPreviewAlreadyExistsAndExamplesExist(self):
        main.mediaDisplayHelper = mock.Mock()
        main.mediaDisplayHelper.hasSourcePreview.return_value = True
        main.mediaDisplayHelper.hasResultPreview.return_value = True

        with mock.patch("main.ensureModelAvailable", return_value=True):
            with mock.patch("main.enqueueWorkObject") as enqueueWorkObjectMock:
                with mock.patch("main.getExamplesDirectory", return_value="/tmp/examples"):
                    with mock.patch("main.dpg.configure_item") as configureItemMock:
                        with mock.patch("main.dpg.show_item") as showItemMock:
                            main.handlePrimaryAction()

        enqueueWorkObjectMock.assert_not_called()
        configureItemMock.assert_called_once_with("file_dialog_tag", default_path="/tmp/examples")
        showItemMock.assert_called_once_with("file_dialog_tag")

    def testHandlePrimaryActionShowsPickerWithoutExamplesDirectory(self):
        main.mediaDisplayHelper = mock.Mock()
        main.mediaDisplayHelper.hasSourcePreview.return_value = False
        main.mediaDisplayHelper.hasResultPreview.return_value = False

        with mock.patch("main.ensureModelAvailable", return_value=True):
            with mock.patch("main.getExamplesDirectory", return_value=None):
                with mock.patch("main.dpg.configure_item") as configureItemMock:
                    with mock.patch("main.dpg.show_item") as showItemMock:
                        main.handlePrimaryAction()

        configureItemMock.assert_not_called()
        showItemMock.assert_called_once_with("file_dialog_tag")

    def testGetExamplesDirectoryUsesBundledExamplesPath(self):
        with mock.patch("main.resolveResourcePath", return_value="/tmp/examples"):
            with mock.patch("main.os.path.isdir", return_value=True):
                examplesDirectory = main.getExamplesDirectory()

        self.assertEqual(examplesDirectory, "/tmp/examples")

    def testHandlePrimaryActionShowsPickerWhenResultPreviewAlreadyExistsWithoutExamples(self):
        main.mediaDisplayHelper = mock.Mock()
        main.mediaDisplayHelper.hasSourcePreview.return_value = True
        main.mediaDisplayHelper.hasResultPreview.return_value = True

        with mock.patch("main.ensureModelAvailable", return_value=True):
            with mock.patch("main.enqueueWorkObject") as enqueueWorkObjectMock:
                with mock.patch("main.getExamplesDirectory", return_value=None):
                    with mock.patch("main.dpg.configure_item") as configureItemMock:
                        with mock.patch("main.dpg.show_item") as showItemMock:
                            main.handlePrimaryAction()

        enqueueWorkObjectMock.assert_not_called()
        configureItemMock.assert_not_called()
        showItemMock.assert_called_once_with("file_dialog_tag")


if __name__ == "__main__":
    unittest.main()
