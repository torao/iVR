#!/bin/bash
# Script to be executed at system startup.

COORDINATE_OPTIONS=""
RECORD_OPTIONS=""

# ---
# [STORAGE OPTIONS]
# 
# Adjust the following two values considering the size of the USB storage attached to the system.
# Set the total size to be abount 1.5GB less than its actual space.

# Total size limit for footage files. If the total size exceeds this capacity, the oldest files
# will be deleted. A footage file per hour is about 250MB to 360MB.
COORDINATE_OPTIONS+=" --limit-footage 60G"

# Total size limit for tracklog files. If the total size exceeds this capacity, the oldest files
# will be deleted.
COORDINATE_OPTIONS+=" --limit-tracklog 2G"

# ---
# [VIDEO OPTIONS]
#

# Video device to be used for video recording explicitly. Specify this when auto-detection doesn't
# recognize the device correctly, or when using a camera module instead of a USB camera.
# RECORD_OPTIONS+=" --video /dev/video0"

# Bit rate of the video. Specify a higher value when the video quality is poor relative to the
# camera quality.
RECORD_OPTIONS+=" --video-bitrate 768k"

# ---
# [AUDIO OPTIONS]
#
# Audio recording is turned off by default, and the state is still in an unstable beta version.

# Enable this option if you want to record audio.
# RECORD_OPTIONS+=" --with-audio"

# Audio sampling rate. Specify a higher value if the audio is poor relative to the microphone
# quality.
# RECORD_OPTIONS+=" --audio-sampling-rate 8k"

# ---

IVR_HOME=$(cd $(dirname $0)/.. && pwd)

# Wait for autofs to start and /opt/ivr/data to be mounted.
DIR_DATA_DEVICE=`readlink $IVR_HOME/data`
if [ ! -z "$DIR_DATA_DEVICE" ]
then
  I=0
  while [ `df | grep $DIR_DATA_DEVICE | wc -l` -eq 0 ]
  do
    echo "$I[sec]: waiting autofs to mount $DIR_DATA_DEVICE -> $IVR_HOME/data..."
    sleep 1
    ls $IVR_HOME/data/ > /dev/null 2>&1
    I=`expr $I + 1`
    if [ $I -gt 180 ]
    then
      espeak "caution, the IVR could not mount the data directory"
      exit 1
    fi
  done
fi

python3 $IVR_HOME/bin/gpslog.py > /dev/null 2>&1 &
python3 $IVR_HOME/bin/coordinate.py $COORDINATE_OPTIONS &
python3 $IVR_HOME/bin/record.py $RECORD_OPTIONS &
