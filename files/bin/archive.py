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
            ivr.log("start to convert file: {}".format(file))
            mp4_file = convert_wip_to_mp4(file)
            if mp4_file is not None:
                remove(file)
                total_size += os.path.getsize(mp4_file)
                files.pop(0)
                converted = True
                mp4_name = os.path.basename(mp4_file)
                ivr.log("file converted: {} -> {}".format(file, mp4_name))
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convert and remove recorded footage files"
    )
    parser.add_argument("dir", help="Directory of footage files")
    parser.add_argument(
        "limit", default="32G", help="Total file size limit (32G, 32000M, etc.)"
    )
    parser.add_argument(
        "-i",
        "--interval",
        type=int,
        default=20,
        help="Interval at which to monitor the directory",
    )

    args = parser.parse_args()
    dir = args.dir
    limit = args.limit
    interval = args.interval

    multi = 1
    if len(limit) > 0 and not limit[-1].isdigit():
        if limit[-1].upper() == "K":
            multi = 1000
            limit = limit[:-1]
        elif limit[-1].upper() == "M":
            multi = 1000 * 1000
            limit = limit[:-1]
        elif limit[-1].upper() == "G":
            multi = 1000 * 1000 * 1000
            limit = limit[:-1]
        elif limit[-1].upper() == "T":
            multi = 1000 * 1000 * 1000 * 1000
            limit = limit[:-1]
        elif limit[-1].upper() == "P":
            multi = 1000 * 1000 * 1000 * 1000 * 1000
            limit = limit[:-1]
    limit = float(limit) * multi

    while True:
        converted = archive_footage_files(dir, limit)
        if converted:
            archive_footage_files(dir, limit)
        time.sleep(interval)
