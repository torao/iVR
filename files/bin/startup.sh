#!/bin/bash
# Script to be executed at system startup.

COORDINATE_OPTIONS=""
RECORD_OPTIONS=""
GPS_OPTIONS=""

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
# [GPS OPTIONS]
#

# Set the GPS time as the exact one if local system clock hasn't synchronized with the NTP server.
GPS_OPTIONS+=" --clock-adjust"

# ---

IVR_HOME=$(cd $(dirname $0)/.. && pwd)

# Mount the data directory if it's not already mounted.
DIR_MOUNTPOINT=`readlink $IVR_HOME/data`
if [ ! -z "$DIR_MOUNTPOINT" ]
then
  if [ ! -d "$DIR_MOUNTPOINT" ]
  then
    echo "Creating directory: $DIR_MOUNTPOINT"
    sudo mkdir -p "$DIR_MOUNTPOINT"
  fi
  DEV_SDA1=`lsblk -p -l -n -o NAME | grep /dev/sda1 | wc -l`
  if [ $DRV_SDA1 -eq 0 ]
  then
    espeak-ng "Caution, cannot find USB storage."
    echo "WARN: Cannot find /dev/sda1 to use as data directory. Use an unmounted directory."
  else
    sudo mount -t auto /dev/sda1 "$DIR_MOUNTPOINT"
    if [ $? -ne 0 ]
    then
      espeak-ng "Caution, IVR could not mount the data directory."
      echo "ERROR: iVR could not mount the data directory."
    fi
  fi
fi

python3 $IVR_HOME/bin/gpslog.py $GPS_OPTIONS > /dev/null 2>&1 &
python3 $IVR_HOME/bin/coordinate.py $COORDINATE_OPTIONS &
python3 $IVR_HOME/bin/record.py $RECORD_OPTIONS &
