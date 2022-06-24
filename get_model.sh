#!/bin/bash
MODEL_FOLDER="./model"

PROTOTXT_LINK="https://raw.githubusercontent.com/richzhang/colorization/caffe/colorization/models/colorization_deploy_v2.prototxt"
PTS_IN_HULL_LINK="https://github.com/richzhang/colorization/blob/caffe/colorization/resources/pts_in_hull.npy?raw=true"
CAFFE_MODEL_LINK="https://eecs.berkeley.edu/~rich.zhang/projects/2016_colorization/files/demo_v2/colorization_release_v2.caffemodel"

PROTOTXT="./model/colorization_deploy_v2.prototxt"
PTS_IN_HULL="./model/pts_in_hull.npy"
CAFFE_MODEL="./model/colorization_release_v2.caffemodel"

function get_files {
    if [ ! -e $PROTOTXT ]; then
    wget $PROTOTXT_LINK -O $PROTOTXT
    else 
        echo "$PROTOTXT file exists"
    fi 

    if [ ! -e $PTS_IN_HULL ]; then
        wget $PTS_IN_HULL_LINK -O $PTS_IN_HULL
    else 
        echo "$PTS_IN_HULL exists"
    fi 

    if [ ! -e $CAFFE_MODEL ]; then
        wget $CAFFE_MODEL_LINK -O $CAFFE_MODEL
    else 
        echo "$CAFFE_MODEL  exists"
    fi 
}

mkdir -p $MODEL_FOLDER
get_files