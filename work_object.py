class ColorizationWorkObject:
    def __init__(self, path, type) -> None:
        self.object = {}
        self.object[type] = path
    
    def retrieve(self):
        return self.object