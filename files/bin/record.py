# python3 record.py 2> /dev/null &
#
import os
import subprocess
import datetime
import sys
import re

TEMP_DIR = "/tmp"  # tmpfs (RAM disk) is preferred for frequent writes
MOVIE_DIR = "/mnt/usb01"  # directory whre recorded video files are stored


def start_recording():

    # calculate the number of seconds remaining in this hour
    now = datetime.datetime.now()
    end = datetime.datetime(now.year, now.month, now.day, now.hour + 1, 0, 0)
    interval = (end - now).seconds

    # determine unique filename
    i = 0
    while True:
        date = now.strftime("%Y%m%d.%H")
        sequence = "" if i == 0 else (".%d" % i)
        file_name = "output-%s%s.mp4" % (date, sequence)
        output = os.path.join(MOVIE_DIR, file_name)
        if not os.path.exists(output):
            break
        i += 1

    telop = [
        "format=yuv420p",
        "drawbox=y=ih-20:w=iw:h=20:t=fill:color=black@0.4",
        "drawtext='text=%{localtime\\:%F %T}:fontsize=16:fontcolor=#DDDDDD:x=4:y=h-17'",
        "drawtext=textfile=/tmp/telop.txt:fontsize=16:reload=1:fontcolor=#DDDDDD:x=180:y=h-17",
    ]
    command = [
        "ffmpeg",
        "-nostdin",
        "-f",
        "v4l2",
        "-thread_queue_size",
        "8192",
        "-s",
        "640x480",
        "-framerate",
        "30",
        "-i",
        "/dev/video0",
        "-f",
        "alsa",
        "-ac",
        "1",
        "-i",
        "hw:1,0",
        "-vf",
        ",".join(telop),
        "-c:v",
        "h264_v4l2m2m",
        "-b:v",
        "768k",
        "-t",
        str(interval),
        "-movflags",
        "+faststart",
        "-bufsize",
        "10M",
        output,
    ]
    result = subprocess.run(command)
    print("exit process: %s" % result)
    print("recorded the footage: %s" % output)


# Returns the device with the lowest number among the USB connected video devices from captured
# video device list using v4l2-ctl --list-devices.
# If no such device was detected, returns `None`.
# This function returns a map with a list of devices, such as /dev/video0, using the title as its
# key.
def detect_default_usb_camera():
    cmd = ["v4l2-ctl", "--list-devices"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)

    # Get keys with a title like 'C270 HD WEBCAM (usb-3f980000.usb-1.3):'
    current_title = None
    min_n = None
    device = None
    title = None
    pattern_device = r"/dev/video([0-9]+)"
    pattern_title = r"\(usb-[^\)]*\):"
    while True:
        line = proc.stdout.readline()
        if not line and proc.poll() is not None:
            break
        line = line.decode("utf-8")
        if not line.startswith("\t") and line.endswith(":\n"):
            matcher = re.search(pattern_title, line)
            if matcher is not None and (min_n is None or min_n > int(matcher[1])):
                current_title = line.strip()
            else:
                current_title = None
        elif line.startswith("\t"):
            if current_title is not None:
                # Get a device with the smallest N for /dev/videoN.
                matcher = re.search(pattern_device, line)
                if matcher is not None and (min_n is None or min_n > int(matcher[1])):
                    title = current_title
                    device = line.strip()
                    min_n = int(matcher[1])
        elif len(line.strip()) != 0:
            print("WARNING: unknown device: %s" % line, file=sys.stderr)
    if device is not None:
        return (title, device)
    return None


# Get the card number and device number of the first USB audio device detected.
def detect_default_usb_audio():
    cmd = ["arecord", "--list-devices"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    pattern = r"^card ([0-9]+): .*, device ([0-9]+): USB Audio.*$"
    while True:
        line = proc.stdout.readline()
        if not line and proc.poll() is not None:
            break
        line = line.decode("utf-8").strip()
        matcher = re.fullmatch(pattern, line, re.IGNORECASE)
        if matcher is not None:
            hw = "%d,%d" % (int(matcher[1]), int(matcher[2]))
            return (line.strip(), hw)
    return None


def main():
    dev_video = detect_default_usb_camera()
    dev_audio = detect_default_usb_audio()
    print(dev_video, dev_audio)
    # while True:
    #     start_recording()


if __name__ == "__main__":
    main()
