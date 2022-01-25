# python3 archive.py 2> /dev/null &
#
# Removes the recorded footage files until their total size is less than the maximum capacity,
# and converts the real-time recorded files to MP4.
#
import argparse
import os
import subprocess
import datetime
import sys
import time
import re
import ivr
import traceback
import signal

ffmpeg_process = None

# change the extension of the specified file.
def change_extension(file, extension):
    dir = os.path.dirname(file)
    base = os.path.splitext(os.path.basename(file))[0]
    return os.path.join(dir, "{}.{}".format(base, extension))


def remove(file, reason=None):
    os.remove(file)
    reason = "" if reason is None else " ({})".format(reason)
    ivr.log("file removed: {}{}".format(file, reason))


# Convert the specified AVI or Motion JPEG file to MPEG-4 and remove the original file if success.
def convert_wip_to_mp4(src):
    global ffmpeg_process

    dest = change_extension(src, "mp4")

    # ffmpeg -y -i footage-20220122.03.mkv -c:v copy footage-20220122.03.recover.mkv
    command = ["ffmpeg"]
    command.extend(["-y"])
    command.extend(["-loglevel", "warning"])
    command.extend(["-i", src])
    command.extend(["-c:v", "h264_v4l2m2m"])
    command.extend(["-pix_fmt", "yuv420p"])
    command.extend(["-b:v", "768k"])
    command.extend([dest])

    proc = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    ffmpeg_process = proc
    try:
        ivr.log("start ffmpeg: %s" % " ".join(proc.args))
        line = proc.stderr.readline()
        while line:
            ivr.log("FFmpeg: {}".format(line.decode("utf-8").strip()))
            line = proc.stderr.readline()
    finally:
        ffmpeg_process = None

    result = subprocess.run(command)
    if result.returncode != 0:
        ivr.beep("Failed to convert to MP4")
        ivr.log("failed to convert to MP4: {}".format(src))
        if os.path.isfile(dest):
            remove(dest)
        return None
    return dest


# Remove the oldest data first to reduce it below the maximum capacity if the total size of the
# video files in the directory exceeds the maximum capacity.
def archive_footage_files(dir, limit):

    # remove interrupted files in the process of converting to MP4
    for f in os.listdir(dir):
        file = os.path.join(dir, f)
        date = ivr.date_of_footage_file(file)
        if date is not None and ivr.is_in_recording(file):
            mp4_file = change_extension(file, "mp4")
            if os.path.isfile(mp4_file):
                reason = "interrupted file in the process of converting to MP4"
                remove(mp4_file, reason)

    # retrie all footage files and sort them in order of newest to oldest
    files = []
    for f in os.listdir(dir):
        file = os.path.join(dir, f)
        date = ivr.date_of_footage_file(file)
        if date is not None:
            if os.path.getsize(file) == 0:
                # remove if the file is empty
                reason = "empty file"
                remove(file, reason)
            else:
                files.append((date, os.stat(file).st_mtime, file))
    files.sort(reverse=True)
    files = [f for _, _, f in files]

    # find and remove the most recent file being recorded from list
    total_size = 0
    for i in range(len(files)):
        file = files[i]
        if ivr.is_in_recording(file):
            total_size += os.path.getsize(file)
            files.pop(i)
            break

    # remove the files we want to keep from the list
    converted = False
    while len(files) > 0 and total_size <= limit:
        file = files[0]
        ext = ivr.file_extension(file)
        size = os.path.getsize(file)
        if ivr.is_in_recording(file):
            t0 = datetime.datetime.now()
            ivr.log("start migration: {}".format(file))
            mp4_file = convert_wip_to_mp4(file)
            if mp4_file is not None:
                t1 = datetime.datetime.now()
                remove(file)
                dest_size = os.path.getsize(mp4_file)
                total_size += dest_size
                files.pop(0)
                converted = True

                # output to log
                mp4_name = os.path.basename(mp4_file)
                effect = dest_size / size
                src_size = ivr.with_aux_unit(size)
                dest_size = ivr.with_aux_unit(dest_size)
                interval = (t1 - t0).seconds
                ivr.log(
                    "the file has been migrated: {} ({}B) -> {} ({}B: {:.1%}); {}sec".format(
                        file, src_size, mp4_name, dest_size, effect, interval
                    )
                )
                continue
            else:
                ivr.log("fail to convert to MP4: {}".format(file))
        if total_size + size > limit:
            break
        total_size += size
        files.pop(0)

    # remove files that have exceeded the limit
    for f in files:
        remove(f, "exceeding the limit")

    return converted


# Stop the FFmpeg subprocess if it's running and a TermException will be thrown.
def term_handler(signum, frame):
    global ffmpeg_process
    if ffmpeg_process is not None:
        ffmpeg_process.terminate()
    raise ivr.TermException("")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convert and remove recorded footage files"
    )
    parser.add_argument(
        "-d",
        "--dir",
        metavar="DIR",
        default=ivr.data_dir(),
        help="Directory of footage files (default: {})".format(ivr.data_dir()),
    )
    parser.add_argument(
        "-l",
        "--limit",
        metavar="CAPACITY",
        default="32G",
        help="Maximum total size of files to be saved, such as 32G, 32000M (default: 32G)",
    )
    parser.add_argument(
        "-i",
        "--interval",
        metavar="SECONDS",
        type=int,
        default=20,
        help="Interval at which to monitor the directory (default: 20 sec)",
    )

    try:

        # register SIGTERM handler
        signal.signal(signal.SIGTERM, term_handler)
        signal.signal(signal.SIGINT, term_handler)

        args = parser.parse_args()
        dir = args.dir
        limit = ivr.without_aux_unit(args.limit)
        interval = args.interval

        while True:
            converted = archive_footage_files(dir, limit)
            if converted:
                archive_footage_files(dir, limit)
            time.sleep(interval)

    except ivr.TermException as e:
        ivr.log("IVR terminates the cleaning")
        ivr.beep("cleaning has stopped")
    except Exception as e:
        t = "".join(list(traceback.TracebackException.from_exception(e).format()))
        ivr.log("ERROR: {}".format(t))
        ivr.log("IVR terminates the cleaning by an error")
        ivr.beep("cleaning has stopped due to an error")
        sys.exit(1)
