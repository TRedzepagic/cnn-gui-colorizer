from dearpygui_ext import logger as DPGLOG
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

    def collectLogUpdates(self, colorizer):
        try:
            while not colorizer.terminated.is_set():
                if not self.logQueue.empty():
                    logUpdate = self.logQueue.get()
                    for messageLevel, message in logUpdate.retrieve().items():
                        if messageLevel == "INFO":
                            self.logInfo(message)
                        if messageLevel == "WARNING":
                            self.logWarning(message)
                        if messageLevel == "CRITICAL":
                            self.logCritical(message)
                        if messageLevel == "DEBUG":
                            self.logDebug(message)
        except Exception as e:
            print(e)