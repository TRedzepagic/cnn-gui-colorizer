import os
import sys
import ctypes
import subprocess
import webbrowser


APP_PROCESS_NAME = "cnn-colorizer"
APP_WINDOW_TITLE = "Image & Video Colorizer (DearPyGUI, OpenCV, CNN)"
LINUX_PROCESS_NAME_LIMIT = 15
_linuxLibc = None

try:
    from setproctitle import setproctitle as _setProcessTitle
except ImportError:
    _setProcessTitle = None

if os.name == "posix":
    try:
        _linuxLibc = ctypes.CDLL("libc.so.6")
    except OSError:
        _linuxLibc = None


def getAppBaseDir():
    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS"):
            return sys._MEIPASS
        return os.path.dirname(sys.executable)

    return os.path.dirname(os.path.abspath(__file__))


def resolveResourcePath(*pathParts):
    return os.path.join(getAppBaseDir(), *pathParts)


def _configureLinuxProcessName(processName):
    applied = False
    encodedName = processName.encode("utf-8")[:LINUX_PROCESS_NAME_LIMIT]

    if _linuxLibc is not None:
        try:
            _linuxLibc.prctl(15, ctypes.c_char_p(encodedName), 0, 0, 0)
            applied = True
        except Exception:
            pass

    try:
        with open("/proc/self/comm", "w", encoding="utf-8") as processCommFile:
            processCommFile.write(processName[:LINUX_PROCESS_NAME_LIMIT] + "\n")
        applied = True
    except OSError:
        pass

    return applied


def configureProcessIdentity(processName=APP_PROCESS_NAME):
    applied = False

    if _setProcessTitle is not None:
        try:
            _setProcessTitle(processName)
            applied = True
        except Exception:
            pass

    if os.name == "posix":
        applied = _configureLinuxProcessName(processName) or applied

    return applied


def openExternalUrl(url):
    if os.name == "nt":
        try:
            os.startfile(url)
            return True
        except OSError:
            pass

    if sys.platform == "darwin":
        try:
            completedProcess = subprocess.run(["open", url], check=False)
            if completedProcess.returncode == 0:
                return True
        except OSError:
            pass

    if os.name == "posix":
        try:
            completedProcess = subprocess.run(["xdg-open", url], check=False)
            if completedProcess.returncode == 0:
                return True
        except OSError:
            pass

    try:
        return bool(webbrowser.open(url))
    except Exception:
        return False
