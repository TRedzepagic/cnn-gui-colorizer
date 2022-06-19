import subprocess
class ImageDisplayHelper():
    def __init__(self) -> None:
        self.imageDisplayProcesses = []
 
    def terminateImageDisplayers(self):
        [imageDisplayProcess.kill() for imageDisplayProcess in self.imageDisplayProcesses]

    def _appendImageDisplayerInstance(self, player):
        self.imageDisplayProcesses.append(player)
    
    def display(self, path):
        imageDisplayerProc = subprocess.Popen(["sxiv", "-sf", path])
        self._appendImageDisplayerInstance(imageDisplayerProc)
        stdout, stderr = imageDisplayerProc.communicate()