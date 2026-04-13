import os
import cv2
import re
from queue import Empty
from display_message import DisplayMessage
from threading import Lock, Thread, Event
from memory_utils import trimProcessMemory
from neural_net import NeuralNet

class Colorizer(Thread):
    """
        This class represents an image/video colorizer.
    """
    def __init__(self, logger, displayQueue, workerQueue) -> None:
        Thread.__init__(self)
        self.videoColorizationInProgress = Event()
        self.terminated = Event()
        self.videoColorizationCanceled = Event()

        self.imgLock = Lock()
        self.videoLock = Lock()
       
        self._colorizedVideoFramesPath = "./colorizedFrames"

        self.logger = logger
        self.displayQueue = displayQueue
        self.workerQueue = workerQueue

        self.videoColorizationProgress = 0

        self._setupOutputFolders()

    def _setupOutputFolders(self):
        outputFolders = [
            "./colorizedFrames",
            "./colorizedImages",
            "./colorizedVideos"
        ]
        for outputFolder in outputFolders:
            if not os.path.exists(outputFolder):
                os.makedirs(outputFolder)
    
    def getColorizedVideoFramesPath(self):
        return self._colorizedVideoFramesPath

    def createSavePath(self, pathIn, savePathType="IMG"):
        fileName, extension = os.path.splitext(os.path.basename(pathIn))
        if savePathType == "IMG":
            outputDirectory = os.path.dirname(pathIn).replace("bwImages", "colorizedImages")
            if outputDirectory == os.path.dirname(pathIn):
                outputDirectory = "./colorizedImages"
        if savePathType == "VID":
            outputDirectory = os.path.dirname(pathIn).replace("bwVideos", "colorizedVideos")
            if outputDirectory == os.path.dirname(pathIn):
                outputDirectory = "./colorizedVideos"

        os.makedirs(outputDirectory, exist_ok=True)
        savePath = os.path.join(outputDirectory, fileName + "_colorized" + extension)
        return savePath

    def _cleanupPreviousVideoFrames(self):
        framePath = self.getColorizedVideoFramesPath()
        msg = "Deleting frames in: {0}".format(framePath)
        self.logger.logMsg("Colorizer", msg)
        for frame in os.scandir(framePath):
            if frame.is_file():
                os.remove(frame.path)
    
    def signalGUIToDisplayItem(self, path, type):
        """
            signalGUIToDisplayItem(path, "IMAGE"/"VIDEO")
        """
        displaySignal = DisplayMessage(path, type)
        self.displayQueue.put(displaySignal)

    def colorizeBWImage(self, path):
        with self.imgLock:
            image = None
            colorizedImage = None
            NNet = None
            try:
                msg = "Colorizing: {0}...".format(path)
                self.logger.logMsg("Colorizer", msg)

                # Signal GUI to display BW Image
                self.signalGUIToDisplayItem(path, "IMAGE")

                image = cv2.imread(path)
                if image is None:
                    raise ValueError("Unable to read image: {0}".format(path))

                NNet = NeuralNet()
                colorizedImage = NNet.colorize(image)
                
                # splitPath will evaluate to [NAME, EXTENSION]
                savePath = self.createSavePath(path)
                cv2.imwrite(savePath, colorizedImage)

                msg = "Image colorization complete. Saving image to {0}.".format(savePath)
                self.logger.logMsg("Colorizer", msg)

                # Signal GUI to display color Image
                self.signalGUIToDisplayItem(savePath, "IMAGE")
            except Exception as e:
                msg = str(e)
                self.logger.logMsg("Colorizer", msg, "CRITICAL")
            finally:
                image = None
                colorizedImage = None
                NNet = None
                trimProcessMemory()
            return 

    def colorizeBWVideo(self, path):
        with self.videoLock:
            vid = None
            NNet = None
            try:
                NNet = NeuralNet()
                self._cleanupPreviousVideoFrames()
                self.videoColorizationInProgress.set()
                vid = cv2.VideoCapture(path)
                if not vid.isOpened():
                    raise ValueError("Unable to open video: {0}".format(path))

                vidFPS = vid.get(cv2.CAP_PROP_FPS) or 24
                frameCount = int(vid.get(cv2.CAP_PROP_FRAME_COUNT))
                count = 0

                # Signal GUI to display the BW Video
                self.signalGUIToDisplayItem(path, "VIDEO")

                msg = "Reading video file: {0}...".format(path)
                self.logger.logMsg("Colorizer", msg)

                while True:
                    if self.terminated.is_set() or self.videoColorizationCanceled.is_set():
                        break
                    if count % 5 == 0:
                        msg = "Processing frame {0}/{1} of: {2}".format(str(count), frameCount, path)
                        self.logger.logMsg("Colorizer", msg)

                    ret, frame = vid.read()
                    if not ret:
                        break

                    colorizedFrame = NNet.colorize(frame)

                    cv2.imwrite("./colorizedFrames/{0}.jpg".format(str(count)), colorizedFrame)
                    count += 1
                    if frameCount > 0:
                        self.videoColorizationProgress = min(count / frameCount, 1)

                if not self.videoColorizationCanceled.is_set() and not self.terminated.is_set():
                    savePath = self.createSavePath(path, savePathType="VID")
                    self._convertFramesToVideo("./colorizedFrames/", savePath, vidFPS)
                    self.signalGUIToDisplayItem(savePath, "VIDEO")
                else:
                    msg = "Video Colorization canceled."
                    self.logger.logMsg("Colorizer", msg, "WARNING")
            except Exception as e:
                msg = str(e)
                self.logger.logMsg("Colorizer", msg, "CRITICAL")
            finally:
                if vid is not None:
                    vid.release()
                self._cleanupPreviousVideoFrames()
                self.videoColorizationInProgress.clear()
                self.videoColorizationCanceled.clear()
                self.videoColorizationProgress = 0
                NNet = None
                trimProcessMemory()
            return
    
    def cancelVideoColorization(self):
        msg = "Canceling video colorization..."
        self.logger.logMsg("Colorizer", msg)
        self.videoColorizationCanceled.set()

    def _convertFramesToVideo(self, pathIn, pathOut, fps):
        msg = "Collecting frames to video file..."
        self.logger.logMsg("Colorizer", msg)

        fileNames = os.listdir(pathIn)
        fileNames.sort(key=lambda f: int(re.sub(r"\D", "", f)))

        if not fileNames:
            raise ValueError("No colorized frames were generated for {0}".format(pathOut))

        firstFramePath = os.path.join(pathIn, fileNames[0])
        firstFrame = cv2.imread(firstFramePath)
        if firstFrame is None:
            raise ValueError("Unable to read generated frame: {0}".format(firstFramePath))

        height, width = firstFrame.shape[:2]
        size = (width, height)
        videoWriter = cv2.VideoWriter(pathOut, cv2.VideoWriter_fourcc(*'mp4v'), fps, size)
        try:
            videoWriter.write(firstFrame)
            for file in fileNames[1:]:
                framePath = os.path.join(pathIn, file)
                frame = cv2.imread(framePath)
                if frame is None:
                    raise ValueError("Unable to read generated frame: {0}".format(framePath))
                videoWriter.write(frame)
        finally:
            videoWriter.release()

        msg = "Video colorization complete."
        self.logger.logMsg("Colorizer", msg)   
        return      

    def run(self):
        try:
            while not self.terminated.is_set():
                try:
                    # Get object paths from GUI
                    workObject = self.workerQueue.get(timeout=0.1)
                except Empty:
                    continue

                for type, path in workObject.retrieve().items():
                    msg = "Got {0}:{1}".format(type,path)
                    self.logger.logMsg("Colorizer", msg)   
                    if type == "IMAGE":
                        clrThr = Thread(target=self.colorizeBWImage, args=[path], daemon=True)
                        clrThr.start()
                    if type == "VIDEO":
                        if self.videoColorizationInProgress.is_set():
                            msg = "A video is already being colorized! Please wait for it to finish, then try again!...".format(path)
                            self.logger.logMsg("Colorizer", msg, "CRITICAL")
                            continue
                        vidThr = Thread(target=self.colorizeBWVideo, args=[path], daemon=True)
                        vidThr.start()
        except Exception as e:
            msg = str(e)
            self.logger.logMsg("Colorizer", msg, "CRITICAL")

    def enqueue(self, object):
        self.workerQueue.put(object)

    def terminateColorizer(self):
        self.terminated.set()
