# python3 record.py 2> /dev/null &
# 
import os
import subprocess
import datetime

TEMP_DIR = '/tmp'           # RAM disk is preferred for frequent writes
MOVIE_DIR = '/mnt/usb01'    # directory whre recorded video files are stored


def start_recording():

    # calculate the number of seconds remaining in this hour
    now = datetime.datetime.now()
    end = datetime.datetime(now.year, now.month, now.day, now.hour + 1, 0, 0)
    interval = (end - now).seconds

    # determine unique filename
    i = 0
    while True:
        date = now.strftime('%Y%m%d.%H')
        sequence = '' if i == 0 else ('.%d' % i)
        file_name = 'output-%s%s.mp4' % (date, sequence)
        output = os.path.join(MOVIE_DIR, file_name)
        if not os.path.exists(output):
            break
        i += 1

    telop = [
        'format=yuv420p',
        'drawbox=y=ih-20:w=iw:h=20:t=fill:color=black@0.4',
        'drawtext=\'text=%{localtime\\:%F %T}:fontsize=16:fontcolor=#DDDDDD:x=4:y=h-17\'',
        'drawtext=textfile=/tmp/telop.txt:fontsize=16:reload=1:fontcolor=#DDDDDD:x=180:y=h-17'
    ]
    command = [
        'ffmpeg',
        '-nostdin',
        '-f', 'v4l2', '-thread_queue_size', '8192', '-s', '640x480', '-framerate', '30','-i', '/dev/video0',
        '-f', 'alsa', '-ac', '1', '-i', 'hw:1,0',
        '-vf', ','.join(telop),
        '-c:v', 'h264_v4l2m2m', '-b:v', '768k',
        '-t', str(interval),
        '-movflags', '+faststart', '-bufsize', '10M',
        output
    ]
    result = subprocess.run(command)
    print("exit process: %s" % result)
    print("recorded the footage: %s" % output)


if __name__ == '__main__':
    while True:
        start_recording()