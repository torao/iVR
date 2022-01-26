#!/bin/bash
# Script for IVR shutdown.

function shutdown(){
    local file="$(dirname $0)/../tmp/$1.pid"
    local pid=`cat $file`
    if [ ! -z "$pid" ]
    then
      if [ `ps -ef | grep " $pid " | wc -l` -ne 0 ]
      then
        kill $pid
      else
        rm $file
      fi
    fi
}

shutdown gpslog.py
shutdown coordinate.py
shutdown record.py
killall ffmpeg
