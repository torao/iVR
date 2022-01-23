# python3 record.py 2> /dev/null &
#
import argparse
import os
import subprocess
import datetime
import sys
import re
import queue
import threading
import ivr

# Real-time recording format: mkv, mp4, avi
FOOTAGE_FILE_EXT = "avi"

# Start recording the footage.
# Returns the FFmpeg exit-code and the name of the generated footage file.
def start_camera_recording(dev_video, dev_audio, telop_file, dir):

    # calculate the number of seconds remaining in this hour
    delta = datetime.timedelta(hours=1)
    now = datetime.datetime.now()
    end = datetime.datetime(now.year, now.month, now.day, now.hour) + delta
    interval = (end - now).seconds

    # determine unique filename
    i = 0
    while True:
        file_name = ivr.footage_file_name(now, i, FOOTAGE_FILE_EXT)
        output = os.path.join(dir, file_name)
        if not os.path.exists(output):
            break
        i += 1
    t1 = now.strftime("%F %T")
    t2 = end.time()
    ivr.log(
        "start recording: {} between {} and {} ({} sec)".format(
            output, t1, t2, interval
        )
    )

    telop = [
        "format=pix_fmts=yuv420p",
        "drawbox=y=ih-16:w=iw:h=16:t=fill:color=black@0.4",
        "drawtext='text=%{localtime\\:%F %T}:fontsize=12:fontcolor=#DDDDDD:x=4:y=h-12'",
        "drawtext=textfile={}:fontsize=12:reload=1:fontcolor=#DDDDDD:x=140:y=h-12".format(
            telop_file
        ),
    ]

    command = ["ffmpeg"]
    command.extend(["-nostdin", "-xerror"])
    command.extend(["-loglevel", "warning"])
    command.extend(["-t", str(interval)])

    # video input options
    # -vsync: When a frame isn't received from the camera at the specified frame rate, it
    #         deletes or duplicates the frame to achieve the specified frame rate.
    command.extend(["-f", "v4l2"])
    command.extend(["-vsync", "cfr"])
    command.extend(["-thread_queue_size", "8192"])
    command.extend(["-s", "640x360"])
    command.extend(["-framerate", "30"])
    command.extend(["-i", dev_video])

    # audio input options
    # NOTE: The audio will not be recorded because once ALSA's buffer xrun error occurs, FFmpeg
    # exit with code -9 and the video file isn't playable at all.
    # -channel_layout: to avoid warning message "Guessed Channel Layout for Input Stream #1.0 : mono"
    if False:
        command.extend(["-f", "alsa"])
        command.extend(["-thread_queue_size", "8192"])
        command.extend(["-ac", "1"])  # the number of channels: 1=mono
        command.extend(["-channel_layout", "mono"])
        command.extend(["-ar", "8k"])  # audio sampling rate
        command.extend(["-i", "hw:{}".format(dev_audio)])

    # video filter
    command.extend(["-vf", ",".join(telop)])

    # video / audio output options
    if FOOTAGE_FILE_EXT == "mkv":
        # -q:v: JPEG quality (2-31)
        command.extend(["-c:v", "mjpeg"])
        command.extend(["-q:v", "3"])
    elif FOOTAGE_FILE_EXT == "mp4":
        command.extend(["-c:v", "h264_v4l2m2m"])
        command.extend(["-pix_fmt", "yuv420p"])

    # output file
    command.extend(["-b:v", "768k"])
    command.extend([output])

    result = subprocess.run(command)
    ivr.log("exit process: %s" % result)
    ivr.log("recorded the footage: %s" % output)
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
            ivr.log("WARNING: unknown device: %s" % line)
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Save the footage from USB camera")
    parser.add_argument("dir", help="Directory where footage files are stored")
    parser.add_argument(
        "telop", help="File that contains text to overlay on the footage"
    )
    parser.add_argument(
        "-v", "--video", help="Camera device to be used, such as /dev/video0"
    )

    args = parser.parse_args()
    dir = args.dir
    telop = args.telop
    dev_video = args.video

    if dev_video is None:
        dev_video_title, dev_video = detect_default_usb_camera()
        ivr.log("Detected USB camera: {} = {}".format(dev_video, dev_video_title))
    dev_autio_title, dev_audio = detect_default_usb_audio()
    ivr.log("Detected Audio: {} = {}".format(dev_audio, dev_autio_title))

    ivr.beep("IVR starts to recording.")
    while True:
        ret, file = start_camera_recording(dev_video, dev_audio, telop, dir)
        ivr.beep("The recording has been switched with return code {}.".format(ret))
        ivr.log("END: {} -> {}".format(ret, file))