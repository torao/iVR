# python3 record.py 2> /dev/null &
#
import os
import subprocess
import datetime
import sys
import re
import queue
import threading
from gps3 import gps3

TEMP_DIR = "/opt/ivr/tmp"  # tmpfs (RAM disk) is preferred for frequent writes
FOOTAGE_DIR = "/opt/ivr/data"  # directory whre recorded video files are stored
TELOP_FILE = os.path.join(TEMP_DIR, "telop.txt")
TYPICAL_SIZE_OF_FOOTAGE_FILE = 360 * 1024 * 1024

FOOTAGE_FILE_EXT = "mkv"
FOOTAGE_FILE_MP4 = "mp4"

# Start recording the footage.
# Returns the FFmpeg exit-code and the name of the generated footage file.
def start_camera_recording():

    # calculate the number of seconds remaining in this hour
    delta = datetime.timedelta(minutes=10)
    now = datetime.datetime.now()
    end = (
        datetime.datetime(
            now.year, now.month, now.day, now.hour, int(now.minute / 10) * 10, 0
        )
        + delta
    )
    interval = (end - now).seconds
    log("START: {}, END: {}, INTERVAL: {}".format(now, end, interval))

    # determine unique filename
    i = 0
    while True:
        file_name = footage_file_name(now, i, FOOTAGE_FILE_EXT)
        output = os.path.join(FOOTAGE_DIR, file_name)
        if not os.path.exists(output):
            break
        i += 1

    telop = [
        "format=yuv420p",
        "drawbox=y=ih-16:w=iw:h=16:t=fill:color=black@0.4",
        "drawtext='text=%{localtime\\:%F %T}:fontsize=12:fontcolor=#DDDDDD:x=4:y=h-12'",
        "drawtext=textfile=/tmp/telop.txt:fontsize=12:reload=1:fontcolor=#DDDDDD:x=150:y=h-12",
    ]
    command = [
        "ffmpeg",
        "-nostdin",
        "-t",
        str(interval),
        # video input
        "-f",
        "v4l2",
        "-thread_queue_size",
        "8192",
        "-s",
        "640x360",
        "-framerate",
        "25",
        "-i",
        "/dev/video0",
        # audio input
        "-f",
        "alsa",
        "-thread_queue_size",
        "1024",
        "-ac",
        "1",
        "-i",
        "hw:1,0",
        # video filter
        "-vf",
        ",".join(telop),
        # convert
        "-c:v",
        "mjpeg",
        "-q:v",  # JPEG quality (2-31)
        "3",
        "-b:v",
        "768k",
        output,
    ]
    result = subprocess.run(command)
    print("exit process: %s" % result)
    print("recorded the footage: %s" % output)
    return (result.returncode, output)


def start_gps_recording(telop_file):
    socket = gps3.GPSDSocket()
    socket.connect()
    socket.watch()

    def time(tm, ept):
        if tm is None or tm == "n/a":
            return "--:--:--±-"
        else:
            jst = datetime.timezone(datetime.timedelta(hours=9), "JST")
            tm = datetime.datetime.strptime(tm, "%Y-%m-%dT%H:%M:%S.%f%z").astimezone(
                jst
            )
            tm = tm.strftime("%H:%M:%S")
            ept = 0 if ept is None else int(float(ept))
            return tm if ept == 0 else "{}±{}".format(tm, ept)

    def latlon(ll, ne, sw):
        if ll is None or ll == "n/a":
            return "---.----"
        else:
            ll = float(ll)
            return "{}{:.4f}".format(ne if ll >= 0.0 else sw, abs(ll))

    def unit(alt, unit, default, conv=None):
        if alt is not None and alt != "n/a":
            alt = float(alt) if conv is None else conv(float(alt))
            alt = "{:.1f}".format(alt)
        else:
            alt = default
        return "{}{}".format(alt, unit)

    base = datetime.datetime(year=2000, month=1, day=1)
    ds = gps3.DataStream()
    for new_data in socket:
        data = None
        now = datetime.datetime.now()
        if new_data:
            ds.unpack(new_data)
            tm = time(ds.TPV["time"], ds.TPV["ept"])
            lat = latlon(ds.TPV["lat"], "N", "S")
            lon = latlon(ds.TPV["lon"], "E", "W")
            alt = unit(ds.TPV["alt"], "m", "---")
            speed = unit(ds.TPV["speed"], "km/h", "---", lambda s: s * 3600.0 / 1000.0)
            data = "[GPS {}]  {}/{}  {}  {}".format(tm, lat, lon, alt, speed)
            base = now
        elif (now - base).seconds > 20:
            data = "Lost GPS signal."
            base = now
        if data is not None:
            temp_file = "{}.tmp".format(telop_file)
            with open(temp_file, mode="w") as f:
                f.write(data)
            os.rename(temp_file, telop_file)
    return


