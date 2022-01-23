import subprocess
import datetime
import os
import sys
import re

FOOTAGE_FILE_PATTERN = r"footage-(\d{4})(\d{2})(\d{2})\.(\d{2})(\.(\d+))?\.[a-zA-Z0-9]+"


def file_extension(file):
    return os.path.splitext(os.path.basename(file))[1]


def is_in_recording(file):
    ext = file_extension(file)
    return ext == ".mkv" or ext == ".avi"


# Returns the recording date and sequence number if the file is a video file recorded by IVR.
# If the file doesn't exist or isn't a footage video, returns None.
def date_of_footage_file(file):
    if os.path.isfile(file):
        matcher = re.fullmatch(FOOTAGE_FILE_PATTERN, os.path.basename(file))
        if matcher is not None:
            year = int(matcher[1])
            month = int(matcher[2])
            date = int(matcher[3])
            hour = int(matcher[4])
            date = datetime.datetime(year, month, date, hour)
            return date
    return None


# Generate a footage file name from the specified date and sequence number.
def footage_file_name(date, sequence, extension):
    date_part = date.strftime("%Y%m%d.%H")
    seq_part = "" if sequence == 0 else (".%d" % sequence)
    return "footage-%s%s.%s" % (date_part, seq_part, extension)


# Notify the user of the specified text.
def beep(speech):
    cmd = ["espeak", speech]
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# Output the specified message as log to the standard output.
def log(msg):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    program = os.path.basename(sys.argv[0])
    print("[{}] {} - {}".format(now, program, msg))
