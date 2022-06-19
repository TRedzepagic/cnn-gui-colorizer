class DisplayMessage:
    def __init__(self, msg, type) -> None:
        """
            Message types:
                - IMAGE
                - VIDEO
            Message:
                - PATH TO IMAGE/VIDEO
            CREATION:
                displayMessage = DisplayMessage(path, "IMAGE")
        """
        self.statusMessage = {}
        self.statusMessage[type] = msg

    def retrieve(self):
        return self.statusMessage