mjpeg_to_mp4_queue = queue.Queue()

# Convert the specified Motion JPEG file to MPEG-4 and remove the original file if success.
def start_mjpeg_to_mp4_message_loop():
    while True:
        src = mjpeg_to_mp4_queue.get()
        if src is None:
            break

        # remove if the file is empty
        if os.path.getsize(src) == 0:
            os.remove(src)
            continue

        # get destination file
        dir = os.path.dirname(src)
        base = os.path.splitext(os.path.basename(src))[0]
        dest = os.path.join(dir, "%s.%s" % (base, FOOTAGE_FILE_MP4))

        # ffmpeg -y -i footage-20220122.03.mkv -c:v copy footage-20220122.03.recover.mkv
        command = [
            "ffmpeg",
            "-y",
            "-i",
            src,
            "-c:v",
            "h264_v4l2m2m",
            "-pix_fmt",
            "yuv420p",
            dest,
        ]
        result = subprocess.run(command)
        if result.returncode == 0:
            os.remove(src)
        log("Motion JPEG file was converted to MPEG-4: %s", dest)
    return (result.returncode, output)


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
    log("cleanup: %s, %s" % (dir, max_capacity))
    files = []
    total_size = 0
    max_size = TYPICAL_SIZE_OF_FOOTAGE_FILE
    for f in os.listdir(dir):
        file = os.path.join(dir, f)
        date = date_of_footage_file(file, FOOTAGE_FILE_EXT)
        if date is not None:
            size = os.path.getsize(file)
            tm = os.stat(file).st_mtime
            total_size += size
            max_size = max(max_size, size)
            files.append((date, tm, file, size))
    files = sorted(files)
    # The size that is assumed not to exceed the max_capacity even if a footage is added.
    limited_capacity = max_capacity - max_size
    while total_size > limited_capacity and len(files) > 1:
        f = files.pop(0)
        file = f[2]
        size = f[3]
        os.remove(file)
        total_size -= size
        log("footage file removed: %s" % file)


# Returns the recording date and sequence number if the file is a video file recorded by IVR.
# If the file isn't a video, returns None.
def date_of_footage_file(file, extension):
    file_pattern = (
        "footage-(\\d{4})(\\d{2})(\\d{2})\\.(\\d{2})(\\d{2})(\\.(\\d+))?\." + extension
    )
    file_pattern = re.compile(file_pattern)
    if os.path.isfile(file):
        matcher = re.fullmatch(file_pattern, os.path.basename(file))
        if matcher is not None:
            date = datetime.datetime(
                int(matcher[1]),
                int(matcher[2]),
                int(matcher[3]),
                int(matcher[4]),
                int(matcher[5]),
            )
            return date
    return None


# Generate a footage file name from the specified date and sequence number.
def footage_file_name(date, sequence, extension):
    date_part = date.strftime("%Y%m%d.%H%M")
    seq_part = "" if sequence == 0 else (".%d" % sequence)
    return "footage-%s%s.%s" % (date_part, seq_part, extension)


def log(msg):
    print("***", msg)


def main():
    footage_dir = FOOTAGE_DIR
    max_capacity = 10 * 1024 * 1024 * 1024

    dev_video = detect_default_usb_camera()
    dev_audio = detect_default_usb_audio()
    # print(dev_video, dev_audio)

    telop_file = TELOP_FILE
    with open(telop_file, mode="w") as f:
        f.write("GPS positioning...")

    gps_recording = threading.Thread(target=lambda: start_gps_recording(telop_file))
    gps_recording.start()

    mjpeg_to_mp4 = threading.Thread(target=start_mjpeg_to_mp4_message_loop)
    mjpeg_to_mp4.start()

    while True:
        cleanup(footage_dir, max_capacity)
        ret, file = start_camera_recording()
        log("END: {} -> {}".format(ret, file))

    mjpeg_to_mp4_queue.put(None)
    mjpeg_to_mp4.join()


if __name__ == "__main__":
    main()
