#!/usr/bin/env python3
import pyautogui
import multiprocessing
import dearpygui.dearpygui as dpg
import threading
import os
import glob

from queue import Queue as ThreadQueue
from multiprocessing import Queue as ProcessQueue

from colorizer import Colorizer
from logger import Logger
from work_object import ColorizationWorkObject
from video_player_helper import VideoPlayerHelper
from image_display_helper import ImageDisplayHelper

def enqueueWorkObject(path, type):
    """
        enqueueWorkObject(path, "IMAGE"/"VIDEO")
    """
    workObject = ColorizationWorkObject(path, type)
    colorizer.enqueue(workObject)

def callback(sender, app_data):
    try:
        dictWithPathAsKey = app_data.get("selections")
        for _, path in dictWithPathAsKey.items():
            extension = path.split(".")[1]
            imgExts = ["jpg", "jpeg", "bmp", "png"]
            vidExts = ["mp4", "avi"]
            if extension in imgExts + vidExts:
                if extension in imgExts:
                    enqueueWorkObject(path, "IMAGE")
                if extension in vidExts:
                    enqueueWorkObject(path, "VIDEO")
            else:
                msg = "Unsupported extension!"
                logger.logMsg("Main", msg, "WARNING")
    except Exception as e:
        msg = str(e)
        logger.logMsg("Main:callback", msg, "CRITICAL")


def collectDisplayUpdates():
    try:
        while not colorizer.terminated.is_set():
            if not displayQueue.empty():
                displayUpdate = displayQueue.get()
                for type, path in displayUpdate.retrieve().items():
                    if type == "IMAGE":
                        displayImageThread = threading.Thread(target=imageDisplayHelper.display, args=[path])
                        displayImageThread.start()
                    if type == "VIDEO":
                        displayVideoThread = threading.Thread(target=videoPlayerHelper.play, args=[path])
                        displayVideoThread.start()
    except Exception as e:
        msg = str(e)
        logger.logMsg("collectDisplayUpdates", msg, "CRITICAL")

def RGBInspect(rgbQueue):
    try:
        while True:
            posXY = pyautogui.position() 
            position = str(posXY)
            rgb = pyautogui.pixel(posXY[0], posXY[1])
            positionRGB = "{0}, {1}".format(position, rgb)
            rgbQueue.put(positionRGB)
    except Exception as e:
        print(e)

def removeRGBScreenshots():
    for filename in glob.glob('.screenshot*'):
        os.remove(filename)

def terminateProgram():
    try:
        imageDisplayHelper.terminateImageDisplayers()
        videoPlayerHelper.terminateVideoPlayers()
        colorizer.terminateColorizer()
        rgbInspectorProc.terminate()
        removeRGBScreenshots()
    except Exception as e:
        msg = str(e)
        logger.logMsg("terminateProgram", msg, "CRITICAL")

def cancelColorization():
    try:
        videoPlayerHelper.terminateVideoPlayers()
        colorizer.cancelVideoColorization()
    except Exception as e:
        msg = str(e)
        logger.logMsg("cancelColorization", msg, "CRITICAL")

def hideVideoColorizationUIItems():
    dpg.hide_item("cancelColorizationButton")
    dpg.hide_item("progressBar")

def showVideoColorizationUIItems():
    dpg.show_item("cancelColorizationButton")
    dpg.show_item("progressBar")  

def updateProgressBar():
    dpg.set_value("progressBar", colorizer.videoColorizationProgress)
    dpg.configure_item("progressBar", overlay=str(int(colorizer.videoColorizationProgress*100))+"%")

if __name__ == "__main__":
    try:
        logQueue = ThreadQueue()
        displayQueue = ThreadQueue()
        workQueue = ThreadQueue()
        rgbQueue = ProcessQueue()

        videoPlayerHelper = VideoPlayerHelper()
        imageDisplayHelper = ImageDisplayHelper()
        
        dpg.create_context()

        with dpg.file_dialog(directory_selector=False, show=False, callback=callback, tag="file_dialog_tag"):
            dpg.add_file_extension(".*")
            dpg.add_file_extension("", color=(150, 255, 150, 255))
            dpg.add_file_extension(".jpeg", color=(0, 255, 0, 255))
            dpg.add_file_extension(".jpg", color=(0, 255, 0, 255))
            dpg.add_file_extension(".png", color=(0, 255, 0, 255))
            dpg.add_file_extension(".bmp", color=(0, 255, 0, 255))
            dpg.add_file_extension(".mp4", color=(0, 255, 0, 255))
            dpg.add_file_extension(".avi", color=(0, 255, 0, 255))


        with dpg.window(no_title_bar=False, no_close=False, no_bring_to_front_on_focus=False, no_move=False, width=1280, height=720) as root:
            dpg.add_button(label="Please select your image or video to colorize...", width=1280, height=50, callback=lambda: dpg.show_item("file_dialog_tag"))
            dpg.add_text(tag="rgbi", default_value="Loading RGB Inspector...")
            dpg.add_button(label="Cancel video colorization", tag="cancelColorizationButton", width=1280, height=50, callback=cancelColorization)
            dpg.add_progress_bar(tag="progressBar", width=1280, overlay="0%")
            hideVideoColorizationUIItems()
        
        logger = Logger(root, logQueue=logQueue)    
        colorizer = Colorizer(logger, displayQueue=displayQueue, workerQueue=workQueue)
        colorizer.start()

        # Log messages from program to GUI
        logThread = threading.Thread(target=logger.collectLogUpdates, args=[colorizer])
        logThread.start()

        # Displaying images and videos
        displayThread = threading.Thread(target=collectDisplayUpdates, args=[])
        displayThread.start()

        # RGB information on mouse hover process
        rgbInspectorProc = multiprocessing.Process(target=RGBInspect, args=[rgbQueue])
        rgbInspectorProc.start()
        
        dpg.create_viewport(title='Image & Video Colorizer (DearPyGUI, OpenCV, CNN)', resizable=True, width=1280, height=720)
        dpg.setup_dearpygui()
        dpg.show_viewport()
        dpg.set_exit_callback(terminateProgram)
        while dpg.is_dearpygui_running():             
            if not rgbQueue.empty():
                rgbInfo = rgbQueue.get()
                dpg.set_value("rgbi", rgbInfo)

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
        msg = str(e)
        logger.logMsg("Main", msg, "CRITICAL")