#!/bin/bash
# Script for IVR shutdown.

function shutdown(){
  local file="$(dirname $0)/../tmp/$1.pid"
  if [ -f $file ]
  then
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
  fi
}

shutdown gpslog.py
sleep 0.6
shutdown coordinate.py
sleep 0.6
shutdown record.py
if [ `ps -ef | grep ffmpeg | grep -v grep | wc -l` -ne 0 ]
then
  killall ffmpeg > /dev/null 2>&1
fi
