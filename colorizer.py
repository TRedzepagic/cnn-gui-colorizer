import os
import cv2
import re
import time
from display_message import DisplayMessage
from threading import Lock, Thread, Event
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
        self.vidLock = Lock()

        self.imgNeuralNet = None
        self.vidNeuralNet = None
       
        self._colorizedVideoFramesPath = "./colorizedFrames"

        self.logger = logger
        self.displayQueue = displayQueue
        self.workerQueue = workerQueue

        self.videoColorizationProgress = 0

        self._setupOutputFolders()
    
    def initImageNeuralNetwork(self):
        if self.imgNeuralNet is None:
            self.imgNeuralNet = NeuralNet()
    
    def initVideoNeuralNetwork(self):
        if self.vidNeuralNet is None:
            self.vidNeuralNet = NeuralNet()

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
        if savePathType == "IMG":
            path = pathIn.replace("bwImages", "colorizedImages")
        if savePathType == "VID":
            path = pathIn.replace("bwVideos", "colorizedVideos")
        splitPath = path.split(".")
        savePath = splitPath[0]+"_colorized"+"."+splitPath[1]
        return savePath

    def _cleanupPreviousVideoFrames(self):
        try:
            framePath = self.getColorizedVideoFramesPath()
            frames = os.listdir(framePath)
            msg = "Deleting frames in: {0}".format(framePath)
            self.logger.logMsg("Colorizer", msg)
            for frame in frames:
                os.remove(framePath + "/" + frame)
        except Exception as e:
            raise e
    
    def signalGUIToDisplayItem(self, path, type):
        """
            signalGUIToDisplayItem(path, "IMAGE"/"VIDEO")
        """
        displaySignal = DisplayMessage(path, type)
        self.displayQueue.put(displaySignal)

    def colorizeBWImage(self, path):
        with self.imgLock:
            try:
                self.initImageNeuralNetwork()
                msg = "Colorizing: {0}...".format(path)
                self.logger.logMsg("Colorizer", msg)

                # Signal GUI to display BW Image
                self.signalGUIToDisplayItem(path, "IMAGE")

                image = cv2.imread(path)
                colorized = self.imgNeuralNet.colorize(image)
                
                # splitPath will evaluate to [NAME, EXTENSION]
                savePath = self.createSavePath(path)
                cv2.imwrite(savePath, colorized)

                msg = "Image colorization complete. Saving image to {0}.".format(savePath)
                self.logger.logMsg("Colorizer", msg)

                # Signal GUI to display color Image
                self.signalGUIToDisplayItem(savePath, "IMAGE")
            except Exception as e:
                msg = str(e)
                self.logger.logMsg("Colorizer", msg, "CRITICAL")
            finally:
                self.imgNeuralNet = None
        return 

    def colorizeBWVideo(self, path):
        with self.vidLock:
            try:
                self.initVideoNeuralNetwork()
                self._cleanupPreviousVideoFrames()
                self.videoColorizationInProgress.set()
                vid = cv2.VideoCapture(path)
                vidFPS = vid.get(cv2.CAP_PROP_FPS)
                frameCount = vid.get(cv2.CAP_PROP_FRAME_COUNT)
                count = 0

                # Signal GUI to display the BW Video
                self.signalGUIToDisplayItem(path, "VIDEO")

                msg = "Reading video file: {0}...".format(path)
                self.logger.logMsg("Colorizer", msg)

                lastProgressSignal = 0
                while True:
                    if self.terminated.is_set() or self.videoColorizationCanceled.is_set():
                        self._cleanupPreviousVideoFrames()
                        break
                    if count % 5 == 0:
                        msg = "Processing frame {0}/{1} of: {2}".format(str(count), frameCount, path)
                        self.logger.logMsg("Colorizer", msg)

                    timeATM = int(time.time())
                    # Update every 3 seconds
                    if timeATM - lastProgressSignal >= 3:
                        lastProgressSignal = timeATM
                        self.videoColorizationProgress = (count/frameCount)

                    ret, frame = vid.read()
                    if not ret:
                        break
                    colorizedFrame = self.vidNeuralNet.colorize(frame)
                    cv2.imwrite("./colorizedFrames/%d.jpg" % count, colorizedFrame)
                    count += 1

                if not self.videoColorizationCanceled.is_set():
                    savePath = self.createSavePath(path, savePathType="VID")
                    self._convertFramesToVideo("./colorizedFrames/", savePath, vidFPS)
                    self.signalGUIToDisplayItem(savePath, "VIDEO")
                else:
                    msg = "Video Colorization canceled."
                    self.logger.logMsg("Colorizer", msg, "WARNING")
            except Exception as e:
                msg = str(e)
                self.logger.logMsg(msg, "CRITICAL")
            finally:
                vid.release()
                cv2.destroyAllWindows()
                self.videoColorizationInProgress.clear()
                self.videoColorizationCanceled.clear()
                self.videoColorizationProgress = 0
                self.vidNeuralNet = None
        return
    
    def cancelVideoColorization(self):
        msg = "Canceling video colorization..."
        self.logger.logMsg("Colorizer", msg)
        self.videoColorizationCanceled.set()

    def _convertFramesToVideo(self, pathIn, pathOut, fps):
        msg = "Collecting frames to video file..."
        self.logger.logMsg("Colorizer", msg)

        fileNames = os.listdir(pathIn)
        fileNames.sort(key=lambda f: int(re.sub('\D', '', f)))
        
        frameArray = []
        for file in fileNames:
            framePath = pathIn + file
            frame = cv2.imread(framePath)
            height, width, layers = frame.shape
            size = (width,height)
            frameArray.append(frame)

        videoWriter = cv2.VideoWriter(pathOut,cv2.VideoWriter_fourcc(*'mp4v'), fps, size)
        for frame in frameArray:
            videoWriter.write(frame)
        
        msg = "Video colorization complete."
        self.logger.logMsg("Colorizer", msg)   
        
        videoWriter.release()
        return      

    def run(self):
        try:
            while not self.terminated.is_set():
                if not self.workerQueue.empty():
                    # Get object paths from GUI
                    workObject = self.workerQueue.get() 
                    for type, path in workObject.retrieve().items():
                        msg = "Got {0}:{1}".format(type,path)
                        self.logger.logMsg("Colorizer", msg)   
                        if type == "IMAGE":
                            clrThr = Thread(target=self.colorizeBWImage, args=[path])
                            clrThr.start()
                        if type == "VIDEO":
                            if self.videoColorizationInProgress.is_set():
                                msg = "A video is already being colorized! Please wait for it to finish, then try again!...".format(path)
                                self.logger.logMsg("Colorizer", msg, "CRITICAL")
                                continue
                            vidThr = Thread(target=self.colorizeBWVideo, args=[path])
                            vidThr.start()
        except Exception as e:
            msg = str(e)
            self.logger.logMsg("Colorizer", msg, "CRITICAL")

    def enqueue(self, object):
        self.workerQueue.put(object)

    def terminateColorizer(self):
        self.terminated.set()