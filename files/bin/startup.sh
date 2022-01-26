#!/bin/bash
# Script to be executed at system startup.

IVR_HOME=$(cd $(dirname $0)/.. && pwd)

# Wait for autofs to start.
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
python3 $IVR_HOME/bin/coordinate.py &
python3 $IVR_HOME/bin/record.py &
