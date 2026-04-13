import dearpygui.dearpygui as dpg
from dearpygui_ext import logger as DPGLOG
from queue import Empty

LOGGER_HEADER_RESERVE_HEIGHT = 52


class LogMessage:
    def __init__(self, msg, msgLvl) -> None:
        """
            Log levels:
                - INFO
                - CRITICAL
                - WARNING
                - DEBUG
        """
        self.message = {}
        self.message[msgLvl] = msg
    
    def retrieve(self):
        return self.message

class Logger():
    """
        Logging wrapper for DPG's log. 
        Specify parent when creating log.

        Usage:
            - logger = Logger(root)    
    """
    def __init__(self,parent, logQueue) -> None:
        self.logger = DPGLOG.mvLogger(parent=parent)
        self.logQueue = logQueue
        children = dpg.get_item_children(self.logger.window_id, 1) or []
        self.headerGroupId = children[0] if len(children) > 0 else None
        self.filterInputId = children[1] if len(children) > 1 else None
        self.childWindowId = children[2] if len(children) > 2 else None
        self.autoScrollCheckboxId = None
        self.clearButtonId = None

        if self.headerGroupId is not None:
            headerChildren = dpg.get_item_children(self.headerGroupId, 1) or []
            self.autoScrollCheckboxId = headerChildren[0] if len(headerChildren) > 0 else None
            self.clearButtonId = headerChildren[1] if len(headerChildren) > 1 else None

        if self.filterInputId is not None:
            dpg.configure_item(self.filterInputId, label="", hint="Filter logs")
        if self.childWindowId is not None:
            dpg.configure_item(self.childWindowId, autosize_x=False, autosize_y=False)
        if self.clearButtonId is not None:
            dpg.configure_item(self.clearButtonId, width=88, small=True)
    def log(self, msg):
        self.logger.log(msg)
    def logInfo(self, msg):
        self.logger.log_info(msg)
    def logCritical(self, msg):
        self.logger.log_critical(msg)
    def logWarning(self, msg):
        self.logger.log_warning(msg)
    def logDebug(self, msg):
        self.logger.log_debug(msg)
    def clearLog(self):
        self.logger.clear_log()
    def toggleAutoScroll(self, flag=True):
        self.logger.auto_scroll(flag)

    def logMsg(self, source, msg, loglevel="INFO"):
        """
            Logs to log queue.
            
            Log levels:
                - INFO
                - CRITICAL
                - WARNING
                - DEBUG

            Usage:
                -   self.log(msg, "LEVEL")
            
            Output:
                -   "[logLevel]: {Source}: {message}"
        """
        msg = "{0}: {1}".format(str(source), str(msg))
        logMsg = LogMessage(msg, loglevel)
        self.logQueue.put(logMsg)

    def _renderLogUpdate(self, logUpdate):
        for messageLevel, message in logUpdate.retrieve().items():
            if messageLevel == "INFO":
                self.logInfo(message)
            if messageLevel == "WARNING":
                self.logWarning(message)
            if messageLevel == "CRITICAL":
                self.logCritical(message)
            if messageLevel == "DEBUG":
                self.logDebug(message)

    def syncLayout(self, width, height):
        innerWidth = max(int(width) - 16, 120)
        logHeight = max(int(height), 160)
        clearButtonWidth = min(max(int(innerWidth * 0.12), 72), 104)

        dpg.configure_item(self.logger.window_id, width=width, height=logHeight)
        if self.headerGroupId is None or self.filterInputId is None or self.childWindowId is None:
            return

        dpg.set_item_width(self.filterInputId, innerWidth)
        dpg.configure_item(
            self.childWindowId,
            width=innerWidth,
            height=max(logHeight - LOGGER_HEADER_RESERVE_HEIGHT, 100),
        )
        if self.clearButtonId is not None:
            dpg.configure_item(self.clearButtonId, width=clearButtonWidth)

    def drainLogUpdates(self):
        try:
            while True:
                try:
                    logUpdate = self.logQueue.get_nowait()
                except Empty:
                    break

                self._renderLogUpdate(logUpdate)
        except Exception as e:
            print(e)

    def collectLogUpdates(self, colorizer):
        try:
            while not colorizer.terminated.is_set():
                try:
                    logUpdate = self.logQueue.get(timeout=0.1)
                except Empty:
                    continue

                self._renderLogUpdate(logUpdate)
        except Exception as e:
            print(e)
