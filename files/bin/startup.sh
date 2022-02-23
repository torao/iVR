#!/bin/bash
# Script to be executed at system startup.

declare -a rec_options=()
declare -a crd_options=()
declare -a gps_options=()

# ---
# [STORAGE OPTIONS]
# 
# The iVR automatically deletes outdated data considering the capacity of the USB storage.
# If you want to limit the available space with a fixed value instead of using all of the storage
# capacity, please set the following values.
# No matter how small the value you specify, two files will always be retained: the latest data
# currently being recorded and the previous data.

# Total size limit for video footage files. If the total size exceeds this capacity, the oldest
# files will be deleted. A footage file per hour is about 250MB to 360MB.
#crd_options+=("--limit-footage" "100G")

# Total size limit for tracklog files. If the total size exceeds this capacity, the oldest files
# will be deleted.
#crd_options+=("--limit-tracklog" "5G")

# ---
# [VIDEO OPTIONS]
# 
# The following options work with FFmpeg. Please refer to the log file to see what FFmpeg commands
# are being executed and if any of the options you need are missing, please modify record.py.

# Video device to be used for video recording explicitly. Specify this when auto-detection doesn't
# recognize the device correctly, or when using a camera module instead of a USB camera.
#rec_options+=("--video" "/dev/video0")

# Video resolution, which can use WIDTHxHEIGHT notations such as 1280x720, 720p, HD, etc.
rec_options+=("--video-resolution" "864x480")

# Output frame-rate of video.
#rec_options+=("--video-fps" "30")

# Bit rate of the video. Specify a higher value when the video quality is poor relative to the
# camera quality.
#rec_options+=("--video-bitrate" "4M")

# Input format from camera.
# Note that the specific resolution and FPS depend on the input format.
# See `v4l2-ctl --list-formats-ext` for the relationship between resolution, FPS and input format.
# See `ffmpeg -f v4l2 -list_formats all -i /dev/video0` for valid values.
# Selecting high quality or Motion-JPEG may increase the CPU usage significantly.
#rec_options+=("--video-input-format" "mjpeg")

# ---
# [AUDIO OPTIONS]
#
# Audio recording is turned off by default, and the state is still in an unstable beta version.

# Enable this option if you don't want to record audio.
#rec_options+=("--without-audio")

# Audio sampling rate. Specify a higher value if the audio is poor relative to the microphone
# quality.
#rec_options+=("--audio-sampling-rate" "8k")

# Disable the noise reduction filter for audio. If it's used in a noise-free environment, disabling
# this may improve the quality of the audio.
#rec_options+=("--without-audio-noise-reduction")

# ---
# [GPS OPTIONS]
#

# Set the GPS time as the exact one if local system clock hasn't synchronized with the NTP server.
gps_options+=("--clock-adjust")

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
    sudo chmod 777 "$DIR_MOUNTPOINT"
  fi

  # Detect the destination storage device.
  DEV_STRAGES=`lsblk -p -l -o NAME | tail -n +2 | grep '/dev/sd[a-z][1-9]' | head -n 1`
  if [ -z "$DEV_STRAGES" ]
  then
    # Error if the destination device does not exist.
    espeak-ng "Error, cannot find USB storage."
    echo "ERROR: Cannot find $DEV_STRAGES to use as data directory. Use an unmounted directory."
    exit 1
  else
    for dev in $DEV_STRAGES
    do
      # If the device is not mounted anywhere, mount it to mountpoint.
      if [ `df | grep "$dev" | wc -l` -eq 0 ]
      then
        sudo mount -t exfat,vfat -o umask=0000 "$dev" "$DIR_MOUNTPOINT"
        if [ $? -ne 0 ]
        then
          espeak-ng "Error, IVR could not mount the data directory."
          echo "ERROR: iVR could not mount the data directory."
          exit 1
        fi
        echo "$dev is now mounted in $DIR_MOUNTPOINT."
        echo "data directory $IVR_HOME/data is available."
        break
      fi
    done
  fi
fi

python3 $IVR_HOME/bin/gpslog.py ${gps_options[@]} > /dev/null 2>&1 &
python3 $IVR_HOME/bin/coordinate.py ${crd_options[@]} &
python3 $IVR_HOME/bin/record.py ${rec_options[@]} &
