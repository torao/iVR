#!/usr/bin/env python3
#
import argparse
import datetime
import os
import re
import signal
import subprocess
import sys
import traceback

import ivr

# Real-time recording format: mkv, mp4, avi
FOOTAGE_FILE_EXT = "avi"

# FFmpeg subprocess
ffmpeg_process = None

# Exception raised when FFmpeg doesn't exit the specified time is exceeded.
class TimeoutException(Exception):
    pass


# A handler that only throws an TimeoutException when FFmpeg timeout is detected.
def timeout_handler(signum, frame):
    raise TimeoutException("")


# Start recording the footage.
# Returns the FFmpeg exit-code and the name of the generated footage file.
def start_camera_recording(
    dev_video,
    dev_audio,
    telop_file,
    dir,
    video_resolution,
    video_fps,
    video_input_format,
    video_bitrate,
    sampling_rate,
):
    global ffmpeg_process

    # determine unique file name
    output = new_footage_file(dir, datetime.datetime.now(), FOOTAGE_FILE_EXT)

    # calculate the number of seconds remaining in this hour
    delta = datetime.timedelta(hours=1)
    now = datetime.datetime.now()
    end = datetime.datetime(now.year, now.month, now.day, now.hour) + delta
    interval = (end - now).seconds
    if interval < 60:
        # to avoid a recording time of less than one minute
        # to avoid running with -t 0 in cases like now=20:59:59.940
        end = end + delta
        interval = (end - now).seconds
    t1 = now.strftime("%F %T")
    t2 = end.time()

    telop = [
        "format=pix_fmts=yuv420p",
        "drawbox=y=ih-16:w=iw:h=16:t=fill:color=black@0.4",
        "drawtext=textfile={}:fontsize=12:reload=1:fontcolor=#DDDDDD:x=4:y=h-12".format(
            telop_file
        ),
    ]

    command = ["ffmpeg"]
    command.extend(["-y"])
    command.extend(["-nostdin"])
    command.extend(["-loglevel", "warning"])
    command.extend(["-t", str(interval)])

    # video input options
    # -vsync:   When a frame isn't received from the camera at the specified frame rate, it
    #           deletes or duplicates the frame to achieve the specified frame rate.
    # -ss 0:00: To avoid the error "application provided invalid, non monotonically increasing dts
    #           to muxer in stream" in Logitech C922n.
    command.extend(["-f", "v4l2"])
    command.extend(["-thread_queue_size", "8192"])
    command.extend(["-s", video_resolution])
    command.extend(["-framerate", video_fps])
    if video_input_format is not None:
        command.extend(["-input_format", video_input_format])
    command.extend(["-ss", "0:00"])
    command.extend(["-i", dev_video])

    # audio input options
    # -channel_layout: to avoid warning message "Guessed Channel Layout for Input Stream #1.0 : mono"
    if dev_audio is not None:
        command.extend(["-f", "alsa"])
        command.extend(["-thread_queue_size", "8192"])
        command.extend(["-ac", "1"])  # the number of channels: 1=mono
        command.extend(["-channel_layout", "mono"])
        if sampling_rate is not None:
            command.extend(["-ar", sampling_rate])  # audio sampling rate
        command.extend(["-i", "hw:{}".format(dev_audio)])

    # video filter
    command.extend(["-vf", ",".join(telop)])

    # video / audio output options
    if FOOTAGE_FILE_EXT == "mkv":
        command.extend(["-c:v", "mjpeg"])
        command.extend(["-q:v", "3"])  # -q:v: JPEG quality (2-31)
    elif FOOTAGE_FILE_EXT == "mp4":
        command.extend(["-c:v", "h264_v4l2m2m"])
        command.extend(["-pix_fmt", "yuv420p"])
    elif FOOTAGE_FILE_EXT == "avi":
        command.extend(["-c:v", "h264_v4l2m2m"])
        command.extend(["-pix_fmt", "yuv420p"])

    # output file
    command.extend(["-b:v", video_bitrate])
    command.extend([output])

    proc = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    ffmpeg_process = proc
    try:
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(interval + 15)

        ivr.save_pid("ffmpeg", proc.pid)

        ivr.log("start recording: {} => ".format(" ".join(proc.args), proc.pid))
        ivr.log("  to {} between {} and {} ({} sec)".format(output, t1, t2, interval))
        line = proc.stderr.readline()
        while line:
            ivr.log("FFmpeg: {}".format(line.decode("utf-8").strip()))
            line = proc.stderr.readline()

    except TimeoutException:
        ivr.log("WARNING: FFmpeg didn't finish after {} sec; aborting".format(interval))
    finally:
        ffmpeg_process = None
        signal.alarm(0)
        if proc.returncode is None:
            proc.terminate()
        ivr.remove_pid("ffmpeg")

    try:
        proc.wait(10)
    except subprocess.TimeoutExpired:
        proc.kill()

    return (proc.returncode, output)


# Create a new file name based on the specified datetime that doesn't overlap with any existing
# footage file.
def new_footage_file(dir, now, ext):

    # read sequence from control file
    sequence_file = os.path.join(ivr.data_dir(), ".control")
    i = 0
    if os.path.exists(sequence_file):
        with open(sequence_file, mode="r") as f:
            i = int(f.read())

    while True:

        # test for successful creation of a new file
        file_name = ivr.footage_file_name(now, i, ext)
        path = os.path.join(dir, file_name)
        try:
            with open(path, mode="x") as f:
                pass
        except FileExistsError:
            i += 1
            continue

        # write sequence to control file
        with open(sequence_file, mode="w") as f:
            f.write(str(i + 1))

        return path


