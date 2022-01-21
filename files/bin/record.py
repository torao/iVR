# python3 record.py 2> /dev/null &
#
import os
import subprocess
import datetime
import sys
import re

TEMP_DIR = "/opt/ivr/tmp"  # tmpfs (RAM disk) is preferred for frequent writes
FOOTAGE_DIR = "/opt/ivr/data"  # directory whre recorded video files are stored
TELOP_FILE = os.path.join(TEMP_DIR, "telop.txt")
TYPICAL_SIZE_OF_FOOTAGE_FILE = 360 * 1024 * 1024


def start_recording():

    # calculate the number of seconds remaining in this hour
    now = datetime.datetime.now()
    end = datetime.datetime(now.year, now.month, now.day, now.hour + 1, 0, 0)
    interval = (end - now).seconds

    # determine unique filename
    i = 0
    while True:
        file_name = footage_file_name(now, i)
        output = os.path.join(FOOTAGE_DIR, file_name)
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
        "-flush_packets",
        "1",
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


# Remove the oldest data first to reduce it below the maximum capacity if the total size of the
# video files in the directory exceeds the maximum capacity.
def cleanup(dir, max_capacity):
    files = []
    total_size = 0
    max_size = TYPICAL_SIZE_OF_FOOTAGE_FILE
    for file in os.listdir(dir):
        ds = date_and_sequence_of_footage_file(file)
        if ds is not None:
            size = os.path.getsize(file)
            total_size += size
            max_size = max(max_size, size)
            files.append((ds[0], ds[1], file, size))
    files = sorted(files)
    # The size that is assumed not to exceed the max_capacity even if a footage is added.
    limited_capacity = max_capacity - max_size
    while total_size > limited_capacity and len(files) > 0:
        file = files[0][2]
        size = files[0][3]
        os.remove(file)
        total_size -= size
        print("footage file removed: %s" % file)


# Returns the recording date and sequence number if the file is a video file recorded by IVR.
# If the file isn't a video, returns None.
def date_and_sequence_of_footage_file(file):
    file_pattern = r"footage-(\d{4})(\d{2})(\d{2})\.(\d{2})(\.(\d+))?\.mp4"
    if os.path.isfile(file):
        matcher = re.fullmatch(file_pattern, os.path.basename(file))
        if matcher is not None:
            date = datetime.datetime(
                int(matcher[1]), int(matcher[2]), int(matcher[3]), int(matcher[4])
            )
            seq = 0 if len(matcher) < 7 else int(matcher[6])
            return (date, seq)
    return None


# Generate a footage file name from the specified date and sequence number.
def footage_file_name(date, sequence):
    date_part = date.strftime("%Y%m%d.%H")
    seq_part = "" if sequence == 0 else (".%d" % sequence)
    return "footage-%s%s.mp4" % (date_part, seq_part)


def main():
    footage_dir = FOOTAGE_DIR
    max_capacity = 1024 * 1024 * 1024

    dev_video = detect_default_usb_camera()
    dev_audio = detect_default_usb_audio()
    print(dev_video, dev_audio)

    telop_file = TELOP_FILE
    with open(telop_file, mode="w") as f:
        f.write("E*****/W*****")

    while True:
        cleanup(footage_dir, max_capacity)
        start_recording()


if __name__ == "__main__":
    main()
