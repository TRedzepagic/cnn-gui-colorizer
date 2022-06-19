import subprocess
class VideoPlayerHelper():
    def __init__(self) -> None:
        self.videoPlayerProcesses = []
 
    def terminateVideoPlayers(self):
        [mpvProc.kill() for mpvProc in self.videoPlayerProcesses]

    def _appendVideoPlayer(self, player):
        self.videoPlayerProcesses.append(player)
    
    def play(self, path):
        mpvProc = subprocess.Popen(["mpv", "--loop", "--no-terminal", path])
        self._appendVideoPlayer(mpvProc)
        stdout, stderr = mpvProc.communicate()