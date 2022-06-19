import cv2
import numpy as np

class NeuralNet():
    def __init__(self) -> None:
        self.prototxt = 'model/colorization_deploy_v2.prototxt'
        self.model = 'model/colorization_release_v2.caffemodel'
        self.points = 'model/pts_in_hull.npy'
        self.net = cv2.dnn.readNetFromCaffe(self.prototxt, self.model)
        self.pts = np.load(self.points)
        # Add the cluster centers as 1x1 convolutions to the model
        self.class8 = self.net.getLayerId("class8_ab")
        self.conv8 = self.net.getLayerId("conv8_313_rh")
        self.pts = self.pts.transpose().reshape(2, 313, 1, 1)
        self.net.getLayer(self.class8).blobs = [self.pts.astype("float32")]
        self.net.getLayer(self.conv8).blobs = [np.full([1, 313], 2.606, dtype="float32")]
    
    def colorize(self, image):
        # Scale image to [0, 1] range
        # Change BGR colorspace to LAB (Lightness, A-axis (Green to Red), B-axis (Blue to Yellow))
        # OpenCV by default works with BGR, not RGB (R and B switch order)
        scaledImage = image.astype("float32") / 255.0
        imageLAB = cv2.cvtColor(scaledImage, cv2.COLOR_BGR2LAB)

        # Resize image to 224x224 (neural net input, required)
        # Extract L (Lightness)
        # Perform mean centering
        resizedLABImage = cv2.resize(imageLAB, (224, 224))
        L = cv2.split(resizedLABImage)[0]
        L -= 50
        
        # Input Lightness into neural net, to predict the other two axes
        # This will predict our colors
        # Resize A and B to comply with original image
        self.net.setInput(cv2.dnn.blobFromImage(L))
        ab = self.net.forward()[0, :, :, :].transpose((1, 2, 0))
        ab = cv2.resize(ab, (image.shape[1], image.shape[0]))

        # Join L from original image with predicted A and B axes.
        # This as a result has the colorized image with complete LAB
        L = cv2.split(imageLAB)[0]
        colorizedImage = np.concatenate((L[:, :, np.newaxis], ab), axis=2)

        # Return to BGR from LAB
        # Only leave [0, 1] values in numpy array
        colorizedImage = cv2.cvtColor(colorizedImage, cv2.COLOR_LAB2BGR)
        colorizedImage = np.clip(colorizedImage, 0, 1)

        # Return [0, 1] array values to [0, 255] values we expect from images
        # Return colorized image
        colorizedImage = (255 * colorizedImage).astype("uint8")
        return colorizedImage
        