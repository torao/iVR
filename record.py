import os
import subprocess
import datetime

TEMP_DIR = '/tmp'           # RAM disk is preferred for frequent writes
MOVIE_DIR = '/mnt/usb01'    # directory whre recorded video files are stored


def main():

    # determine unique filename
    now = datetime.datetime.now()
    i = 0
    while True:
        date = now.strftime('%Y%m%d.%H')
        sequence = '' if i == 0 else ('.%d' % i)
        file_name = 'output-%s%s.mp4' % (date, sequence)
        output = os.path.join(MOVIE_DIR, file_name)
        if not os.path.exists(output):
            break
        i += 1

    command = [
        'ffmpeg',
        '-f', 'v4l2', '-thread_queue_size', '8192', '-s', '640x480', '-framerate', '30','-i', '/dev/video0',
        '-f', 'alsa', '-ac', '1', '-i', 'hw:1,0',
        '-c:v', 'h264_v4l2m2m', '-b:v', '768k',
        '-t', '60',
        '-movflags', '+faststart', '-bufsize', '10M',
        # '-f', 'segments', '-flags', '+global_header',
        # '-segment_format_options', 'movflags=+faststart', '-reset_timestamps', '1', '-segment_time', '3600',
        output
    ]
    result = subprocess.run(command)
    print("exit process: %s" % result)


if __name__ == '__main__':
    main()