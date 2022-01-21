#!/bin/bash
# Script to be executed at system startup.

# Set this variable explicitly if the video input device cannot be detected correctly.
# The appropriate device can be found by `v4l2-ctl --list-devices`.
#DEVICE_CAMERA=/dev/video0

# Set this variable explicitly if the audio input device cannot be detected correctly.
# The appropriate device can be found by `arecord --list-devices`.
#DEVICE_AUDIO=1,0

python $(dirname $0)/record.py 2> $(dirname $0)/stderr.log > $(dirname $0)/stdout.log &
