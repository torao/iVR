#!/bin/sh

# Set this variable explicitly if the video input device cannot be detected correctly.
# The appropriate device can be found by `v4l2-ctl --list-devices`.
#DEVICE_CAMERA=/dev/video0

# 
IVR_HOME=$(cd $(dirname $0)/.. && pwd)

function fatal() {
    echo "ERROR: $1" >&2
    exit 1
}