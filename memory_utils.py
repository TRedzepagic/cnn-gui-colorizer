import ctypes
import gc
import os


_mallocTrim = None

if os.name == "posix":
    try:
        _libc = ctypes.CDLL("libc.so.6")
        _mallocTrim = getattr(_libc, "malloc_trim", None)
    except OSError:
        _mallocTrim = None


def trimProcessMemory():
    gc.collect()

    if _mallocTrim is None:
        return False

    try:
        return bool(_mallocTrim(0))
    except Exception:
        return False
