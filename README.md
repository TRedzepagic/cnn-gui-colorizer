# Colorizer GUI using CNNs
An app using a neural network approach to colorize images and videos.
<br>
The application (the neural net rather) "hallucinates" possible colors (so an acceptable result is a probable result, not necessarily the real truth).
<br>
GUI written in [DearPyGui](https://github.com/hoffstadt/DearPyGui) to allow a pleasant user experience.
## Screenshots
![Screenshot1](screenshots/screenshot-turtle.png)
<br>
![Screenshot2](screenshots/screenshot-brain.png)
## Installation & Usage
1. Check out [R. Zhang's instructions on how to get the trained model.](https://github.com/richzhang/colorization/tree/caffe/colorization)
2. Clone repository
3. For video reproduction, you need MPV: [MPV Installation](https://mpv.io/installation/), or quickly for Debian based distros: ```sudo apt install mpv```
4. For displaying images, you need sxiv: ```sudo apt install sxiv```
5. ```pip3 install -r requirements.txt```
6. Execute with ```python3 main_DPG.py```

## Features
-   Colorize images
-   Colorize videos
-   Colorize images & videos at the same time
-   Cancel video colorization if it is taking too long for your liking
-   Video colorization progress bar
-   File picker, no need for program arguments
-   RGB information on mouse hover

## Resources
- [Zhang, R., Isola, P., & Efros, A. A. (2016). Colorful Image Colorization. ECCV.](https://arxiv.org/pdf/1603.08511.pdf)
- [Zhang, R., Zhu, J.-Y., Isola, P., Geng, X., Lin, A. S., Yu, T., & Efros, A. A. (2017). Real-Time User-Guided Image Colorization with Learned Deep Priors. ACM Transactions on Graphics (TOG), 9(4).](https://arxiv.org/pdf/1705.02999.pdf)
- [Rosebrock A. (2019). Black and white image colorization with OpenCV and Deep Learning](https://pyimagesearch.com/2019/02/25/black-and-white-image-colorization-with-opencv-and-deep-learning/)
- [DearPyGui documentation.](https://dearpygui.readthedocs.io/)