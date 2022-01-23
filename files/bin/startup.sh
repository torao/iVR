#!/bin/bash
# Script to be executed at system startup.

# Set this variable explicitly if the video input device cannot be detected correctly.
# The appropriate device can be found by `v4l2-ctl --list-devices`.
#DEVICE_CAMERA=/dev/video0

# Set this variable explicitly if the audio input device cannot be detected correctly.
# The appropriate device can be found by `arecord --list-devices`.
#DEVICE_AUDIO=1,0

python3 $(dirname $0)/gps_positioning.py /tmp/telop.txt &
python3 $(dirname $0)/archive.py $(dirname $0)/../data/ 3G &
python3 $(dirname $0)/record.py $(dirname $0)/../data/ $(dirname $0)/../tmp/telop.txt 2> $(dirname $0)/stderr.log > $(dirname $0)/stdout.log &