SCREEN_SIZE_ALIASES = {
    "320x180": ["QVGA"],
    "400x240": ["WQVGA"],
    "352x288": ["CIF"],
    "640x200": ["CGA"],
    "480x320": ["HVGA"],
    "640x350": ["EGA"],
    "640x400": ["DCGA"],
    "640x480": ["VGA"],
    "720x480": ["DVD", "NTSC480"],
    "720x483": ["NTSC"],
    "800x480": ["WVGA"],
    "854x480": ["FWVGA"],
    "864x480": ["FWVGA+"],
    "800x600": ["SVGA"],
    "1024x480": ["UWVGA"],
    "1024x576": ["WSVGA"],
    "1280x600": ["UWSVGA"],
    "1024x768": ["XGA"],
    "1280x720": ["720p", "HD", "HDTV"],
    "1280x768": ["WXGA"],
    "1152x864": ["XGA+"],
    "1280x800": ["WXGA"],
    "1366x768": ["FWXGA"],
    "1280x1024": ["SXGA"],
    "1280x1050": ["SXGA+"],
    "1920x1080": ["1080p", "1080i", "FHD", "Full HD", "2k"],
    "3840x2160": ["2160p", "4k"],
}

# Converts the specified resolution name to WIDTHxHEIGHT notation.
def screen_resolution(name):
    if re.fullmatch(r"\d+x\d+", name) is not None:
        return name
    for resolution, aliases in SCREEN_SIZE_ALIASES.items():
        for alias in aliases:
            if alias.upper() == name.upper():
                return resolution
    return None


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
    return (None, None)


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
    return (None, None)


# Stop the FFmpeg subprocess if it's running and a TermException will be thrown.
def term_handler(signum, frame):
    global ffmpeg_process
    if ffmpeg_process is not None:
        ffmpeg_process.terminate()
    raise ivr.TermException("")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Save the footage from USB camera")
    parser.add_argument(
        "-d",
        "--dir",
        metavar="DIR",
        default=ivr.data_dir(),
        help="Directory where footage files are stored (default: {})".format(
            ivr.data_dir()
        ),
    )
    parser.add_argument(
        "-t",
        "--telop",
        metavar="FILE",
        default=ivr.telop_file(),
        help="File that contains text to overlay on the footage (default: {})".format(
            ivr.telop_file()
        ),
    )
    parser.add_argument(
        "-v",
        "--video",
        metavar="DEVICE",
        help="Camera device to be used, such as /dev/video0 (default: auto detect)",
    )
    parser.add_argument(
        "-vr",
        "--video-resolution",
        metavar="RESOLUTION",
        default="640x360",
        help="Screen resolution for video recording, such as 1280x720, 720p, or HD (default: 640x360)",
    )
    parser.add_argument(
        "-vf",
        "--video-fps",
        metavar="FPS",
        default="30",
        help="Frames per second for video recording, such as 30, 60 (default: 30)",
    )
    parser.add_argument(
        "-vif",
        "--video-input-format",
        metavar="FORMAT",
        help="Input format from camera, such as yuyv422, mjpeg (default: depends on runtime). See `ffmpeg -f v4l2 -list_formats all -i /dev/video0` for valid values.",
    )
    parser.add_argument(
        "-vbr",
        "--video-bitrate",
        metavar="BITRATE",
        default="768k",
        help="Bitrate for video recording (default: 768k)",
    )
    parser.add_argument(
        "-a",
        "--with-audio",
        action="store_true",
        help="(beta) Record audio with video (default: no audio)",
    )
    parser.add_argument(
        "-as",
        "--audio-sampling-rate",
        metavar="SAMPLING_RATE",
        help="Sampling rate for audio recording (default: 8k)",
    )

    try:
        ivr.save_pid()

        # register SIGTERM handler
        signal.signal(signal.SIGTERM, term_handler)
        signal.signal(signal.SIGINT, term_handler)

        args = parser.parse_args()
        dir = args.dir
        telop = args.telop
        dev_video = args.video
        video_resolution = args.video_resolution
        video_fps = args.video_fps
        video_input_format = args.video_input_format
        video_bitrate = args.video_bitrate
        with_audio = args.with_audio
        sampling_rate = args.audio_sampling_rate

        # resolve screen resolution name
        res = screen_resolution(video_resolution)
        if res is None:
            print("ERROR: invalid screen resolution: {}".format(video_resolution))
            exit(1)
        video_resolution = res

        # auto-detect video and audio devices
        if dev_video is None:
            dev_video_title, dev_video = detect_default_usb_camera()
            ivr.log("detected USB camera: {} = {}".format(dev_video, dev_video_title))
        dev_audio = None
        if with_audio:
            dev_autio_title, dev_audio = detect_default_usb_audio()
            ivr.log("detected Audio: {} = {}".format(dev_audio, dev_autio_title))

        # create an empty telop file assuming that it's before the GPS logger is started
        if not os.path.isfile(telop):
            ivr.write(telop, ivr.DEFAULT_TELOP)

        ivr.beep("IVR starts to recording.")
        while True:
            ret, file = start_camera_recording(
                dev_video,
                dev_audio,
                telop,
                dir,
                video_resolution,
                video_fps,
                video_input_format,
                video_bitrate,
                sampling_rate,
            )
            ivr.beep("")
            ivr.log(
                "the recording of {} has been terminated with: {}".format(file, ret)
            )

    except ivr.TermException as e:
        ivr.log("IVR terminates the recording")
        ivr.beep("footage recording has stopped")
    except Exception as e:
        t = "".join(list(traceback.TracebackException.from_exception(e).format()))
        ivr.log("ERROR: {}".format(t))
        ivr.log("IVR terminates the recording by an error")
        ivr.beep("footage recording has stopped due to an error")
        sys.exit(1)
    finally:
        ivr.remove_pid()
